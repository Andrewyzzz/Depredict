"""
Flask Blueprint for history and calibration endpoints.

Loads past debate results and computes calibration statistics.
"""

import json
import logging
import math
import os
import statistics
from pathlib import Path
from flask import Blueprint, jsonify

from ..services.prospective_tracker import ProspectiveTracker
from ..services.polymarket_client import PolymarketClient

logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__, url_prefix="/api/history")

# Project root paths: backend/app/api/history.py → up 3 = backend/ → up 1 = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_RESULTS_DIR = _DATA_DIR / "results"
_QUESTIONS_FILE = _DATA_DIR / "questions.json"

# Shared instances for prospective tracking
_prospective_tracker = ProspectiveTracker()
_polymarket_client = PolymarketClient()


def _load_questions() -> list[dict]:
    """Load questions from data/questions.json."""
    if not _QUESTIONS_FILE.exists():
        return []
    with open(_QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_result(question_id: str) -> dict | None:
    """Load a result JSON by question ID from data/results/."""
    result_path = _RESULTS_DIR / f"{question_id}.json"
    if not result_path.exists():
        return None
    with open(result_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_all_results() -> list[tuple[dict, dict]]:
    """Load all (question, result) pairs where both exist."""
    questions = _load_questions()
    pairs = []
    for q in questions:
        result = _load_result(q["id"])
        if result is not None:
            pairs.append((q, result))
    return pairs


@history_bp.route("", methods=["GET"])
def get_history():
    """
    Get list of past debate tasks with outcomes.

    Returns: list of past debates with question, outcome, and key stats.
    """
    questions = _load_questions()
    history = []

    for q in questions:
        result = _load_result(q["id"])
        entry = {
            "id": q["id"],
            "question": q["question"],
            "category": q.get("category", "unknown"),
            "market_price": q.get("market_price"),
            "resolved": q.get("resolved", False),
            "resolution": q.get("resolution"),
            "source": q.get("source", "unknown"),
        }

        if result is not None:
            entry["has_result"] = True
            entry["timestamp"] = result.get("timestamp")
            entry["aggregated_probability"] = result.get("aggregated_probability")
            # Include all mechanism probabilities
            mechanisms = result.get("aggregation_mechanisms", {})
            entry["mechanism_probabilities"] = {
                method: info.get("probability")
                for method, info in mechanisms.items()
            }
        else:
            entry["has_result"] = False

        history.append(entry)

    return jsonify({
        "history": history,
        "total": len(history),
        "with_results": sum(1 for h in history if h.get("has_result")),
    })


@history_bp.route("/<question_id>/result", methods=["GET"])
def get_result(question_id: str):
    """
    Get the full debate result for a specific question.

    Tries: 1) data/results/<question_id>.json (old history)
           2) prospective tracker saved results (new system)
    """
    # Try old history system (data/results/)
    result = _load_result(question_id)

    if result is None:
        # Try prospective tracker saved results
        result = _prospective_tracker.get_debate_result(question_id)

    if result is None:
        # Try task manager state files (backend/data/tasks/)
        _TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "tasks"
        task_file = _TASKS_DIR / f"{question_id}.json"
        if task_file.exists():
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                result = task_data.get("result")
            except Exception:
                pass

    if result is None:
        return jsonify({"error": "result not found"}), 404

    # Enrich with question metadata from old system if available
    questions = _load_questions()
    for q in questions:
        if q["id"] == question_id:
            result["question_id"] = question_id
            if "market_price" not in result or result["market_price"] is None:
                result["market_price"] = q.get("market_price")
            result["resolved"] = q.get("resolved", False)
            result["resolution"] = q.get("resolution")
            result["category"] = q.get("category", "")
            break

    return jsonify(result)


@history_bp.route("/calibration", methods=["GET"])
def get_calibration():
    """
    Get calibration statistics (Brier scores by aggregation method).

    Computes Brier scores only for resolved questions that have debate results.
    """
    pairs = _load_all_results()

    # Filter to resolved questions only
    resolved = [(q, r) for q, r in pairs if q.get("resolved") and q.get("resolution") is not None]

    if not resolved:
        return jsonify({
            "error": "no resolved questions with results available",
            "total_questions": len(pairs),
            "resolved_count": 0,
        })

    # Aggregation methods to evaluate
    methods = [
        "simple_average", "median", "trimmed_mean", "logit_average",
        "extremized", "reputation_weighted", "lmsr_market",
        "peer_prediction", "hybrid",
    ]

    # Compute Brier scores per method
    method_briers: dict[str, list[float]] = {m: [] for m in methods}
    # Also compute for market price baseline
    market_briers: list[float] = []
    # And round1 average (no-debate baseline)
    nodebate_briers: list[float] = []

    for q, result in resolved:
        outcome = 1.0 if q["resolution"] else 0.0

        # Market price Brier score
        mp = q.get("market_price")
        if mp is not None:
            market_briers.append((mp - outcome) ** 2)

        # Round 1 (no-debate) Brier score
        r1_avg = result.get("round1_average")
        if r1_avg is not None:
            p = r1_avg / 100.0
            nodebate_briers.append((p - outcome) ** 2)

        # Mechanism Brier scores
        mechanisms = result.get("aggregation_mechanisms", {})
        for method in methods:
            info = mechanisms.get(method, {})
            prob = info.get("probability")
            if prob is not None:
                p = prob / 100.0
                method_briers[method].append((p - outcome) ** 2)

    # Assemble calibration report
    calibration = {}
    for method in methods:
        scores = method_briers[method]
        if scores:
            calibration[method] = {
                "brier_score": round(statistics.mean(scores), 6),
                "n_questions": len(scores),
                "std": round(statistics.stdev(scores), 6) if len(scores) > 1 else 0.0,
            }

    # Baselines
    baselines = {}
    if market_briers:
        baselines["market_price"] = {
            "brier_score": round(statistics.mean(market_briers), 6),
            "n_questions": len(market_briers),
        }
    if nodebate_briers:
        baselines["no_debate_round1"] = {
            "brier_score": round(statistics.mean(nodebate_briers), 6),
            "n_questions": len(nodebate_briers),
        }

    # Rank methods by Brier score (lower is better)
    ranked = sorted(calibration.items(), key=lambda x: x[1]["brier_score"])

    return jsonify({
        "calibration": dict(ranked),
        "baselines": baselines,
        "total_resolved": len(resolved),
        "best_method": ranked[0][0] if ranked else None,
    })


@history_bp.route("/agents", methods=["GET"])
def get_agent_rankings():
    """
    Get per-agent reputation rankings based on historical performance.

    Computes Brier scores for each agent across all resolved questions.
    """
    pairs = _load_all_results()
    resolved = [(q, r) for q, r in pairs if q.get("resolved") and q.get("resolution") is not None]

    if not resolved:
        return jsonify({
            "error": "no resolved questions with results available",
            "agents": [],
        })

    # Collect per-agent Brier scores from round3 predictions
    agent_scores: dict[str, list[float]] = {}
    agent_meta: dict[str, dict] = {}  # stance, etc.

    for q, result in resolved:
        outcome = 1.0 if q["resolution"] else 0.0
        round3 = result.get("rounds", {}).get("round3", [])

        for agent_result in round3:
            name = agent_result.get("agent_name")
            prob = agent_result.get("probability")
            if name and prob is not None:
                p = prob / 100.0
                bs = (p - outcome) ** 2
                agent_scores.setdefault(name, []).append(bs)
                if name not in agent_meta:
                    agent_meta[name] = {
                        "stance": agent_result.get("stance", "unknown"),
                    }

    # Compute rankings
    agents = []
    for name, scores in agent_scores.items():
        avg_brier = statistics.mean(scores)
        agents.append({
            "name": name,
            "stance": agent_meta.get(name, {}).get("stance", "unknown"),
            "avg_brier_score": round(avg_brier, 6),
            "n_questions": len(scores),
            "std": round(statistics.stdev(scores), 6) if len(scores) > 1 else 0.0,
            "reputation": round(1.0 - avg_brier, 4),  # Simple reputation: 1 - avg_brier
        })

    # Sort by Brier score (lower = better = higher rank)
    agents.sort(key=lambda x: x["avg_brier_score"])

    # Add rank
    for i, agent in enumerate(agents):
        agent["rank"] = i + 1

    return jsonify({
        "agents": agents,
        "total_agents": len(agents),
        "total_resolved": len(resolved),
    })


# ------------------------------------------------------------------
# Prospective prediction endpoints
# ------------------------------------------------------------------

@history_bp.route("/prospective", methods=["GET"])
def get_prospective():
    """
    Get all prospective (forward-looking) predictions.

    Returns: { predictions: [...], stats: {...} }
    """
    predictions = _prospective_tracker.get_all()
    stats = _prospective_tracker.get_stats()

    return jsonify({
        "predictions": predictions,
        "stats": stats,
    })


@history_bp.route("/prospective/check", methods=["POST"])
def check_prospective_resolutions():
    """
    Trigger resolution checking for all pending prospective predictions.

    Queries Polymarket for each pending prediction's market status and
    updates resolved predictions with Brier scores.

    Returns: { result: {...}, stats: {...} }
    """
    try:
        result = _prospective_tracker.check_resolutions(_polymarket_client)
        stats = _prospective_tracker.get_stats()
        return jsonify({
            "result": result,
            "stats": stats,
        })
    except Exception as e:
        logger.exception("Failed to check prospective resolutions")
        return jsonify({"error": str(e)}), 500
