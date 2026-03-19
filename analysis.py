"""
Analysis and visualization for aggregation mechanism experiments.

Generates all figures and tables needed for the paper:
  - Figure 1: Brier Score comparison across mechanisms (bar chart)
  - Figure 2: Calibration (reliability) diagrams
  - Figure 3: Reputation convergence over time
  - Figure 4: LMSR market price evolution
  - Figure 5: BTS score vs actual Brier Score (rank correlation)
  - Table 1: Main results table
  - Table 2: Per-category breakdown

Usage:
    python analysis.py                   # Generate from experiment results
    python analysis.py --results-dir data/results
"""

import json
import math
import os
import statistics
from collections import defaultdict

# Use matplotlib with non-interactive backend for paper figures
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


FIGURES_DIR = os.path.join(os.path.dirname(__file__), "figures")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "data", "results")

MECHANISM_LABELS = {
    "no_debate (R1)": "No Debate (R1 Avg)",
    "simple_average": "Simple Average",
    "extremized": "Extremized Average",
    "reputation_weighted": "Reputation-Weighted (M1)",
    "lmsr_market": "LMSR Market (M2)",
    "peer_prediction": "Peer Prediction (M3)",
    "hybrid": "Hybrid (M4)",
    "market_price": "Market Price",
}

COLORS = {
    "no_debate (R1)": "#9e9e9e",
    "simple_average": "#42a5f5",
    "extremized": "#66bb6a",
    "reputation_weighted": "#ffa726",
    "lmsr_market": "#ef5350",
    "peer_prediction": "#ab47bc",
    "hybrid": "#26c6da",
    "market_price": "#78909c",
}


def load_summary(results_dir: str = RESULTS_DIR) -> dict:
    """Load experiment summary."""
    path = os.path.join(results_dir, "experiment_summary.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_results(results_dir: str = RESULTS_DIR) -> list[dict]:
    """Load all individual question results."""
    results = []
    for fname in sorted(os.listdir(results_dir)):
        if fname.startswith("q") or fname.startswith("manifold_"):
            path = os.path.join(results_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                results.append(json.load(f))
    return results


# ── Figure 1: Brier Score Bar Chart ───────────────────────────────────────


def plot_brier_comparison(summary: dict, save_path: str | None = None):
    """Bar chart comparing Brier Scores across all mechanisms."""
    scores = summary["scores"]
    methods = list(MECHANISM_LABELS.keys())
    methods = [m for m in methods if m in scores]

    briers = [scores[m]["brier"] for m in methods]
    labels = [MECHANISM_LABELS[m] for m in methods]
    colors = [COLORS[m] for m in methods]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(range(len(methods)), briers, color=colors, edgecolor="white", linewidth=0.5)

    # Add value labels on bars
    for bar, val in zip(bars, briers):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                f"{val:.4f}", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(range(len(methods)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=10)
    ax.set_ylabel("Brier Score (lower is better)", fontsize=12)
    ax.set_title("Aggregation Mechanism Comparison: Brier Score", fontsize=14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Highlight best mechanism
    best_idx = briers.index(min(briers))
    bars[best_idx].set_edgecolor("gold")
    bars[best_idx].set_linewidth(2)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close()


# ── Figure 2: Calibration Diagrams ───────────────────────────────────────


def plot_calibration(summary: dict, results: list[dict], save_path: str | None = None):
    """Reliability diagrams for key mechanisms."""
    methods_to_plot = ["simple_average", "reputation_weighted", "lmsr_market", "hybrid", "market_price"]

    fig, axes = plt.subplots(1, len(methods_to_plot), figsize=(4 * len(methods_to_plot), 4), sharey=True)

    for ax, method in zip(axes, methods_to_plot):
        preds = []
        actuals = []

        for i, q in enumerate(summary.get("per_question", [])):
            actual = q["actual"]
            if method == "market_price":
                prob = q.get("market_price", 0.5)
            else:
                prob = q.get("mechanism_predictions", {}).get(method, 50) / 100.0
            preds.append(prob)
            actuals.append(1.0 if actual else 0.0)

        if not preds:
            continue

        # Bin predictions
        n_bins = 10
        bins = defaultdict(lambda: {"preds": [], "actuals": []})
        for p, a in zip(preds, actuals):
            bin_idx = min(int(p * n_bins), n_bins - 1)
            bins[bin_idx]["preds"].append(p)
            bins[bin_idx]["actuals"].append(a)

        bin_centers = []
        bin_actuals = []
        bin_sizes = []

        for i in range(n_bins):
            if bins[i]["preds"]:
                bin_centers.append(np.mean(bins[i]["preds"]))
                bin_actuals.append(np.mean(bins[i]["actuals"]))
                bin_sizes.append(len(bins[i]["preds"]))

        # Plot
        ax.plot([0, 1], [0, 1], "k--", alpha=0.3, label="Perfect calibration")
        if bin_centers:
            ax.scatter(bin_centers, bin_actuals,
                      s=[s * 20 for s in bin_sizes],
                      c=COLORS.get(method, "#333"),
                      alpha=0.7, edgecolors="white")
            ax.plot(bin_centers, bin_actuals, c=COLORS.get(method, "#333"), alpha=0.5)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Predicted Probability", fontsize=9)
        ax.set_title(MECHANISM_LABELS.get(method, method), fontsize=10)
        ax.set_aspect("equal")

    axes[0].set_ylabel("Observed Frequency", fontsize=9)
    fig.suptitle("Calibration Diagrams", fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close()


# ── Figure 3: Reputation Convergence ─────────────────────────────────────


def plot_reputation_convergence(results: list[dict], save_path: str | None = None):
    """Plot agent reputation scores over time (across questions)."""
    # Extract reputation snapshots from each result
    rep_history = defaultdict(list)
    question_labels = []

    for i, r in enumerate(results):
        snapshot = r.get("reputation_snapshot", {})
        question_labels.append(f"Q{i+1}")
        for agent_name, info in snapshot.items():
            rep_history[agent_name].append(info.get("reputation", 1.0))

    if not rep_history:
        print("No reputation data found in results.")
        return

    fig, ax = plt.subplots(figsize=(14, 6))

    for agent_name, reps in rep_history.items():
        ax.plot(range(len(reps)), reps, marker="o", markersize=3, label=agent_name, alpha=0.7)

    ax.set_xlabel("Question Number", fontsize=12)
    ax.set_ylabel("Reputation Score", fontsize=12)
    ax.set_title("Agent Reputation Convergence Over Time", fontsize=14)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close()


# ── Figure 4: LMSR Price Evolution ──────────────────────────────────────


def plot_lmsr_trades(results: list[dict], question_idx: int = 0, save_path: str | None = None):
    """Plot LMSR market price evolution for a single question."""
    if question_idx >= len(results):
        print(f"Question index {question_idx} out of range.")
        return

    r = results[question_idx]
    lmsr_details = (r.get("aggregation_mechanisms", {})
                     .get("lmsr_market", {})
                     .get("details", {}))
    trade_history = lmsr_details.get("trade_history", [])

    if not trade_history:
        print("No LMSR trade history found.")
        return

    prices = [trade_history[0].get("price_before", 50)]
    labels = ["Initial"]

    for trade in trade_history:
        prices.append(trade["price_after"])
        labels.append(trade["agent_name"])

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(range(len(prices)), prices, "b-o", markersize=6, linewidth=2)

    # Annotate each trade
    for i, (price, label) in enumerate(zip(prices, labels)):
        if i > 0:
            action = trade_history[i-1]["action"]
            color = "green" if action == "buy_yes" else "red"
            ax.annotate(label, (i, price), textcoords="offset points",
                       xytext=(0, 10), ha="center", fontsize=7,
                       rotation=45, color=color)

    # Show actual resolution
    actual = r.get("actual")
    if actual is not None:
        actual_line = 100.0 if actual else 0.0
        ax.axhline(y=actual_line, color="gold", linestyle="--", alpha=0.5,
                   label=f"Actual: {'YES' if actual else 'NO'}")

    ax.set_xlabel("Trade Sequence", fontsize=12)
    ax.set_ylabel("Market Price (%)", fontsize=12)
    ax.set_title(f"LMSR Market Price Evolution\n{r.get('question', '')[:80]}", fontsize=12)
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close()


# ── Figure 5: BTS Validation ────────────────────────────────────────────


def plot_bts_validation(summary: dict, save_path: str | None = None):
    """Scatter plot: BTS ranking vs actual Brier ranking of agents."""
    reputation = summary.get("reputation_final", {})
    if not reputation:
        print("No reputation data found.")
        return

    # Sort by reputation (proxy for actual Brier performance)
    sorted_by_brier = sorted(reputation.items(),
                             key=lambda x: x[1].get("avg_brier", 1), reverse=False)
    brier_ranks = {name: i+1 for i, (name, _) in enumerate(sorted_by_brier)}

    # Sort by reputation score (informed by BTS over time)
    sorted_by_rep = sorted(reputation.items(),
                           key=lambda x: x[1]["reputation"], reverse=True)
    rep_ranks = {name: i+1 for i, (name, _) in enumerate(sorted_by_rep)}

    names = list(brier_ranks.keys())
    x = [brier_ranks[n] for n in names]
    y = [rep_ranks[n] for n in names]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(x, y, s=100, c="#ab47bc", edgecolors="white", linewidth=1, zorder=5)

    for name, xi, yi in zip(names, x, y):
        ax.annotate(name, (xi, yi), textcoords="offset points",
                   xytext=(5, 5), fontsize=8)

    # Perfect correlation line
    n = len(names)
    ax.plot([1, n], [1, n], "k--", alpha=0.3, label="Perfect rank agreement")

    # Spearman correlation
    from scipy.stats import spearmanr
    try:
        corr, pval = spearmanr(x, y)
        ax.text(0.05, 0.95, f"Spearman ρ = {corr:.3f}\np = {pval:.4f}",
                transform=ax.transAxes, fontsize=11,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    except ImportError:
        # scipy not available, compute manually
        d_sq = sum((xi - yi) ** 2 for xi, yi in zip(x, y))
        corr = 1 - (6 * d_sq) / (n * (n**2 - 1))
        ax.text(0.05, 0.95, f"Spearman ρ = {corr:.3f}",
                transform=ax.transAxes, fontsize=11,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    ax.set_xlabel("Rank by Actual Brier Score (best → worst)", fontsize=12)
    ax.set_ylabel("Rank by Reputation Score (best → worst)", fontsize=12)
    ax.set_title("BTS-Informed Reputation vs Actual Performance", fontsize=14)
    ax.set_xlim(0.5, n + 0.5)
    ax.set_ylim(0.5, n + 0.5)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.legend()

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close()


# ── Table: Per-Category Breakdown ────────────────────────────────────────


def print_category_table(summary: dict):
    """Print per-category Brier Score breakdown."""
    per_q = summary.get("per_question", [])
    if not per_q:
        print("No per-question data.")
        return

    # Group by category (we need to load questions.json for category info)
    questions_path = os.path.join(os.path.dirname(__file__), "data", "questions.json")
    with open(questions_path, "r", encoding="utf-8") as f:
        all_questions = json.load(f)
    id_to_cat = {q["id"]: q.get("category", "unknown") for q in all_questions}

    categories = defaultdict(lambda: defaultdict(list))
    methods = ["simple_average", "extremized", "reputation_weighted",
               "lmsr_market", "peer_prediction", "hybrid"]

    for q in per_q:
        cat = id_to_cat.get(q["id"], "unknown")
        actual = 1.0 if q["actual"] else 0.0

        for method in methods:
            prob = q.get("mechanism_predictions", {}).get(method, 50) / 100.0
            brier = (prob - actual) ** 2
            categories[cat][method].append(brier)

        # Market price
        mp = q.get("market_price", 0.5)
        categories[cat]["market_price"].append((mp - actual) ** 2)

    # Print table
    all_methods = methods + ["market_price"]
    header = f"{'Category':<15s}"
    for m in all_methods:
        label = m[:12]
        header += f" {label:>12s}"
    print(header)
    print("-" * len(header))

    for cat in sorted(categories.keys()):
        row = f"{cat:<15s}"
        for m in all_methods:
            vals = categories[cat][m]
            avg = statistics.mean(vals) if vals else float("nan")
            row += f" {avg:>12.4f}"
        row += f"  (n={len(categories[cat][methods[0]])})"
        print(row)


# ── LaTeX Table Generation ───────────────────────────────────────────────


def generate_latex_table(summary: dict, save_path: str | None = None):
    """Generate LaTeX table for the paper."""
    scores = summary["scores"]
    methods = list(MECHANISM_LABELS.keys())
    methods = [m for m in methods if m in scores]

    lines = [
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{Aggregation Mechanism Performance Comparison}",
        r"\label{tab:main_results}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Method & Brier Score $\downarrow$ & Log Score $\uparrow$ & ECE $\downarrow$ \\",
        r"\midrule",
    ]

    best_brier = min(scores[m]["brier"] for m in methods)

    for m in methods:
        s = scores[m]
        label = MECHANISM_LABELS[m]
        brier_str = f"{s['brier']:.4f}"
        log_str = f"{s['log']:.4f}"
        ece_str = f"{s['ece']:.4f}"

        if s["brier"] == best_brier:
            brier_str = r"\textbf{" + brier_str + "}"

        lines.append(f"  {label} & {brier_str} & {log_str} & {ece_str} \\\\")

        # Add midrule after baselines
        if m == "extremized":
            lines.append(r"\midrule")
        elif m == "hybrid":
            lines.append(r"\midrule")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    latex = "\n".join(lines)

    if save_path:
        with open(save_path, "w") as f:
            f.write(latex)
        print(f"Saved LaTeX table: {save_path}")
    else:
        print(latex)

    return latex


# ── Main ─────────────────────────────────────────────────────────────────


def generate_all(results_dir: str = RESULTS_DIR):
    """Generate all figures and tables."""
    os.makedirs(FIGURES_DIR, exist_ok=True)

    print("Loading experiment results...")
    summary = load_summary(results_dir)
    results = load_all_results(results_dir)

    print(f"Loaded summary with {summary.get('num_questions', 0)} questions")
    print(f"Loaded {len(results)} individual results")

    # Generate figures
    print("\nGenerating figures...")

    plot_brier_comparison(
        summary,
        save_path=os.path.join(FIGURES_DIR, "fig1_brier_comparison.png"),
    )

    plot_calibration(
        summary, results,
        save_path=os.path.join(FIGURES_DIR, "fig2_calibration.png"),
    )

    if results:
        plot_reputation_convergence(
            results,
            save_path=os.path.join(FIGURES_DIR, "fig3_reputation_convergence.png"),
        )

        plot_lmsr_trades(
            results, question_idx=0,
            save_path=os.path.join(FIGURES_DIR, "fig4_lmsr_trades.png"),
        )

    plot_bts_validation(
        summary,
        save_path=os.path.join(FIGURES_DIR, "fig5_bts_validation.png"),
    )

    # Generate tables
    print("\nGenerating tables...")
    generate_latex_table(
        summary,
        save_path=os.path.join(FIGURES_DIR, "table1_main_results.tex"),
    )

    print("\nPer-category breakdown:")
    print_category_table(summary)

    print(f"\nAll figures saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    import sys
    results_dir = sys.argv[1] if len(sys.argv) > 1 else RESULTS_DIR
    generate_all(results_dir)
