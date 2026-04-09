#!/usr/bin/env python3
"""
Fit post-aggregation calibration parameters from historical resolved predictions.

Reads data/prospective/predictions.json, runs LOO-CV grid search over (α, δ)
for the combined-predictor + clipping strategy on mid-range markets, and
saves the result to data/prospective/calibration.json.

After running this, new predictions made by the backend will automatically
have calibrated probabilities attached.

Usage:
    python scripts/fit_calibration.py
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from calibration import _DEFAULT_PARAMS_PATH, fit_calibration, save_params  # noqa: E402

PRED_PATH = ROOT / "data" / "prospective" / "predictions.json"

# Mid-range filter mirrors the n=143 significance report. Outside this band
# the model is systematically dominated by market and calibration cannot
# extract additional signal.
MID_LO, MID_HI = 0.20, 0.70


def load_resolved() -> list[dict]:
    with open(PRED_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [
        p for p in raw
        if p.get("status") == "resolved"
        and p.get("resolution") is not None
        and p.get("market_price_at_prediction") is not None
        and p.get("all_mechanisms", {}).get("hybrid") is not None
    ]


def main() -> int:
    if not PRED_PATH.exists():
        print(f"ERROR: predictions file not found at {PRED_PATH}", file=sys.stderr)
        return 1

    preds = load_resolved()
    print(f"Loaded {len(preds)} resolved predictions from {PRED_PATH}")

    mid = [p for p in preds if MID_LO <= p["market_price_at_prediction"] < MID_HI]
    print(f"Filtered to mid-range markets [{MID_LO}, {MID_HI}): n = {len(mid)}")

    if len(mid) < 10:
        print("ERROR: not enough samples to fit calibration", file=sys.stderr)
        return 1

    model = np.array([p["all_mechanisms"]["hybrid"] / 100.0 for p in mid])
    market = np.array([p["market_price_at_prediction"] for p in mid])
    outcomes = np.array([1.0 if p["resolution"] else 0.0 for p in mid])

    print("Fitting (α, δ) via LOO-CV grid search...")
    result = fit_calibration(model, market, outcomes)

    print()
    print("=" * 64)
    print("Calibration Fit Result")
    print("=" * 64)
    print(f"  Samples (LOO-CV):    n = {result.n}")
    print(f"  Best α (median):     {result.params.alpha:.3f}")
    print(f"  Best δ (median):     {result.params.delta:.3f}")
    print()
    print(f"  Raw model Brier:     {result.raw_brier:.4f}")
    print(f"  Market Brier:        {result.market_brier:.4f}")
    print(f"  Calibrated Brier:    {result.calibrated_brier:.4f}")
    delta_b = result.calibrated_brier - result.market_brier
    print(f"    Δ vs market:       {delta_b:+.4f}")
    print()
    p = result.p_value
    sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else "n.s."
    print(f"  One-sided p-value:   {p:.4f}  ({sig})  (calibrated < market)")
    print()
    a_lo, a_hi = np.percentile(result.alpha_per_fold, [25, 75])
    d_lo, d_hi = np.percentile(result.delta_per_fold, [25, 75])
    print(f"  α IQR across folds:  [{a_lo:.2f}, {a_hi:.2f}]")
    print(f"  δ IQR across folds:  [{d_lo:.2f}, {d_hi:.2f}]")
    print()

    save_params(result.params)
    print(f"Saved calibration params to {_DEFAULT_PARAMS_PATH}")

    if p >= 0.05:
        print()
        print("WARNING: calibrated predictions are not yet significantly better")
        print("         than market (p ≥ 0.05). Expand the resolved sample.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
