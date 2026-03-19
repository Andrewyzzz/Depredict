"""
Batch experiment runner for evaluating aggregation mechanisms.

Runs debates on resolved questions and compares Brier Scores across:
- Baseline: No debate (Round 1 simple average)
- M0: Simple average (Round 3)
- M0b: Extremized average (Round 3)
- M1: Reputation-weighted aggregation
- M2: LMSR prediction market
- M3: Peer prediction (BTS)
- M4: Hybrid mechanism
- Reference: Market price (Polymarket)

Also computes:
- Per-agent Brier Scores for reputation updates
- Calibration analysis
- BTS ranking vs actual ranking correlation

Usage:
    python experiment.py              # Run all resolved questions
    python experiment.py --limit 3    # Run first 3 questions only (test mode)
"""

import argparse
import json
import math
import os
import statistics
from datetime import datetime

from aggregator import ReputationTracker, get_oracle_single_agent
from config import DATA_DIR, RESULTS_DIR, REPUTATION_DECAY
from debate import DebatePipeline


# ── Scoring Functions ──────────────────────────────────────────────────────


def brier_score(predicted: float, actual: bool) -> float:
    """Brier Score for a single prediction. Lower is better."""
    outcome = 1.0 if actual else 0.0
    return (predicted - outcome) ** 2


def log_score(predicted: float, actual: bool) -> float:
    """Logarithmic score for a single prediction. Higher (less negative) is better."""
    eps = 1e-10
    if actual:
        return math.log(max(predicted, eps))
    else:
        return math.log(max(1 - predicted, eps))


def calc_scores(predictions: list[float], actuals: list[bool]) -> dict:
    """Calculate average Brier and Log scores."""
    if not predictions or not actuals:
        return {"brier": float("nan"), "log": float("nan")}

    briers = [brier_score(p, a) for p, a in zip(predictions, actuals)]
    logs = [log_score(p, a) for p, a in zip(predictions, actuals)]
    return {
        "brier": statistics.mean(briers),
        "log": statistics.mean(logs),
    }


# ── Calibration Analysis ──────────────────────────────────────────────────


def calibration_bins(
    predictions: list[float], actuals: list[bool], n_bins: int = 10
) -> list[dict]:
    """
    Compute calibration bins for reliability diagram.

    Groups predictions into bins and compares predicted vs actual frequency.
    """
    bins = [{"predictions": [], "actuals": []} for _ in range(n_bins)]

    for pred, actual in zip(predictions, actuals):
        bin_idx = min(int(pred * n_bins), n_bins - 1)
        bins[bin_idx]["predictions"].append(pred)
        bins[bin_idx]["actuals"].append(1.0 if actual else 0.0)

    result = []
    for i, b in enumerate(bins):
        if b["predictions"]:
            avg_pred = statistics.mean(b["predictions"])
            avg_actual = statistics.mean(b["actuals"])
            result.append({
                "bin": f"{i/n_bins:.1f}-{(i+1)/n_bins:.1f}",
                "n": len(b["predictions"]),
                "avg_predicted": round(avg_pred, 4),
                "avg_actual": round(avg_actual, 4),
                "calibration_error": round(abs(avg_pred - avg_actual), 4),
            })

    return result


def expected_calibration_error(predictions: list[float], actuals: list[bool]) -> float:
    """Expected Calibration Error (ECE): weighted average of bin calibration errors."""
    bins = calibration_bins(predictions, actuals)
    total_n = sum(b["n"] for b in bins)
    if total_n == 0:
        return float("nan")
    return sum(b["n"] / total_n * b["calibration_error"] for b in bins)


# ── Data Loading ───────────────────────────────────────────────────────────


def load_questions(resolved_only: bool = False) -> list[dict]:
    """Load questions from questions.json."""
    path = os.path.join(DATA_DIR, "questions.json")
    with open(path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if resolved_only:
        questions = [q for q in questions if q.get("resolved")]

    return questions


# ── Main Experiment ────────────────────────────────────────────────────────


MECHANISM_NAMES = [
    "simple_average",
    "median",
    "trimmed_mean",
    "logit_average",
    "extremized",
    "reputation_weighted",
    "lmsr_market",
    "peer_prediction",
    "hybrid",
]


def run_experiment(limit: int | None = None):
    """Run the full experiment comparing all aggregation mechanisms."""
    questions = load_questions(resolved_only=True)

    if limit:
        questions = questions[:limit]
        print(f"[限制模式] 只运行前 {limit} 个问题")

    if not questions:
        print("没有已结算的问题可用于评估。")
        print("请在 data/questions.json 中添加 resolved=true 的问题。")
        return

    print(f"找到 {len(questions)} 个已结算问题")
    print("=" * 60)

    # Shared reputation tracker across questions (simulates sequential deployment)
    agent_names = [p["name"] for p in __import__("config").AGENT_PERSONAS]
    reputation_tracker = ReputationTracker(agent_names, decay=REPUTATION_DECAY)
    pipeline = DebatePipeline(reputation_tracker=reputation_tracker)

    results = []
    actuals = []

    # Per-mechanism prediction lists
    mechanism_preds: dict[str, list[float]] = {m: [] for m in MECHANISM_NAMES}
    no_debate_preds = []
    market_preds = []

    for q in questions:
        print(f"\n处理: {q['question']}")

        try:
            result = pipeline.run(q["question"], q["market_price"])
            result["actual"] = q["resolution"]
            result["question_id"] = q["id"]
            results.append(result)

            actual = q["resolution"]
            actuals.append(actual)

            # Round 1 average (no debate baseline)
            r1_avg = result.get("round1_average")
            no_debate_preds.append(r1_avg / 100.0 if r1_avg is not None else 0.5)

            # Market price
            mp = result.get("market_price")
            market_preds.append(mp if mp is not None else 0.5)

            # Each mechanism's prediction
            agg_mechs = result.get("aggregation_mechanisms", {})
            for method in MECHANISM_NAMES:
                prob = agg_mechs.get(method, {}).get("probability")
                mechanism_preds[method].append(prob / 100.0 if prob is not None else 0.5)

            # Update reputations based on per-agent Brier Scores
            round3 = result.get("rounds", {}).get("round3", [])
            for agent_result in round3:
                name = agent_result.get("agent_name")
                prob = agent_result.get("probability")
                if name and prob is not None:
                    bs = brier_score(prob / 100.0, actual)
                    reputation_tracker.update(name, bs)

            # Save individual result
            os.makedirs(RESULTS_DIR, exist_ok=True)
            result_path = os.path.join(RESULTS_DIR, f"{q['id']}.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"  错误: {e}")
            continue

    if not results:
        print("\n没有成功的实验结果。")
        return

    # ── Results Summary ────────────────────────────────────────────────────

    print(f"\n{'='*80}")
    print("实验结果: 聚合机制对比")
    print(f"{'='*80}")

    # Build score table
    all_methods = {}
    all_methods["no_debate (R1)"] = calc_scores(no_debate_preds, actuals)
    all_methods["no_debate (R1)"]["ece"] = expected_calibration_error(no_debate_preds, actuals)

    for method in MECHANISM_NAMES:
        scores = calc_scores(mechanism_preds[method], actuals)
        scores["ece"] = expected_calibration_error(mechanism_preds[method], actuals)
        all_methods[method] = scores

    all_methods["market_price"] = calc_scores(market_preds, actuals)
    all_methods["market_price"]["ece"] = expected_calibration_error(market_preds, actuals)

    # Print table
    print(f"\n  {'Method':<25s} {'Brier ↓':>10s} {'Log Score ↑':>12s} {'ECE ↓':>10s}")
    print(f"  {'-'*25} {'-'*10} {'-'*12} {'-'*10}")

    for method, scores in all_methods.items():
        brier_str = f"{scores['brier']:.4f}" if not math.isnan(scores["brier"]) else "N/A"
        log_str = f"{scores['log']:.4f}" if not math.isnan(scores["log"]) else "N/A"
        ece_str = f"{scores['ece']:.4f}" if not math.isnan(scores["ece"]) else "N/A"
        print(f"  {method:<25s} {brier_str:>10s} {log_str:>12s} {ece_str:>10s}")

    # Best mechanism
    debate_methods = {m: s for m, s in all_methods.items()
                      if m not in ("no_debate (R1)", "market_price")}
    best_method = min(debate_methods, key=lambda m: debate_methods[m]["brier"])
    print(f"\n  最佳机制: {best_method} (Brier: {debate_methods[best_method]['brier']:.4f})")

    # ── Reputation Analysis ────────────────────────────────────────────────

    print(f"\n{'='*80}")
    print("Agent 信誉排名 (经过所有问题后)")
    print(f"{'='*80}")

    rep_snapshot = reputation_tracker.snapshot()
    sorted_agents = sorted(rep_snapshot.items(), key=lambda x: x[1]["reputation"], reverse=True)

    print(f"\n  {'Agent':<20s} {'Reputation':>12s} {'Avg Brier':>12s} {'Questions':>10s}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10}")

    for name, info in sorted_agents:
        avg_b = f"{info['avg_brier']:.4f}" if info["avg_brier"] is not None else "N/A"
        print(f"  {name:<20s} {info['reputation']:>12.4f} {avg_b:>12s} {info['total_questions']:>10d}")

    # ── BTS Validation ─────────────────────────────────────────────────────

    print(f"\n{'='*80}")
    print("BTS 验证: 元预测质量 vs 实际 Brier Score 排名")
    print(f"{'='*80}")

    # Check if we have BTS data from the last question
    if results:
        last_result = results[-1]
        bts_details = (last_result.get("aggregation_mechanisms", {})
                       .get("peer_prediction", {})
                       .get("details", {}))
        agent_scores = bts_details.get("agent_scores", {})

        if agent_scores:
            print(f"\n  (基于最后一个问题的 BTS 分数)")
            print(f"  {'Agent':<20s} {'BTS Score':>12s} {'Weight':>10s} {'Prediction':>12s}")
            print(f"  {'-'*20} {'-'*12} {'-'*10} {'-'*12}")

            sorted_bts = sorted(agent_scores.items(), key=lambda x: x[1]["bts_score"], reverse=True)
            for name, info in sorted_bts:
                print(f"  {name:<20s} {info['bts_score']:>12.4f} {info['weight']:>10.4f} {info['prediction']*100:>11.1f}%")

    # ── Per-Question Details ───────────────────────────────────────────────

    print(f"\n{'='*80}")
    print("逐题详情")
    print(f"{'='*80}")

    for i, r in enumerate(results):
        actual_str = "YES" if r["actual"] else "NO"
        print(f"\n  {r['question']}")
        print(f"    实际结果: {actual_str}")
        print(f"    Round 1 (无辩论):     {no_debate_preds[i]*100:>6.1f}%  |  Brier: {brier_score(no_debate_preds[i], r['actual']):.4f}")

        agg_mechs = r.get("aggregation_mechanisms", {})
        for method in MECHANISM_NAMES:
            prob = mechanism_preds[method][i]
            bs = brier_score(prob, r["actual"])
            print(f"    {method:<22s}: {prob*100:>6.1f}%  |  Brier: {bs:.4f}")

        print(f"    {'market_price':<22s}: {market_preds[i]*100:>6.1f}%  |  Brier: {brier_score(market_preds[i], r['actual']):.4f}")

    # ── Save Experiment Summary ────────────────────────────────────────────

    summary = {
        "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
        "num_questions": len(results),
        "scores": {
            method: {
                "brier": round(scores["brier"], 6),
                "log": round(scores["log"], 6),
                "ece": round(scores["ece"], 6),
            }
            for method, scores in all_methods.items()
        },
        "best_mechanism": best_method,
        "reputation_final": rep_snapshot,
        "per_question": [
            {
                "id": r["question_id"],
                "question": r["question"],
                "actual": r["actual"],
                "round1_avg": r.get("round1_average"),
                "market_price": r.get("market_price"),
                "mechanism_predictions": {
                    method: round(mechanism_preds[method][i] * 100, 2)
                    for method in MECHANISM_NAMES
                },
            }
            for i, r in enumerate(results)
        ],
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary_path = os.path.join(RESULTS_DIR, "experiment_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n实验摘要已保存到 {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max questions to run")
    args = parser.parse_args()
    run_experiment(limit=args.limit)
