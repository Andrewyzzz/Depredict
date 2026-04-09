"""
Prospective prediction tracker.

Saves and manages predictions on unresolved Polymarket markets,
tracks resolution status, and computes Brier scores once resolved.
"""

import json
import logging
import os
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.calibration import calibrate, load_params

logger = logging.getLogger(__name__)

# Default path: backend/app/services/../../.. = project root -> data/prospective/
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "prospective"
_PREDICTIONS_FILE = "predictions.json"


class ProspectiveTracker:
    """Tracks prospective (forward-looking) predictions on live markets."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._predictions_path = self._data_dir / _PREDICTIONS_FILE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_prediction(
        self,
        question: str,
        slug: str,
        market_price: float,
        debate_result: dict,
        task_id: str | None = None,
    ) -> dict:
        """Save a new prospective prediction from a completed debate.

        Args:
            question: The prediction question text.
            slug: Polymarket market slug for later resolution checking.
            market_price: Market YES price at time of prediction (0-1 scale).
            debate_result: Full debate pipeline result dict.
            task_id: Optional task ID for linking to the debate report.

        Returns:
            The saved prediction record.
        """
        now = datetime.now(timezone.utc)
        pred_id = f"pred_{int(now.timestamp())}"

        # Extract aggregation data
        aggregated_prob = debate_result.get("aggregated_probability")
        mechanisms = debate_result.get("aggregation_mechanisms", {})
        all_mechanisms = {
            method: info.get("probability")
            for method, info in mechanisms.items()
        }

        # Determine which aggregation method was used (hybrid if available)
        aggregation_method = "hybrid" if "hybrid" in mechanisms else "simple_average"

        # Apply post-aggregation calibration (combined predictor + clipping
        # toward market price). Falls back to identity (no-op) if no fitted
        # parameters exist on disk yet.
        cal_params = load_params()
        calibrated_prob = None
        if aggregated_prob is not None:
            p_cal = calibrate(aggregated_prob / 100.0, market_price, cal_params)
            calibrated_prob = round(p_cal * 100.0, 2)

        # Persist the full debate result for later report viewing, enriched
        # with calibrated probability so the report view can show both raw
        # and calibrated forecasts side-by-side.
        if task_id:
            enriched_result = dict(debate_result)
            if calibrated_prob is not None:
                enriched_result["calibrated_probability"] = calibrated_prob
                if not cal_params.is_identity():
                    enriched_result["calibration"] = {
                        "alpha": cal_params.alpha,
                        "delta": cal_params.delta,
                        "fitted_at": cal_params.fitted_at,
                    }
            self._save_debate_result(task_id, enriched_result, question, market_price)

        prediction = {
            "id": pred_id,
            "task_id": task_id,
            "question": question,
            "slug": slug,
            "market_price_at_prediction": round(market_price, 4),
            "model_probability": aggregated_prob,
            "model_probability_calibrated": calibrated_prob,
            "aggregation_method": aggregation_method,
            "all_mechanisms": all_mechanisms,
            "calibration": {
                "alpha": cal_params.alpha,
                "delta": cal_params.delta,
                "fitted_at": cal_params.fitted_at,
            } if not cal_params.is_identity() else None,
            "predicted_at": now.isoformat(),
            "source": "prospective",
            "status": "pending",
            "resolved_at": None,
            "resolution": None,
            "model_brier": None,
            "model_brier_calibrated": None,
            "market_brier": None,
        }

        predictions = self._load_predictions()

        # Deduplicate by slug — skip if already predicted
        existing_slugs = {p.get("slug") for p in predictions}
        if slug in existing_slugs:
            logger.info("Skipping duplicate prediction for slug=%s", slug)
            return prediction

        predictions.append(prediction)
        self._save_predictions(predictions)

        logger.info("Saved prospective prediction %s for slug=%s", pred_id, slug)
        return prediction

    def get_all(self) -> list[dict]:
        """Return all prospective predictions."""
        return self._load_predictions()

    def get_pending(self) -> list[dict]:
        """Return only pending (unresolved) predictions."""
        return [p for p in self._load_predictions() if p.get("status") == "pending"]

    def check_resolutions(self, polymarket_client) -> dict:
        """Check each pending prediction against Polymarket for resolution.

        Args:
            polymarket_client: A PolymarketClient instance with get_market_by_slug().

        Returns:
            Summary dict with counts of checked, resolved, and still-pending.
        """
        predictions = self._load_predictions()
        checked = 0
        newly_resolved = 0

        for pred in predictions:
            if pred.get("status") != "pending":
                continue

            slug = pred.get("slug")
            if not slug:
                continue

            checked += 1

            try:
                market = polymarket_client.get_market_by_slug(slug)
            except Exception:
                logger.warning("Failed to fetch market for slug=%s", slug)
                continue

            if market is None:
                logger.debug("Market not found for slug=%s", slug)
                continue

            # Check if market is resolved by looking at outcome_prices
            resolution = polymarket_client._extract_resolution(market)
            if resolution is None:
                continue  # Not yet resolved

            # Market is resolved -- update the prediction
            now = datetime.now(timezone.utc).isoformat()
            outcome = 1.0 if resolution else 0.0

            # Compute Brier scores
            model_prob = pred.get("model_probability")
            calibrated_prob = pred.get("model_probability_calibrated")
            market_price = pred.get("market_price_at_prediction")

            model_brier = None
            calibrated_brier = None
            market_brier = None

            if model_prob is not None:
                p = model_prob / 100.0  # model_probability is 0-100 scale
                model_brier = round((p - outcome) ** 2, 6)

            if calibrated_prob is not None:
                p = calibrated_prob / 100.0
                calibrated_brier = round((p - outcome) ** 2, 6)

            if market_price is not None:
                market_brier = round((market_price - outcome) ** 2, 6)

            pred["status"] = "resolved"
            pred["resolved_at"] = now
            pred["resolution"] = resolution
            pred["model_brier"] = model_brier
            pred["model_brier_calibrated"] = calibrated_brier
            pred["market_brier"] = market_brier

            newly_resolved += 1
            logger.info(
                "Resolved prediction %s: resolution=%s, model_brier=%.4f, market_brier=%.4f",
                pred["id"], resolution,
                model_brier or 0, market_brier or 0,
            )

        if newly_resolved > 0:
            self._save_predictions(predictions)

        still_pending = sum(1 for p in predictions if p.get("status") == "pending")
        return {
            "checked": checked,
            "newly_resolved": newly_resolved,
            "still_pending": still_pending,
            "total": len(predictions),
        }

    def get_stats(self) -> dict:
        """Return summary statistics for all prospective predictions.

        Returns:
            Dict with total, pending, resolved counts and average Brier scores.
        """
        predictions = self._load_predictions()
        total = len(predictions)
        pending = sum(1 for p in predictions if p.get("status") == "pending")
        resolved = sum(1 for p in predictions if p.get("status") == "resolved")

        model_briers = [
            p["model_brier"] for p in predictions
            if p.get("status") == "resolved" and p.get("model_brier") is not None
        ]
        calibrated_briers = [
            p["model_brier_calibrated"] for p in predictions
            if p.get("status") == "resolved" and p.get("model_brier_calibrated") is not None
        ]
        market_briers = [
            p["market_brier"] for p in predictions
            if p.get("status") == "resolved" and p.get("market_brier") is not None
        ]

        avg_model_brier = round(statistics.mean(model_briers), 6) if model_briers else None
        avg_calibrated_brier = (
            round(statistics.mean(calibrated_briers), 6) if calibrated_briers else None
        )
        avg_market_brier = round(statistics.mean(market_briers), 6) if market_briers else None

        return {
            "total": total,
            "pending": pending,
            "resolved": resolved,
            "avg_model_brier": avg_model_brier,
            "avg_calibrated_brier": avg_calibrated_brier,
            "avg_market_brier": avg_market_brier,
            "model_beats_market": (
                avg_model_brier < avg_market_brier
                if avg_model_brier is not None and avg_market_brier is not None
                else None
            ),
            "calibrated_beats_market": (
                avg_calibrated_brier < avg_market_brier
                if avg_calibrated_brier is not None and avg_market_brier is not None
                else None
            ),
        }

    def get_debate_result(self, task_id: str) -> dict | None:
        """Load a persisted debate result by task_id."""
        result_path = self._data_dir / "results" / f"{task_id}.json"
        if not result_path.exists():
            return None
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load debate result %s: %s", task_id, e)
            return None

    def _save_debate_result(self, task_id: str, result: dict, question: str, market_price: float):
        """Persist a full debate result to disk for later report viewing."""
        results_dir = self._data_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path = results_dir / f"{task_id}.json"
        # Enrich with metadata
        enriched = dict(result)
        enriched["question"] = question
        enriched["market_price"] = market_price
        try:
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(enriched, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            logger.exception("Failed to save debate result for task_id=%s", task_id)

    # ------------------------------------------------------------------
    # Persistence helpers (atomic writes via temp file + rename)
    # ------------------------------------------------------------------

    def _load_predictions(self) -> list[dict]:
        """Load predictions from JSON file."""
        if not self._predictions_path.exists():
            return []
        try:
            with open(self._predictions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load predictions: %s", e)
            return []

    def _save_predictions(self, predictions: list[dict]) -> None:
        """Atomically save predictions to JSON file."""
        # Write to temp file in same directory, then rename for atomicity
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._data_dir), suffix=".tmp", prefix="predictions_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(predictions, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._predictions_path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
