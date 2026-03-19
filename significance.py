"""
Statistical significance testing for aggregation mechanism comparisons.

Implements:
  - Paired bootstrap test for Brier Score differences
  - Diebold-Mariano test for forecast comparison
  - Bootstrap confidence intervals

Usage:
    from significance import paired_bootstrap_test, diebold_mariano_test
"""

import math
import statistics
from typing import Optional

import numpy as np


def brier_score(pred: float, actual: bool) -> float:
    outcome = 1.0 if actual else 0.0
    return (pred - outcome) ** 2


def paired_bootstrap_test(
    preds_a: list[float],
    preds_b: list[float],
    actuals: list[bool],
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict:
    """
    Paired bootstrap test for Brier Score difference.

    Tests H0: E[BS_a] = E[BS_b]
    H1: E[BS_a] != E[BS_b]

    Args:
        preds_a: Predictions from method A (0-1 scale).
        preds_b: Predictions from method B (0-1 scale).
        actuals: Actual outcomes.
        n_bootstrap: Number of bootstrap resamples.
        seed: Random seed for reproducibility.

    Returns:
        Dict with observed_diff, p_value, ci_lower, ci_upper.
        Negative diff means A is better (lower Brier).
    """
    rng = np.random.RandomState(seed)
    n = len(preds_a)

    diffs = [
        brier_score(pa, o) - brier_score(pb, o)
        for pa, pb, o in zip(preds_a, preds_b, actuals)
    ]
    observed_diff = float(np.mean(diffs))

    boot_diffs = []
    for _ in range(n_bootstrap):
        idx = rng.choice(n, n, replace=True)
        boot_mean = float(np.mean([diffs[i] for i in idx]))
        boot_diffs.append(boot_mean)

    boot_diffs = np.array(boot_diffs)

    # Two-sided p-value
    if observed_diff < 0:
        p_value = float(np.mean(boot_diffs >= 0)) * 2
    elif observed_diff > 0:
        p_value = float(np.mean(boot_diffs <= 0)) * 2
    else:
        p_value = 1.0
    p_value = min(p_value, 1.0)

    ci_lower, ci_upper = float(np.percentile(boot_diffs, 2.5)), float(np.percentile(boot_diffs, 97.5))

    return {
        "observed_diff": round(observed_diff, 6),
        "p_value": round(p_value, 4),
        "ci_lower": round(ci_lower, 6),
        "ci_upper": round(ci_upper, 6),
        "significant_005": p_value < 0.05,
        "significant_001": p_value < 0.01,
    }


def diebold_mariano_test(
    preds_a: list[float],
    preds_b: list[float],
    actuals: list[bool],
) -> dict:
    """
    Diebold-Mariano test for equal predictive accuracy.

    Uses squared error loss (Brier Score). Tests whether the mean
    loss differential is significantly different from zero.

    Args:
        preds_a: Predictions from method A.
        preds_b: Predictions from method B.
        actuals: Actual outcomes.

    Returns:
        Dict with test statistic, p_value (two-sided).
    """
    n = len(preds_a)
    if n < 3:
        return {"dm_stat": float("nan"), "p_value": float("nan")}

    d = [
        brier_score(pa, o) - brier_score(pb, o)
        for pa, pb, o in zip(preds_a, preds_b, actuals)
    ]
    d_bar = statistics.mean(d)

    # Variance of d (with Newey-West correction for h=1 step ahead)
    gamma_0 = sum((di - d_bar) ** 2 for di in d) / n
    if gamma_0 == 0:
        return {"dm_stat": float("nan"), "p_value": float("nan")}

    dm_stat = d_bar / math.sqrt(gamma_0 / n)

    # Two-sided p-value using normal approximation
    from scipy.stats import norm
    p_value = 2 * (1 - norm.cdf(abs(dm_stat)))

    return {
        "dm_stat": round(dm_stat, 4),
        "p_value": round(p_value, 4),
        "significant_005": p_value < 0.05,
        "significant_001": p_value < 0.01,
    }


def compute_all_pairwise(
    method_preds: dict[str, list[float]],
    actuals: list[bool],
    reference_method: str = "simple_average",
) -> dict:
    """
    Compute bootstrap tests for all methods vs a reference method.

    Args:
        method_preds: Dict mapping method_name -> list of predictions (0-1 scale).
        actuals: Actual outcomes.
        reference_method: Method to compare against.

    Returns:
        Dict mapping method_name -> test results.
    """
    ref_preds = method_preds.get(reference_method)
    if ref_preds is None:
        return {}

    results = {}
    for method, preds in method_preds.items():
        if method == reference_method:
            continue
        bootstrap = paired_bootstrap_test(preds, ref_preds, actuals)
        dm = diebold_mariano_test(preds, ref_preds, actuals)
        results[method] = {
            "bootstrap": bootstrap,
            "diebold_mariano": dm,
        }
    return results


def significance_star(p_value: float) -> str:
    """Return significance marker for LaTeX tables."""
    if p_value < 0.01:
        return "**"
    elif p_value < 0.05:
        return "*"
    return ""


def format_significance_table(
    method_scores: dict[str, float],
    pairwise_results: dict[str, dict],
    reference_method: str = "simple_average",
) -> str:
    """
    Format a significance comparison table for printing.

    Args:
        method_scores: Dict mapping method_name -> Brier Score.
        pairwise_results: Output from compute_all_pairwise().
        reference_method: The reference method.
    """
    lines = []
    lines.append(f"{'Method':<25s} {'Brier':>8s} {'Diff vs ref':>12s} {'p-value':>10s} {'Sig':>5s}")
    lines.append(f"{'-'*25} {'-'*8} {'-'*12} {'-'*10} {'-'*5}")

    ref_score = method_scores.get(reference_method, 0)
    lines.append(f"{reference_method:<25s} {ref_score:>8.4f} {'(ref)':>12s} {'':>10s} {'':>5s}")

    for method, result in sorted(pairwise_results.items(), key=lambda x: method_scores.get(x[0], 0)):
        score = method_scores.get(method, 0)
        diff = result["bootstrap"]["observed_diff"]
        p_val = result["bootstrap"]["p_value"]
        star = significance_star(p_val)
        lines.append(f"{method:<25s} {score:>8.4f} {diff:>+12.4f} {p_val:>10.4f} {star:>5s}")

    return "\n".join(lines)
