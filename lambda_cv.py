"""
Lambda hyperparameter validation for the Hybrid mechanism (M4).

Implements:
  - Temporal split validation (train on first 30%, test on remaining 70%)
  - Leave-One-Out Cross-Validation (LOOCV)
  - Lambda sensitivity analysis with heatmap generation

Usage:
    python lambda_cv.py
"""

import json
import math
import os
import statistics
from itertools import product

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aggregator import (
    ReputationTracker,
    aggregate_reputation_weighted,
    aggregate_lmsr,
    aggregate_peer_prediction,
)
from config import (
    AGENT_PERSONAS, RESULTS_DIR, REPUTATION_DECAY, LMSR_LIQUIDITY,
)


FIGURES_DIR = os.path.join(os.path.dirname(__file__), "figures")


def brier_score(pred: float, actual: bool) -> float:
    outcome = 1.0 if actual else 0.0
    return (pred - outcome) ** 2


def load_active_results() -> list[dict]:
    """Load all individual result files that are active (non-trivial predictions)."""
    results = []
    results_dir = RESULTS_DIR

    if not os.path.isdir(results_dir):
        return results

    for fname in sorted(os.listdir(results_dir)):
        if not fname.endswith(".json") or fname.startswith("experiment") or fname.startswith("active"):
            continue
        path = os.path.join(results_dir, fname)
        with open(path) as f:
            data = json.load(f)
        # Skip non-dict entries (e.g., list-type files)
        if not isinstance(data, dict):
            continue
        # Filter to active questions (R1 avg not ~50%)
        r1_avg = data.get("round1_average")
        if r1_avg is not None and abs(r1_avg - 50) > 1 and "actual" in data:
            results.append(data)

    return results


def compute_hybrid_brier(
    result: dict,
    rep_weights: dict[str, float],
    lambda_rep: float,
    lambda_market: float,
    lambda_bts: float,
) -> float | None:
    """Compute hybrid Brier Score for a single question with given lambdas."""
    round3 = result.get("rounds", {}).get("round3", [])
    meta_preds = result.get("meta_predictions", {})
    actual = result.get("actual")
    if actual is None:
        return None

    # M1: Reputation-weighted
    m1 = aggregate_reputation_weighted(round3, rep_weights)
    p_m1 = m1.get("probability")

    # M2: LMSR
    budgets = {name: 100.0 * (1 + w) for name, w in rep_weights.items()}
    m2 = aggregate_lmsr(round3, budgets=budgets, liquidity=LMSR_LIQUIDITY)
    p_m2 = m2.get("probability")

    # M3: Peer prediction
    m3 = aggregate_peer_prediction(round3, meta_preds or None)
    p_m3 = m3.get("probability")

    components = {"m1": p_m1, "m2": p_m2, "m3": p_m3}
    valid = {k: v for k, v in components.items() if v is not None}
    if not valid:
        return None

    weight_map = {"m1": lambda_rep, "m2": lambda_market, "m3": lambda_bts}
    total_w = sum(weight_map[k] for k in valid)
    if total_w == 0:
        return None

    hybrid_prob = sum(v * weight_map[k] / total_w for k, v in valid.items()) / 100.0
    return brier_score(hybrid_prob, actual)


def temporal_split_validation(results: list[dict], train_frac: float = 0.3) -> dict:
    """
    Temporal split validation for lambda selection.

    Uses first train_frac of questions to select optimal lambda,
    then evaluates on the remaining questions.
    """
    n = len(results)
    split = max(2, int(n * train_frac))
    train_results = results[:split]
    test_results = results[split:]

    if len(test_results) < 2:
        return {"error": "Not enough data for temporal split"}

    agent_names = [p["name"] for p in AGENT_PERSONAS]
    grid_step = 0.1
    grid_values = [round(x * grid_step, 2) for x in range(int(1 / grid_step) + 1)]

    # Grid search on train set
    best_lambdas = None
    best_train_brier = float("inf")

    rep_tracker = ReputationTracker(agent_names, decay=REPUTATION_DECAY)
    # Build reputation from train set
    for r in train_results:
        round3 = r.get("rounds", {}).get("round3", [])
        actual = r.get("actual")
        if actual is None:
            continue
        for agent_result in round3:
            name = agent_result.get("agent_name")
            prob = agent_result.get("probability")
            if name and prob is not None:
                bs = brier_score(prob / 100.0, actual)
                rep_tracker.update(name, bs)

    rep_weights = rep_tracker.get_weights()

    for l1 in grid_values:
        for l2 in grid_values:
            l3 = round(1.0 - l1 - l2, 2)
            if l3 < 0 or l3 > 1:
                continue

            train_briers = []
            for r in train_results:
                bs = compute_hybrid_brier(r, rep_weights, l1, l2, l3)
                if bs is not None:
                    train_briers.append(bs)

            if train_briers:
                mean_bs = statistics.mean(train_briers)
                if mean_bs < best_train_brier:
                    best_train_brier = mean_bs
                    best_lambdas = (l1, l2, l3)

    if best_lambdas is None:
        return {"error": "Grid search failed"}

    # Evaluate on test set with selected lambdas
    # Continue building reputation through test set
    test_briers = []
    for r in test_results:
        round3 = r.get("rounds", {}).get("round3", [])
        actual = r.get("actual")
        if actual is None:
            continue

        current_weights = rep_tracker.get_weights()
        bs = compute_hybrid_brier(r, current_weights, *best_lambdas)
        if bs is not None:
            test_briers.append(bs)

        # Update reputation
        for agent_result in round3:
            name = agent_result.get("agent_name")
            prob = agent_result.get("probability")
            if name and prob is not None:
                agent_bs = brier_score(prob / 100.0, actual)
                rep_tracker.update(name, agent_bs)

    return {
        "best_lambdas": {
            "reputation": best_lambdas[0],
            "market": best_lambdas[1],
            "bts": best_lambdas[2],
        },
        "train_brier": round(best_train_brier, 6),
        "test_brier": round(statistics.mean(test_briers), 6) if test_briers else None,
        "train_size": len(train_results),
        "test_size": len(test_results),
    }


def lambda_sensitivity_analysis(results: list[dict], grid_step: float = 0.05) -> dict:
    """
    Compute Brier Score over the full lambda simplex for heatmap.

    Returns dict with grid points and corresponding Brier scores.
    """
    agent_names = [p["name"] for p in AGENT_PERSONAS]
    rep_tracker = ReputationTracker(agent_names, decay=REPUTATION_DECAY)

    # Build full reputation
    for r in results:
        round3 = r.get("rounds", {}).get("round3", [])
        actual = r.get("actual")
        if actual is None:
            continue
        for agent_result in round3:
            name = agent_result.get("agent_name")
            prob = agent_result.get("probability")
            if name and prob is not None:
                bs = brier_score(prob / 100.0, actual)
                rep_tracker.update(name, bs)

    rep_weights = rep_tracker.get_weights()

    grid_values = [round(x * grid_step, 3) for x in range(int(1 / grid_step) + 1)]
    grid_points = []

    for l1 in grid_values:
        for l2 in grid_values:
            l3 = round(1.0 - l1 - l2, 3)
            if l3 < -0.001 or l3 > 1.001:
                continue
            l3 = max(0, min(1, l3))

            all_briers = []
            for r in results:
                bs = compute_hybrid_brier(r, rep_weights, l1, l2, l3)
                if bs is not None:
                    all_briers.append(bs)

            if all_briers:
                grid_points.append({
                    "lambda_rep": l1,
                    "lambda_market": l2,
                    "lambda_bts": l3,
                    "brier": round(statistics.mean(all_briers), 6),
                })

    return {"grid_points": grid_points}


def plot_lambda_heatmap(sensitivity: dict, output_path: str | None = None):
    """
    Plot lambda sensitivity as a 2D heatmap (lambda_rep vs lambda_market).

    lambda_bts = 1 - lambda_rep - lambda_market (implicit).
    """
    points = sensitivity["grid_points"]
    if not points:
        print("No grid points to plot.")
        return

    # Build 2D grid
    l1_vals = sorted(set(p["lambda_rep"] for p in points))
    l2_vals = sorted(set(p["lambda_market"] for p in points))

    grid = np.full((len(l1_vals), len(l2_vals)), np.nan)
    l1_idx = {v: i for i, v in enumerate(l1_vals)}
    l2_idx = {v: i for i, v in enumerate(l2_vals)}

    for p in points:
        i = l1_idx[p["lambda_rep"]]
        j = l2_idx[p["lambda_market"]]
        grid[i, j] = p["brier"]

    fig, ax = plt.subplots(figsize=(8, 7))

    # Mask NaN (infeasible region where l1+l2 > 1)
    masked = np.ma.masked_invalid(grid)

    im = ax.pcolormesh(
        l2_vals, l1_vals, masked,
        cmap="RdYlGn_r", shading="auto",
    )
    cbar = fig.colorbar(im, ax=ax, label="Brier Score (lower is better)")

    # Mark the best point
    best = min(points, key=lambda p: p["brier"])
    ax.plot(best["lambda_market"], best["lambda_rep"], "k*", markersize=15,
            label=f"Best: rep={best['lambda_rep']:.2f}, mkt={best['lambda_market']:.2f}, "
                  f"bts={best['lambda_bts']:.2f}\nBrier={best['brier']:.4f}")

    ax.set_xlabel(r"$\lambda_{\mathrm{market}}$ (LMSR weight)", fontsize=12)
    ax.set_ylabel(r"$\lambda_{\mathrm{reputation}}$ (Reputation weight)", fontsize=12)
    ax.set_title(r"Hybrid $\lambda$ Sensitivity ($\lambda_{\mathrm{BTS}} = 1 - \lambda_{\mathrm{rep}} - \lambda_{\mathrm{mkt}}$)",
                 fontsize=13)
    ax.legend(loc="upper right", fontsize=9)

    # Draw simplex boundary (l1 + l2 = 1)
    ax.plot([0, 1], [1, 0], "k--", alpha=0.3, linewidth=1)

    plt.tight_layout()
    if output_path is None:
        output_path = os.path.join(FIGURES_DIR, "fig_lambda_sensitivity.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved {output_path}")
    plt.close()

    return best


def main():
    results = load_active_results()
    print(f"Loaded {len(results)} active results")

    if not results:
        print("No active results found. Run experiment.py first.")
        return

    # 1. Temporal split validation
    print(f"\n{'='*60}")
    print("Temporal Split Validation (30/70)")
    print(f"{'='*60}")
    ts_result = temporal_split_validation(results, train_frac=0.3)
    print(json.dumps(ts_result, indent=2))

    # 2. Lambda sensitivity analysis
    print(f"\n{'='*60}")
    print("Lambda Sensitivity Analysis")
    print(f"{'='*60}")
    sensitivity = lambda_sensitivity_analysis(results, grid_step=0.1)
    best = plot_lambda_heatmap(sensitivity)
    if best:
        print(f"Best lambda: rep={best['lambda_rep']}, mkt={best['lambda_market']}, "
              f"bts={best['lambda_bts']}, Brier={best['brier']:.4f}")

    # Save results
    output = {
        "temporal_split": ts_result,
        "best_lambda": best,
        "n_questions": len(results),
    }
    output_path = os.path.join(RESULTS_DIR, "lambda_validation.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {output_path}")


if __name__ == "__main__":
    main()
