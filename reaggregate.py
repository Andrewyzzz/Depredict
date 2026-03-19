"""
Re-aggregate existing results with the fixed LMSR (median initial price).
No new API calls needed - reuses Round 3 predictions from saved results.

Also generates reputation convergence plot for the paper.
"""

import json
import math
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aggregator import (
    ReputationTracker,
    aggregate_simple_average,
    aggregate_median,
    aggregate_trimmed_mean,
    aggregate_logit_average,
    aggregate_extremized,
    aggregate_reputation_weighted,
    aggregate_lmsr,
    aggregate_peer_prediction,
    aggregate_hybrid,
    get_oracle_single_agent,
)
from config import (
    AGENT_PERSONAS, RESULTS_DIR, REPUTATION_DECAY, LMSR_LIQUIDITY,
    EXTREMIZATION_D, HYBRID_LAMBDA_MARKET, HYBRID_LAMBDA_REPUTATION,
    HYBRID_LAMBDA_BTS,
)


MECHANISM_NAMES = [
    "simple_average", "median", "trimmed_mean", "logit_average",
    "extremized", "reputation_weighted",
    "lmsr_market", "peer_prediction", "hybrid",
]


def brier_score(pred, actual):
    outcome = 1.0 if actual else 0.0
    return (pred - outcome) ** 2


def log_score(pred, actual):
    eps = 1e-10
    return math.log(max(pred, eps)) if actual else math.log(max(1 - pred, eps))


def main():
    # Load all individual results
    active_ids = [
        "q4", "q9", "q10",
        "manifold_JRzyleybZU", "manifold_Tx9a1HiZ66", "manifold_F5jTYCQhiT",
        "manifold_2xMTqHjaYG", "manifold_fFmTjkm8yz", "manifold_KLC57yIaQ6",
        "manifold_iqSm3mgj7Q", "manifold_rEHv8m4j5V", "manifold_zCViv6JFc3",
        "manifold_Qnpn9GHKM4", "manifold_ogBggSkiZv", "manifold_uofbKIvdBh",
        "manifold_xe44ohr8fo", "manifold_ZI0NplgyCl", "manifold_dPsgLStNtI",
    ]

    # Load results
    results = []
    for qid in active_ids:
        path = os.path.join(RESULTS_DIR, f"{qid}.json")
        if os.path.exists(path):
            with open(path) as f:
                results.append(json.load(f))

    print(f"Loaded {len(results)} active results")

    # Setup reputation tracker
    agent_names = [p["name"] for p in AGENT_PERSONAS]
    rep_tracker = ReputationTracker(agent_names, decay=REPUTATION_DECAY)

    # Re-aggregate each question
    all_preds = {m: [] for m in MECHANISM_NAMES}
    no_debate_preds = []
    market_preds = []
    actuals = []

    # Track reputation snapshots for convergence plot
    reputation_history = []  # list of dicts: {agent_name: reputation} per question

    for r in results:
        round3 = r.get("rounds", {}).get("round3", [])
        meta_preds = r.get("meta_predictions", {})
        actual = r["actual"]
        actuals.append(actual)

        # R1 average
        r1_avg = r.get("round1_average")
        no_debate_preds.append(r1_avg / 100.0 if r1_avg else 0.5)

        # Market price
        mp = r.get("market_price", 0.5)
        market_preds.append(mp)

        # Get reputation weights
        rep_weights = rep_tracker.get_weights()

        # Re-aggregate with fixed mechanisms
        agg = {
            "simple_average": aggregate_simple_average(round3),
            "median": aggregate_median(round3),
            "trimmed_mean": aggregate_trimmed_mean(round3),
            "logit_average": aggregate_logit_average(round3),
            "extremized": aggregate_extremized(round3, d=EXTREMIZATION_D),
            "reputation_weighted": aggregate_reputation_weighted(round3, rep_weights),
            "lmsr_market": aggregate_lmsr(
                round3,
                budgets={n: 100.0 * (1 + w) for n, w in rep_weights.items()},
                liquidity=LMSR_LIQUIDITY,
            ),
            "peer_prediction": aggregate_peer_prediction(round3, meta_preds or None),
            "hybrid": aggregate_hybrid(
                round3, rep_weights, meta_preds or None,
                lmsr_liquidity=LMSR_LIQUIDITY,
                lambda_market=HYBRID_LAMBDA_MARKET,
                lambda_reputation=HYBRID_LAMBDA_REPUTATION,
                lambda_bts=HYBRID_LAMBDA_BTS,
            ),
        }

        for method in MECHANISM_NAMES:
            prob = agg[method].get("probability")
            all_preds[method].append(prob / 100.0 if prob is not None else 0.5)

        # Update reputation
        for agent_result in round3:
            name = agent_result.get("agent_name")
            prob = agent_result.get("probability")
            if name and prob is not None:
                bs = brier_score(prob / 100.0, actual)
                rep_tracker.update(name, bs)

        # Save snapshot after this question
        snap = rep_tracker.snapshot()
        reputation_history.append({name: info["reputation"] for name, info in snap.items()})

    # ── Print Results ──────────────────────────────────────────────────

    print(f"\n{'='*70}")
    print(f"Re-Aggregated Results ({len(results)} Active Questions)")
    print(f"{'='*70}")
    print(f"  {'Method':<25s} {'Brier ↓':>10s} {'Log Score ↑':>12s}")
    print(f"  {'-'*25} {'-'*10} {'-'*12}")

    all_scores = {}

    # No debate
    briers = [brier_score(p, a) for p, a in zip(no_debate_preds, actuals)]
    logs = [log_score(p, a) for p, a in zip(no_debate_preds, actuals)]
    all_scores["no_debate (R1)"] = {"brier": statistics.mean(briers), "log": statistics.mean(logs)}
    print(f"  {'no_debate (R1)':<25s} {statistics.mean(briers):>10.4f} {statistics.mean(logs):>12.4f}")

    for method in MECHANISM_NAMES:
        briers = [brier_score(p, a) for p, a in zip(all_preds[method], actuals)]
        logs = [log_score(p, a) for p, a in zip(all_preds[method], actuals)]
        all_scores[method] = {"brier": statistics.mean(briers), "log": statistics.mean(logs)}
        print(f"  {method:<25s} {statistics.mean(briers):>10.4f} {statistics.mean(logs):>12.4f}")

    briers = [brier_score(p, a) for p, a in zip(market_preds, actuals)]
    logs = [log_score(p, a) for p, a in zip(market_preds, actuals)]
    all_scores["market_price"] = {"brier": statistics.mean(briers), "log": statistics.mean(logs)}
    print(f"  {'market_price':<25s} {statistics.mean(briers):>10.4f} {statistics.mean(logs):>12.4f}")

    # Best
    debate_methods = {m: all_scores[m] for m in MECHANISM_NAMES}
    best = min(debate_methods, key=lambda m: debate_methods[m]["brier"])
    print(f"\n  Best: {best} (Brier: {debate_methods[best]['brier']:.4f})")

    sa_brier = all_scores["simple_average"]["brier"]
    print(f"\n  Improvements over simple average:")
    for m in MECHANISM_NAMES:
        if m != "simple_average":
            imp = (sa_brier - all_scores[m]["brier"]) / sa_brier * 100
            print(f"    {m}: {imp:+.2f}%")

    # Per-question detail for the most interesting cases
    print(f"\n{'='*70}")
    print("Per-Question Details")
    print(f"{'='*70}")

    for i, r in enumerate(results):
        actual_str = "YES" if r["actual"] else "NO"
        q = r["question"][:55]
        r1 = no_debate_preds[i] * 100
        mp_val = market_preds[i] * 100

        print(f"\n  [{actual_str}] {q}")
        print(f"    R1={r1:.0f}%  Market={mp_val:.0f}%", end="")
        for method in MECHANISM_NAMES:
            val = all_preds[method][i] * 100
            print(f"  {method[:6]}={val:.0f}%", end="")
        print()

    # ── Reputation ─────────────────────────────────────────────────────

    print(f"\n{'='*70}")
    print("Final Agent Reputations")
    print(f"{'='*70}")

    AGENT_EN = {
        "乐观分析师": "Optimist", "质疑分析师": "Skeptic",
        "贝叶斯分析师": "Bayesian", "历史类比师": "Historian",
        "数据统计师": "Statistician", "情绪分析师": "Sentiment",
        "逆向投资者": "Contrarian", "基本面分析师": "Fundamentalist",
        "风险评估师": "Risk Analyst", "综合策略师": "Synthesizer",
    }

    snap = rep_tracker.snapshot()
    sorted_agents = sorted(snap.items(), key=lambda x: x[1]["reputation"], reverse=True)
    for name, info in sorted_agents:
        en = AGENT_EN.get(name, name)
        avg_b = f"{info['avg_brier']:.4f}" if info["avg_brier"] else "N/A"
        print(f"  {en:<18s} rep={info['reputation']:.4f}  avg_brier={avg_b}")

    # ── Reputation Convergence Plot ───────────────────────────────────

    if reputation_history:
        plot_reputation_convergence(reputation_history, AGENT_EN)

    # ── Save reputation history for external use ──────────────────────

    history_path = os.path.join(RESULTS_DIR, "reputation_history.json")
    with open(history_path, "w") as f:
        json.dump(reputation_history, f, indent=2)
    print(f"\nSaved {history_path}")


FIGURES_DIR = os.path.join(os.path.dirname(__file__), "figures")


def plot_reputation_convergence(
    reputation_history: list[dict],
    agent_name_en: dict[str, str],
):
    """
    Plot reputation score trajectories over questions.

    Args:
        reputation_history: List of {agent_name: reputation} dicts, one per question.
        agent_name_en: Chinese -> English name mapping.
    """
    os.makedirs(FIGURES_DIR, exist_ok=True)

    if not reputation_history:
        print("No reputation history to plot.")
        return

    agent_names = list(reputation_history[0].keys())
    n_questions = len(reputation_history)
    x = list(range(1, n_questions + 1))

    # Color palette for 10 agents
    colors = [
        "#4caf50", "#f44336", "#2196f3", "#ff9800", "#9c27b0",
        "#00bcd4", "#e91e63", "#8bc34a", "#795548", "#607d8b",
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    for i, name in enumerate(agent_names):
        trajectory = [reputation_history[q].get(name, 1.0) for q in range(n_questions)]
        en_name = agent_name_en.get(name, name)
        ax.plot(x, trajectory, color=colors[i % len(colors)],
                linewidth=1.8, alpha=0.85, label=en_name)

    ax.set_xlabel("Question Number", fontsize=12)
    ax.set_ylabel("Reputation Score", fontsize=12)
    ax.set_title("Agent Reputation Convergence Over Questions", fontsize=14)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Add vertical line at ~30 questions if enough data
    if n_questions >= 30:
        ax.axvline(x=30, color="gray", linestyle="--", alpha=0.4, linewidth=1)
        ax.text(31, ax.get_ylim()[1] * 0.98, "convergence\nbegins",
                fontsize=8, color="gray", va="top")

    plt.tight_layout()
    output_path = os.path.join(FIGURES_DIR, "fig_reputation_convergence.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved {output_path}")
    plt.close()


if __name__ == "__main__":
    main()
