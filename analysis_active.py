"""
Re-analyze experiment results using only active questions
(where agents produced non-trivial predictions, not defaulting to 50%).
"""

import json
import math
import os
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIGURES_DIR = os.path.join(os.path.dirname(__file__), "figures")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "data", "results")

MECHANISM_LABELS = {
    "no_debate (R1)": "No Debate\n(R1 Avg)",
    "simple_average": "Simple\nAverage",
    "median": "Median",
    "trimmed_mean": "Trimmed\nMean",
    "logit_average": "Logit\nAverage",
    "extremized": "Extremized\nAverage",
    "reputation_weighted": "Reputation\nWeighted (M1)",
    "lmsr_market": "LMSR\nMarket (M2)",
    "peer_prediction": "Peer\nPrediction (M3)",
    "hybrid": "Hybrid\n(M4)",
    "market_price": "Market\nPrice",
}

COLORS = {
    "no_debate (R1)": "#9e9e9e",
    "simple_average": "#42a5f5",
    "median": "#5c6bc0",
    "trimmed_mean": "#7986cb",
    "logit_average": "#4db6ac",
    "extremized": "#66bb6a",
    "reputation_weighted": "#ffa726",
    "lmsr_market": "#ef5350",
    "peer_prediction": "#ab47bc",
    "hybrid": "#26c6da",
    "market_price": "#78909c",
}

MECHANISM_NAMES = [
    "simple_average", "median", "trimmed_mean", "logit_average",
    "extremized", "reputation_weighted",
    "lmsr_market", "peer_prediction", "hybrid",
]

# Chinese → English agent name mapping for figures
AGENT_NAME_EN = {
    "乐观分析师": "Optimist",
    "质疑分析师": "Skeptic",
    "贝叶斯分析师": "Bayesian",
    "历史类比师": "Historian",
    "数据统计师": "Statistician",
    "情绪分析师": "Sentiment",
    "逆向投资者": "Contrarian",
    "基本面分析师": "Fundamentalist",
    "风险评估师": "Risk Analyst",
    "综合策略师": "Synthesizer",
}


def brier_score(pred, actual):
    outcome = 1.0 if actual else 0.0
    return (pred - outcome) ** 2


def log_score(pred, actual):
    eps = 1e-10
    if actual:
        return math.log(max(pred, eps))
    return math.log(max(1 - pred, eps))


def ece(preds, actuals, n_bins=5):
    bins = defaultdict(lambda: {"p": [], "a": []})
    for p, a in zip(preds, actuals):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx]["p"].append(p)
        bins[idx]["a"].append(1.0 if a else 0.0)
    total = len(preds)
    if total == 0:
        return float("nan")
    return sum(
        len(b["p"]) / total * abs(np.mean(b["p"]) - np.mean(b["a"]))
        for b in bins.values() if b["p"]
    )


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)

    with open(os.path.join(RESULTS_DIR, "experiment_summary.json")) as f:
        summary = json.load(f)

    # Filter to active questions only
    active_qs = []
    for q in summary["per_question"]:
        r1 = q.get("round1_avg")
        if r1 is not None and abs(r1 - 50) > 1:
            active_qs.append(q)

    print(f"Active questions: {len(active_qs)} / {len(summary['per_question'])}")

    # ── Recompute scores for active questions only ──────────────────────

    methods_all = ["no_debate (R1)"] + MECHANISM_NAMES + ["market_price"]
    scores = {}

    for method in methods_all:
        preds = []
        actuals = []
        skip_method = False
        for q in active_qs:
            actual = q["actual"]

            if method == "no_debate (R1)":
                p = q["round1_avg"] / 100.0
            elif method == "market_price":
                p = q.get("market_price", 0.5)
            else:
                mechs = q.get("mechanism_predictions", {})
                if method not in mechs:
                    # Method not in summary data (new baseline not yet in experiment results)
                    skip_method = True
                    break
                p = mechs[method] / 100.0
            actuals.append(actual)
            preds.append(p)

        if skip_method:
            print(f"  [SKIP] {method} not found in experiment summary — re-run experiment.py to include")
            continue

        briers = [brier_score(p, a) for p, a in zip(preds, actuals)]
        logs = [log_score(p, a) for p, a in zip(preds, actuals)]
        scores[method] = {
            "brier": statistics.mean(briers),
            "log": statistics.mean(logs),
            "ece": ece(preds, actuals),
            "preds": preds,
            "actuals": actuals,
        }

    # Filter to methods actually present in scores
    methods_all = [m for m in methods_all if m in scores]

    # ── Print Table ─────────────────────────────────────────────────────

    print(f"\n{'='*70}")
    print(f"Results on {len(active_qs)} Active Questions")
    print(f"{'='*70}")
    print(f"  {'Method':<25s} {'Brier ↓':>10s} {'Log Score ↑':>12s} {'ECE ↓':>10s}")
    print(f"  {'-'*25} {'-'*10} {'-'*12} {'-'*10}")

    for method in methods_all:
        s = scores[method]
        print(f"  {method:<25s} {s['brier']:>10.4f} {s['log']:>12.4f} {s['ece']:>10.4f}")

    debate_methods = {m: scores[m] for m in MECHANISM_NAMES if m in scores}
    best = min(debate_methods, key=lambda m: debate_methods[m]["brier"])
    print(f"\n  Best mechanism: {best} (Brier: {debate_methods[best]['brier']:.4f})")

    # Improvement over simple average
    sa_brier = scores["simple_average"]["brier"]
    for m in MECHANISM_NAMES:
        if m != "simple_average" and m in scores:
            imp = (sa_brier - scores[m]["brier"]) / sa_brier * 100
            print(f"  {m} vs simple_avg: {imp:+.2f}%")

    # ── Figure 1: Brier Score Comparison ────────────────────────────────

    fig, ax = plt.subplots(figsize=(13, 6))
    methods_plot = methods_all
    briers = [scores[m]["brier"] for m in methods_plot]
    labels = [MECHANISM_LABELS[m] for m in methods_plot]
    colors = [COLORS[m] for m in methods_plot]

    bars = ax.bar(range(len(methods_plot)), briers, color=colors, edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, briers):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                f"{val:.4f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(range(len(methods_plot)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Brier Score (lower is better)", fontsize=12)
    ax.set_title(f"Aggregation Mechanism Comparison ({len(active_qs)} Active Questions)", fontsize=14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    best_idx = briers.index(min(briers))
    bars[best_idx].set_edgecolor("gold")
    bars[best_idx].set_linewidth(2.5)

    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig1_brier_comparison.png"), dpi=300, bbox_inches="tight")
    print(f"\nSaved fig1_brier_comparison.png")
    plt.close()

    # ── Figure 2: Calibration Diagrams ──────────────────────────────────

    methods_cal = ["simple_average", "reputation_weighted", "lmsr_market", "hybrid", "market_price"]
    fig, axes = plt.subplots(1, len(methods_cal), figsize=(4 * len(methods_cal), 4), sharey=True)

    for ax, method in zip(axes, methods_cal):
        preds = scores[method]["preds"]
        actuals = scores[method]["actuals"]

        n_bins = 5
        bins = defaultdict(lambda: {"p": [], "a": []})
        for p, a in zip(preds, [1.0 if a else 0.0 for a in actuals]):
            idx = min(int(p * n_bins), n_bins - 1)
            bins[idx]["p"].append(p)
            bins[idx]["a"].append(a)

        centers, obs, sizes = [], [], []
        for i in range(n_bins):
            if bins[i]["p"]:
                centers.append(np.mean(bins[i]["p"]))
                obs.append(np.mean(bins[i]["a"]))
                sizes.append(len(bins[i]["p"]))

        ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
        if centers:
            ax.scatter(centers, obs, s=[s * 30 for s in sizes],
                      c=COLORS.get(method, "#333"), alpha=0.8, edgecolors="white", zorder=5)
            ax.plot(centers, obs, c=COLORS.get(method, "#333"), alpha=0.5)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Predicted", fontsize=9)
        label = method.replace("_", " ").title()
        ax.set_title(label, fontsize=10)
        ax.set_aspect("equal")

    axes[0].set_ylabel("Observed Frequency", fontsize=9)
    fig.suptitle(f"Calibration Diagrams ({len(active_qs)} Active Questions)", fontsize=13, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig2_calibration.png"), dpi=300, bbox_inches="tight")
    print("Saved fig2_calibration.png")
    plt.close()

    # ── Figure 3: Agent Reputation ──────────────────────────────────────

    rep = summary.get("reputation_final", {})
    if rep:
        sorted_agents = sorted(rep.items(), key=lambda x: x[1]["reputation"], reverse=True)
        names = [AGENT_NAME_EN.get(a[0], a[0]) for a in sorted_agents]
        reps = [a[1]["reputation"] for a in sorted_agents]
        avg_briers = [a[1].get("avg_brier", 0) or 0 for a in sorted_agents]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Reputation bar chart
        bars = ax1.barh(range(len(names)), reps, color="#ffa726", edgecolor="white")
        ax1.set_yticks(range(len(names)))
        ax1.set_yticklabels(names, fontsize=10)
        ax1.set_xlabel("Reputation Score", fontsize=11)
        ax1.set_title("Agent Reputation (after all questions)", fontsize=12)
        ax1.invert_yaxis()
        for bar, v in zip(bars, reps):
            ax1.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
                    f"{v:.4f}", va="center", fontsize=9)

        # Avg Brier bar chart
        bars2 = ax2.barh(range(len(names)), avg_briers, color="#ef5350", edgecolor="white")
        ax2.set_yticks(range(len(names)))
        ax2.set_yticklabels(names, fontsize=10)
        ax2.set_xlabel("Average Brier Score (lower is better)", fontsize=11)
        ax2.set_title("Agent Accuracy", fontsize=12)
        ax2.invert_yaxis()
        for bar, v in zip(bars2, avg_briers):
            ax2.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height()/2,
                    f"{v:.4f}", va="center", fontsize=9)

        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, "fig3_agent_reputation.png"), dpi=300, bbox_inches="tight")
        print("Saved fig3_agent_reputation.png")
        plt.close()

    # ── Figure 4: Per-question comparison scatter ───────────────────────

    fig, ax = plt.subplots(figsize=(10, 8))

    for q in active_qs:
        actual = 1.0 if q["actual"] else 0.0
        hybrid_p = q["mechanism_predictions"].get("hybrid", 50) / 100.0
        market_p = q.get("market_price", 0.5)

        hybrid_err = abs(hybrid_p - actual)
        market_err = abs(market_p - actual)

        color = "green" if hybrid_err < market_err else "red" if hybrid_err > market_err else "gray"
        ax.scatter(market_err, hybrid_err, c=color, s=60, alpha=0.7, edgecolors="white", zorder=5)

    ax.plot([0, 1], [0, 1], "k--", alpha=0.3, label="Equal performance")
    ax.set_xlabel("Market Price Absolute Error", fontsize=12)
    ax.set_ylabel("Hybrid (M4) Absolute Error", fontsize=12)
    ax.set_title("Per-Question: Hybrid vs Market Price", fontsize=14)
    ax.text(0.7, 0.1, "Hybrid better", fontsize=10, color="green", transform=ax.transAxes)
    ax.text(0.1, 0.9, "Market better", fontsize=10, color="red", transform=ax.transAxes)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal")

    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig4_hybrid_vs_market.png"), dpi=300, bbox_inches="tight")
    print("Saved fig4_hybrid_vs_market.png")
    plt.close()

    # ── Figure 5: Prediction shift (R1 → R3) ───────────────────────────

    fig, ax = plt.subplots(figsize=(12, 6))

    q_labels = [q["question"][:35] + "..." for q in active_qs]
    r1_vals = [q["round1_avg"] for q in active_qs]
    hybrid_vals = [q["mechanism_predictions"].get("hybrid", 50) for q in active_qs]
    market_vals = [q.get("market_price", 0.5) * 100 for q in active_qs]
    actual_vals = [100 if q["actual"] else 0 for q in active_qs]

    x = np.arange(len(active_qs))
    width = 0.2

    ax.bar(x - 1.5*width, r1_vals, width, label="No Debate (R1)", color="#9e9e9e", alpha=0.8)
    ax.bar(x - 0.5*width, hybrid_vals, width, label="Hybrid (M4)", color="#26c6da", alpha=0.8)
    ax.bar(x + 0.5*width, market_vals, width, label="Market Price", color="#78909c", alpha=0.8)
    ax.scatter(x + 1.5*width, actual_vals, marker="*", s=100, c="gold", zorder=5, label="Actual")

    ax.set_xticks(x)
    ax.set_xticklabels(q_labels, rotation=70, ha="right", fontsize=7)
    ax.set_ylabel("Probability (%)", fontsize=11)
    ax.set_title("Prediction Comparison Across Questions", fontsize=13)
    ax.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig5_prediction_comparison.png"), dpi=300, bbox_inches="tight")
    print("Saved fig5_prediction_comparison.png")
    plt.close()

    # ── Figure 6: Disagreement vs. Improvement Scatter ────────────────

    fig, ax = plt.subplots(figsize=(8, 6))

    disagreements = []
    improvements = []
    for q in active_qs:
        mechs = q.get("mechanism_predictions", {})
        # Compute agent disagreement (std of available mechanism predictions as proxy)
        sa_p = mechs.get("simple_average", 50) / 100.0
        hybrid_p = mechs.get("hybrid", 50) / 100.0
        actual = 1.0 if q["actual"] else 0.0

        sa_bs = (sa_p - actual) ** 2
        hybrid_bs = (hybrid_p - actual) ** 2
        improvement = sa_bs - hybrid_bs  # positive = hybrid better

        # Estimate disagreement from spread of mechanism predictions
        all_mech_vals = [mechs.get(m, 50) / 100.0 for m in MECHANISM_NAMES if m in mechs]
        if len(all_mech_vals) > 1:
            disagreement = float(np.std(all_mech_vals))
        else:
            disagreement = 0.0

        disagreements.append(disagreement)
        improvements.append(improvement)

    colors_scatter = ["green" if imp > 0 else "red" for imp in improvements]
    ax.scatter(disagreements, improvements, c=colors_scatter, s=60, alpha=0.7, edgecolors="white")
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Agent Disagreement (Std Dev)", fontsize=12)
    ax.set_ylabel("Brier Score Improvement (Hybrid vs Simple Avg)", fontsize=12)
    ax.set_title("Mechanism Design Benefit vs Agent Disagreement", fontsize=13)
    ax.text(0.95, 0.95, "Hybrid better", transform=ax.transAxes, ha="right", va="top", color="green", fontsize=10)
    ax.text(0.95, 0.05, "Simple Avg better", transform=ax.transAxes, ha="right", va="bottom", color="red", fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig6_disagreement_improvement.png"), dpi=300, bbox_inches="tight")
    print("Saved fig6_disagreement_improvement.png")
    plt.close()

    # ── Statistical Significance Testing ───────────────────────────────

    print(f"\n{'='*70}")
    print("Statistical Significance (vs Simple Average)")
    print(f"{'='*70}")

    try:
        from significance import compute_all_pairwise, format_significance_table, significance_star

        method_preds_01 = {}
        for method in methods_all:
            method_preds_01[method] = scores[method]["preds"]

        all_actuals = scores["simple_average"]["actuals"]
        pairwise = compute_all_pairwise(method_preds_01, all_actuals, reference_method="simple_average")

        method_brier_scores = {m: scores[m]["brier"] for m in methods_all}
        table_str = format_significance_table(method_brier_scores, pairwise, "simple_average")
        print(table_str)

        # Store significance stars for LaTeX table
        sig_stars = {}
        for method, result in pairwise.items():
            sig_stars[method] = significance_star(result["bootstrap"]["p_value"])

    except ImportError:
        print("  (significance.py not found or scipy missing, skipping)")
        sig_stars = {}

    # ── Save updated summary with active-only scores ────────────────────

    active_summary = {
        "num_active_questions": len(active_qs),
        "num_total_questions": len(summary["per_question"]),
        "scores_active_only": {
            method: {
                "brier": round(scores[method]["brier"], 6),
                "log": round(scores[method]["log"], 6),
                "ece": round(scores[method]["ece"], 6),
            }
            for method in methods_all
        },
        "best_mechanism": best,
    }
    with open(os.path.join(RESULTS_DIR, "active_summary.json"), "w") as f:
        json.dump(active_summary, f, indent=2)
    print(f"\nSaved active_summary.json")

    # ── LaTeX Table (with significance stars) ──────────────────────────

    print(f"\n{'='*70}")
    print("LaTeX Table")
    print(f"{'='*70}")

    latex_labels = {
        "no_debate (R1)": "No Debate (R1 Avg)",
        "simple_average": "Simple Average",
        "median": "Median",
        "trimmed_mean": "Trimmed Mean",
        "logit_average": "Logit Average",
        "extremized": "Extremized Average",
        "reputation_weighted": "Reputation-Weighted (M1)",
        "lmsr_market": "LMSR Market (M2)",
        "peer_prediction": "Peer Prediction (M3)",
        "hybrid": "Hybrid (M4)",
        "market_price": "Market Price (Reference)",
    }

    best_brier = min(scores[m]["brier"] for m in methods_all)
    best_ece = min(scores[m]["ece"] for m in methods_all)

    lines = []
    for method in methods_all:
        s = scores[method]
        label = latex_labels.get(method, method)
        b = f"{s['brier']:.4f}"
        l = f"{s['log']:.4f}"
        e = f"{s['ece']:.4f}"
        star = sig_stars.get(method, "")
        if s["brier"] == best_brier:
            b = r"\textbf{" + b + "}"
        if s["ece"] == best_ece:
            e = r"\textbf{" + e + "}"
        if star:
            b = b + f"$^{{{star}}}$"
        lines.append(f"  {label} & {b} & {l} & {e} \\\\")

    latex = "\n".join(lines)
    print(latex)

    with open(os.path.join(FIGURES_DIR, "table1_main_results.tex"), "w") as f:
        f.write(latex)
    print(f"\nSaved table1_main_results.tex")


if __name__ == "__main__":
    main()
