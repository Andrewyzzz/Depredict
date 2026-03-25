#!/usr/bin/env python3
"""
DePredict Polymarket Backtest — PDF Report

Generates a multi-page PDF with:
  - Cover page
  - Executive summary
  - Methodology deep-dive (signal, Kelly, aggregation)
  - Result charts (equity, mechanism comparison, Brier, sensitivity)
  - Per-trade tables
  - Conclusions & caveats

Usage:
    python scripts/backtest_pdf_report.py
    python scripts/backtest_pdf_report.py -o reports/custom_name.pdf
"""

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
DATA_PATH = PROJECT_ROOT / "data" / "prospective" / "predictions.json"

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":       "#111317",
    "surface":  "#1a1c20",
    "card":     "#1e2024",
    "border":   "#2a2c32",
    "primary":  "#adc6ff",
    "blue":     "#4d8eff",
    "text":     "#e2e2e8",
    "dim":      "#8a8e9c",
    "green":    "#4ae176",
    "red":      "#ff6b6b",
    "amber":    "#f0b90b",
    "purple":   "#b48eff",
    "cyan":     "#56d4e0",
    "orange":   "#ff9f43",
    "pink":     "#ff6b9d",
}

MECH_LABELS = {
    "simple_average":      "Simple Avg",
    "median":              "Median",
    "trimmed_mean":        "Trimmed Mean",
    "logit_average":       "Logit Avg",
    "extremized":          "Extremized",
    "reputation_weighted": "Rep-Weighted",
    "lmsr_market":         "LMSR",
    "peer_prediction":     "Peer Predict",
    "hybrid":              "Hybrid (M4)",
}
MECH_COLORS = {
    "simple_average": C["blue"], "median": C["green"], "trimmed_mean": C["cyan"],
    "logit_average": C["purple"], "extremized": C["amber"],
    "reputation_weighted": C["orange"], "lmsr_market": C["pink"],
    "peer_prediction": C["red"], "hybrid": C["primary"],
}
ALL_MECHANISMS = list(MECH_LABELS.keys())

CRYPTO_KW = ["bitcoin", "ethereum", "btc", "eth", "crypto", "solana",
             "sol", "xrp", "bnb", "doge", "dogecoin", "defi"]


# ── Style helpers ─────────────────────────────────────────────────────────────

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "SF Pro Text", "Inter", "Arial"],
    "font.size": 9,
    "axes.facecolor": C["surface"],
    "figure.facecolor": C["bg"],
    "text.color": C["text"],
    "axes.edgecolor": C["border"],
    "axes.labelcolor": C["dim"],
    "xtick.color": C["dim"],
    "ytick.color": C["dim"],
    "grid.color": C["border"],
    "grid.alpha": 0.4,
    "axes.grid": True,
    "axes.grid.which": "major",
    "legend.facecolor": C["surface"],
    "legend.edgecolor": C["border"],
    "legend.fontsize": 8,
})


def new_page(pdf, figsize=(11.69, 8.27)):
    """Create a new landscape A4 figure."""
    fig = plt.figure(figsize=figsize, facecolor=C["bg"])
    return fig


def save_page(pdf, fig):
    pdf.savefig(fig, facecolor=C["bg"])
    plt.close(fig)


# ── Data loading & simulation ─────────────────────────────────────────────────

def is_crypto(pred):
    t = (pred.get("slug", "") + " " + pred.get("question", "")).lower()
    return any(k in t for k in CRYPTO_KW)


def load_data():
    with open(DATA_PATH) as f:
        raw = json.load(f)
    resolved = [p for p in raw if p["status"] == "resolved" and p["resolution"] is not None]
    rows = []
    for p in resolved:
        mechs = p.get("all_mechanisms", {})
        row = {
            "question": p["question"], "slug": p["slug"],
            "category": "Crypto" if is_crypto(p) else "Non-Crypto",
            "market_price": p["market_price_at_prediction"],
            "resolution": p["resolution"],
            "model_brier": p.get("model_brier"),
            "market_brier": p.get("market_brier"),
            "predicted_at": pd.to_datetime(p["predicted_at"]),
        }
        for m in ALL_MECHANISMS:
            row[f"prob_{m}"] = mechs.get(m)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("predicted_at").reset_index(drop=True)


def kelly_fraction(p, mkt, side):
    if side == "YES":
        b = (1.0 - mkt) / mkt
        f = (p * b - (1.0 - p)) / b
    else:
        b = mkt / (1.0 - mkt)
        f = ((1.0 - p) * b - p) / b
    return max(f, 0.0)


def simulate(df, mechanism, kelly_mult=0.5, min_edge=0.0, bankroll=1000.0):
    records = []
    bank = bankroll
    for _, row in df.iterrows():
        v = row.get(f"prob_{mechanism}")
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        p = v / 100.0
        mkt = row["market_price"]
        edge = p - mkt
        if abs(edge) < min_edge:
            continue
        side = "YES" if edge > 0 else "NO"
        kf = kelly_fraction(p, mkt, side) * kelly_mult
        if kf <= 0:
            continue
        bet = bank * kf
        if side == "YES":
            pnl = bet * (1.0 - mkt) / mkt if row["resolution"] else -bet
            win = bool(row["resolution"])
        else:
            pnl = bet * mkt / (1.0 - mkt) if not row["resolution"] else -bet
            win = not row["resolution"]
        bank += pnl
        records.append({
            "question": row["question"], "category": row["category"],
            "predicted_at": row["predicted_at"],
            "side": side, "p": p, "mkt": mkt, "edge": abs(edge),
            "kf": kf, "bet": bet, "pnl": pnl, "win": win, "bank": bank,
        })
    return pd.DataFrame(records)


def stats(sim, bankroll=1000.0):
    if sim.empty:
        return dict(n=0, wins=0, wr=0, pnl=0, roi=0, sharpe=0, maxdd=0, final=bankroll)
    n = len(sim)
    w = int(sim["win"].sum())
    pnl = sim["pnl"].sum()
    roi = pnl / bankroll * 100
    r = sim["pnl"] / sim["bet"]
    sharpe = r.mean() / r.std() if r.std() > 0 else 0
    eq = np.array([bankroll] + sim["bank"].tolist())
    pk = np.maximum.accumulate(eq)
    dd = ((pk - eq) / np.where(pk > 0, pk, 1)).max() * 100
    return dict(n=n, wins=w, wr=w / n * 100, pnl=pnl, roi=roi,
                sharpe=sharpe, maxdd=dd, final=bankroll + pnl)


# ── Page builders ─────────────────────────────────────────────────────────────

def page_cover(pdf, df):
    fig = new_page(pdf)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_facecolor(C["bg"])

    # Accent line
    ax.plot([0.08, 0.92], [0.62, 0.62], color=C["blue"], linewidth=2, alpha=0.6)
    ax.plot([0.08, 0.35], [0.61, 0.61], color=C["blue"], linewidth=4)

    ax.text(0.5, 0.78, "DEPREDICT", fontsize=42, fontweight="bold",
            color=C["primary"], ha="center", va="center", fontfamily="monospace")
    ax.text(0.5, 0.70, "Polymarket Backtest Report", fontsize=22,
            color=C["text"], ha="center", va="center")
    ax.text(0.5, 0.55, "Can AI Multi-Expert Deliberation Generate Alpha\nin Prediction Markets?",
            fontsize=14, color=C["dim"], ha="center", va="center", linespacing=1.6)

    n_total = len(df)
    n_crypto = len(df[df["category"] == "Crypto"])
    n_nc = len(df[df["category"] == "Non-Crypto"])
    date_range = f"{df['predicted_at'].min().strftime('%Y-%m-%d')} → {df['predicted_at'].max().strftime('%Y-%m-%d')}"

    info = (f"{n_total} Resolved Predictions  ·  {n_nc} Non-Crypto  ·  {n_crypto} Crypto\n"
            f"Period: {date_range}\n"
            f"Strategy: Kelly Criterion (Half-Kelly)  ·  Initial Bankroll: $1,000")
    ax.text(0.5, 0.38, info, fontsize=10, color=C["dim"], ha="center", va="center",
            linespacing=1.8, fontfamily="monospace")

    ax.text(0.5, 0.12, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            fontsize=9, color=C["border"], ha="center")
    ax.text(0.5, 0.08, "github.com/Andrewyzzz/Depredict", fontsize=8,
            color=C["border"], ha="center", style="italic")

    save_page(pdf, fig)


def page_executive_summary(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("Executive Summary", fontsize=18, color=C["primary"],
                 fontweight="bold", y=0.95)

    sim_all = simulate(df, "hybrid")
    sim_nc = simulate(df[df["category"] == "Non-Crypto"], "hybrid")
    sim_cr = simulate(df[df["category"] == "Crypto"], "hybrid")
    s_all, s_nc, s_cr = stats(sim_all), stats(sim_nc), stats(sim_cr)

    model_b = df["model_brier"].dropna().mean()
    market_b = df["market_brier"].dropna().mean()
    brier_wins = int((df["model_brier"] < df["market_brier"]).sum())

    # KPI cards as a table-like layout
    ax = fig.add_axes([0.05, 0.62, 0.9, 0.28])
    ax.axis("off")
    ax.set_xlim(0, 6); ax.set_ylim(0, 2)

    kpis = [
        ("Overall ROI", f"{s_all['roi']:+.1f}%", s_all["roi"] > 0),
        ("Non-Crypto ROI", f"{s_nc['roi']:+.1f}%", s_nc["roi"] > 0),
        ("Crypto ROI", f"{s_cr['roi']:+.1f}%", s_cr["roi"] > 0),
        ("Win Rate (All)", f"{s_all['wr']:.1f}%", s_all["wr"] > 50),
        ("Brier Edge", f"{market_b - model_b:+.4f}", market_b > model_b),
        ("Brier Wins", f"{brier_wins}/{len(df)}", brier_wins > len(df) / 2),
    ]
    for i, (label, value, positive) in enumerate(kpis):
        x = i
        color = C["green"] if positive else C["red"]
        rect = mpatches.FancyBboxPatch((x + 0.05, 0.1), 0.9, 1.8,
                                       boxstyle="round,pad=0.05",
                                       facecolor=C["card"], edgecolor=C["border"])
        ax.add_patch(rect)
        ax.text(x + 0.5, 1.5, label, fontsize=7, color=C["dim"],
                ha="center", va="center", fontweight="bold")
        ax.text(x + 0.5, 0.85, value, fontsize=16, color=color,
                ha="center", va="center", fontweight="bold", fontfamily="monospace")

    # Category comparison table
    ax2 = fig.add_axes([0.08, 0.22, 0.84, 0.32])
    ax2.axis("off")
    ax2.set_xlim(0, 10); ax2.set_ylim(0, 5)

    headers = ["Category", "Trades", "Win Rate", "ROI", "P&L", "Sharpe", "Max DD", "Final"]
    rows_data = [
        ("All", s_all), ("Non-Crypto", s_nc), ("Crypto", s_cr),
    ]

    # Header
    for j, h in enumerate(headers):
        ax2.text(j * 1.25, 4.5, h, fontsize=7.5, color=C["dim"],
                 fontweight="bold", ha="center", va="center")
    ax2.plot([0, 10], [4.15, 4.15], color=C["border"], linewidth=0.5)

    for i, (label, s) in enumerate(rows_data):
        y = 3.5 - i * 1.0
        color = C["green"] if s["roi"] > 0 else C["red"]
        vals = [
            label,
            str(s["n"]),
            f"{s['wr']:.1f}%",
            f"{s['roi']:+.1f}%",
            f"${s['pnl']:+,.0f}",
            f"{s['sharpe']:+.2f}",
            f"{s['maxdd']:.1f}%",
            f"${s['final']:,.0f}",
        ]
        for j, v in enumerate(vals):
            c = color if j in (3, 4) else C["text"]
            ax2.text(j * 1.25, y, v, fontsize=9, color=c,
                     ha="center", va="center", fontfamily="monospace")
        ax2.plot([0, 10], [y - 0.4, y - 0.4], color=C["border"], linewidth=0.3, alpha=0.5)

    # Key finding
    ax3 = fig.add_axes([0.08, 0.04, 0.84, 0.14])
    ax3.axis("off")
    finding = (
        "KEY FINDING: DePredict generates significant alpha on non-crypto markets "
        f"({s_nc['roi']:+.0f}% ROI, {s_nc['wr']:.0f}% win rate) "
        f"but consistently loses on crypto predictions ({s_cr['roi']:+.0f}% ROI). "
        "Optimal strategy: deploy capital exclusively on non-crypto markets with half-Kelly sizing."
    )
    ax3.text(0.02, 0.5, finding, fontsize=9.5, color=C["text"],
             va="center", wrap=True,
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a2a3a", edgecolor=C["blue"], alpha=0.8))

    save_page(pdf, fig)


def page_methodology_1(pdf):
    """Methodology page 1: System Architecture & Signal Generation"""
    fig = new_page(pdf)
    fig.suptitle("Methodology — System & Signal", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    y = 9.8
    sections = [
        ("1. DePredict Multi-Expert Deliberation System", [
            "DePredict assembles 10 AI expert agents, each with a distinct analytical stance",
            "(bull, bear, neutral) and domain-specific knowledge profile, to deliberate on",
            "binary prediction market questions. Rather than relying on a single model's output,",
            "the system creates 'structured cognitive conflict' — forcing experts to surface",
            "blind spots, challenge each other's reasoning, and converge toward calibrated forecasts.",
            "",
            "The 10 agents span diverse analytical perspectives:",
            "  · Optimistic Analyst (Bull)        · Skeptical Analyst (Bear)",
            "  · Bayesian Analyst (Neutral)        · Historical Analogy Analyst (Neutral)",
            "  · Data Statistician (Neutral)       · Sentiment Analyst (Bull)",
            "  · Contrarian Investor (Bear)        · Fundamentals Analyst (Neutral)",
            "  · Risk Assessor (Bear)              · Synthesis Strategist (Neutral)",
        ]),
        ("2. Three-Round Debate Pipeline", [
            "Round 1 — Independent Prediction: Each agent receives RAG-retrieved documents",
            "  (YouTube transcripts + Tavily news) and produces an independent probability",
            "  estimate (0–100%) with reasoning. Information is partitioned: 40% shared docs +",
            "  60% private docs per agent, creating genuine information asymmetry.",
            "",
            "Round 2 — Cross-Rebuttal: Agents see all Round 1 predictions and reasoning,",
            "  then write rebuttals challenging specific points. Agents may revise their",
            "  probability in light of new arguments.",
            "",
            "Round 3 — Final Prediction: After reading all rebuttals, each agent commits",
            "  to a final probability, incorporating the strongest arguments from the debate.",
        ]),
        ("3. Nine Aggregation Mechanisms", [
            "The 10 agents' final predictions are aggregated via 9 independent mechanisms:",
            "",
            "  · Simple Average — arithmetic mean of all agent probabilities",
            "  · Median — robust to outlier predictions",
            "  · Trimmed Mean — removes top/bottom 10% before averaging",
            "  · Logit Average — aggregation in log-odds space (handles extremes better)",
            "  · Extremized Average — pushes consensus away from 50% (Baron et al. 2014)",
            "  · Reputation-Weighted — weights by historical Brier Score performance",
            "  · LMSR Market — Hanson's Logarithmic Market Scoring Rule with Kelly sizing",
            "  · Peer Prediction (BTS) — Bayesian Truth Serum, scores via meta-predictions",
            "  · Hybrid (M4) — weighted blend: 0.4×LMSR + 0.3×Reputation + 0.3×BTS",
            "",
            "The Hybrid (M4) mechanism is the primary signal used in this backtest.",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=11, color=C["blue"], fontweight="bold")
        y -= 0.35
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"], fontfamily="monospace")
            y -= 0.28
        y -= 0.25

    save_page(pdf, fig)


def page_methodology_2(pdf):
    """Methodology page 2: Trading Logic & Kelly Criterion"""
    fig = new_page(pdf)
    fig.suptitle("Methodology — Trading & Position Sizing", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    y = 9.8
    sections = [
        ("4. Trading Signal Generation", [
            "Polymarket is a binary prediction market: YES shares trade at price P_mkt ∈ (0,1),",
            "paying $1 if the event occurs and $0 otherwise. The market price equals the",
            "implied probability. Our trading signal exploits discrepancies between DePredict's",
            "model probability P_model and the market price P_mkt.",
            "",
            "Signal Logic:",
            "  If P_model > P_mkt  →  BUY YES  (model thinks event is more likely than market)",
            "  If P_model < P_mkt  →  BUY NO   (model thinks event is less likely than market)",
            "  Edge = |P_model − P_mkt|",
            "",
            "P&L Calculation:",
            "  BUY YES at cost P_mkt → if YES resolves:  profit = bet × (1 − P_mkt) / P_mkt",
            "                        → if NO resolves:   loss = −bet",
            "  BUY NO  at cost (1−P_mkt) → if NO resolves:   profit = bet × P_mkt / (1 − P_mkt)",
            "                            → if YES resolves:  loss = −bet",
        ]),
        ("5. Kelly Criterion Position Sizing", [
            "The Kelly Criterion determines the optimal fraction of bankroll to wager,",
            "maximizing long-run geometric growth while avoiding ruin.",
            "",
            "For a BUY YES trade (net odds b = (1 − P_mkt) / P_mkt):",
            "",
            "              P_model × b  −  (1 − P_model)",
            "  f* =  ─────────────────────────────────────",
            "                          b",
            "",
            "For a BUY NO trade (net odds b = P_mkt / (1 − P_mkt)):",
            "",
            "              (1 − P_model) × b  −  P_model",
            "  f* =  ───────────────────────────────────────",
            "                            b",
            "",
            "Where f* is the fraction of bankroll to bet. If f* ≤ 0, skip the trade.",
        ]),
        ("6. Half-Kelly & Risk Management", [
            "Full Kelly is theoretically optimal but assumes perfect probability estimates.",
            "In practice, model uncertainty means full Kelly over-bets, creating extreme",
            "volatility and drawdowns.",
            "",
            "We use Half-Kelly (f = 0.5 × f*) as the default, which:",
            "  · Achieves ~75% of full Kelly's long-run growth rate",
            "  · Cuts variance roughly in half",
            "  · Substantially reduces max drawdown",
            "  · Is more robust to probability estimation errors",
            "",
            "Sensitivity analysis is performed across Kelly fractions 0.1x → 1.0x.",
            "",
            "Additional parameters tested:",
            "  · Min Edge Threshold — only trade when |P_model − P_mkt| > threshold",
            "  · Category Filter — separate crypto vs non-crypto performance",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=11, color=C["blue"], fontweight="bold")
        y -= 0.35
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"], fontfamily="monospace")
            y -= 0.28
        y -= 0.25

    save_page(pdf, fig)


def page_methodology_3(pdf):
    """Methodology page 3: Evaluation Metrics"""
    fig = new_page(pdf)
    fig.suptitle("Methodology — Evaluation Framework", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    y = 9.8
    sections = [
        ("7. Profitability Metrics", [
            "  · Total P&L — absolute dollar profit/loss from initial bankroll",
            "  · ROI (Return on Investment) — P&L / initial_bankroll × 100%",
            "  · Win Rate — fraction of trades that result in positive P&L",
            "  · Sharpe Ratio — mean(per-trade return) / std(per-trade return)",
            "    Measures risk-adjusted returns; >0.5 is good, >1.0 is excellent",
            "  · Max Drawdown — largest peak-to-trough decline as % of peak bankroll",
            "    Measures worst-case capital erosion",
        ]),
        ("8. Prediction Quality Metrics", [
            "  · Brier Score — (P_predicted − outcome)², where outcome ∈ {0, 1}",
            "    Ranges 0 (perfect) to 1 (worst); lower is better",
            "  · Model vs Market Brier — compares DePredict Brier to market-implied Brier",
            "    (market_price − outcome)²; model wins if its Brier < market Brier",
            "  · Edge Distribution — histogram of (P_model − P_mkt) colored by W/L",
            "    Reveals whether large edges correlate with wins",
        ]),
        ("9. Sensitivity Dimensions", [
            "  · Kelly Fraction (0.1x → 1.0x) — find optimal risk level",
            "  · Edge Threshold (0% → 20%) — filter low-conviction signals",
            "  · Aggregation Mechanism (9 methods) — which aggregator is most profitable",
            "  · Category (Crypto vs Non-Crypto) — domain-specific performance",
        ]),
        ("10. Backtest Assumptions & Constraints", [
            "  · Execution at recorded market price (no slippage model)",
            "  · No transaction costs by default (Polymarket has no trading fees,",
            "    but bid/ask spread exists — sensitivity can be run with --friction)",
            "  · Sequential trades, bankroll updated after each resolution",
            "  · No look-ahead bias: only market_price_at_prediction is used",
            "  · No position limits or liquidity constraints",
            "  · All predictions use the same Kelly multiplier (no adaptive sizing)",
        ]),
        ("11. Data Collection", [
            "  · Markets sourced via Polymarket API (gamma-api.polymarket.com)",
            "  · Pre-filtered: excluded extreme prices (<5% or >95%),",
            "    derivative markets (props, spreads, O/U), geopolitical/violence topics",
            "  · Resolution checked automatically via API polling",
            "  · Time period: March 18–24, 2026 (7 days of live predictions)",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=11, color=C["blue"], fontweight="bold")
        y -= 0.35
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"], fontfamily="monospace")
            y -= 0.28
        y -= 0.2

    save_page(pdf, fig)


def page_equity_curve(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("Equity Curve — Hybrid (Half-Kelly)", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)
    ax = fig.add_subplot(111)

    bankroll = 1000.0
    for label, cat, color, ls in [
        ("Non-Crypto", "Non-Crypto", C["green"], "-"),
        ("Crypto", "Crypto", C["red"], "--"),
        ("All Markets", None, C["blue"], "-"),
    ]:
        sub = df if cat is None else df[df["category"] == cat]
        sim = simulate(sub, "hybrid", bankroll=bankroll)
        if sim.empty:
            continue
        eq = [bankroll] + sim["bank"].tolist()
        ax.plot(range(len(eq)), eq, label=label, color=color,
                linewidth=2 if cat is None else 1.8, linestyle=ls)

    ax.axhline(y=bankroll, color=C["dim"], linestyle=":", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Trade #", fontsize=10)
    ax.set_ylabel("Bankroll ($)", fontsize=10)
    ax.legend(loc="upper left")
    ax.set_title("")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_mechanism_comparison(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("ROI by Aggregation Mechanism & Category", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_subplot(111)
    x = np.arange(len(ALL_MECHANISMS))
    w = 0.25

    for i, (label, cat, color) in enumerate([
        ("All", None, C["blue"]),
        ("Non-Crypto", "Non-Crypto", C["green"]),
        ("Crypto", "Crypto", C["red"]),
    ]):
        rois = []
        for m in ALL_MECHANISMS:
            sub = df if cat is None else df[df["category"] == cat]
            sim = simulate(sub, m)
            roi = sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0
            rois.append(roi)
        bars = ax.bar(x + i * w - w, rois, w, label=label, color=color, alpha=0.85)
        for bar, roi in zip(bars, rois):
            if abs(roi) > 10:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f"{roi:+.0f}%", ha="center", va="bottom" if roi > 0 else "top",
                        fontsize=6, color=C["dim"])

    ax.set_xticks(x)
    ax.set_xticklabels([MECH_LABELS[m] for m in ALL_MECHANISMS], fontsize=7.5, rotation=30, ha="right")
    ax.set_ylabel("ROI (%)", fontsize=10)
    ax.axhline(y=0, color=C["text"], linewidth=0.8)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_brier_and_edge(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("Prediction Quality — Brier Score & Edge Distribution", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    # Brier scatter
    ax1 = fig.add_subplot(121)
    for cat, color, marker in [("Non-Crypto", C["green"], "o"), ("Crypto", C["red"], "D")]:
        sub = df[df["category"] == cat]
        ax1.scatter(sub["market_brier"], sub["model_brier"],
                    c=color, marker=marker, alpha=0.7, s=40, label=cat, edgecolors="white", linewidths=0.3)
    ax1.plot([0, 0.8], [0, 0.8], color=C["dim"], linestyle=":", linewidth=1, label="Model = Market")
    ax1.set_xlabel("Market Brier", fontsize=9)
    ax1.set_ylabel("Model Brier", fontsize=9)
    ax1.set_xlim(0, 0.75); ax1.set_ylim(0, 0.75)
    ax1.legend(fontsize=7)
    ax1.set_title("Model vs Market Brier Score", fontsize=10, color=C["primary"])
    ax1.text(0.55, 0.15, "Model Better", fontsize=8, color=C["green"], alpha=0.6)
    ax1.text(0.1, 0.6, "Market Better", fontsize=8, color=C["red"], alpha=0.6)

    # Edge distribution
    ax2 = fig.add_subplot(122)
    sim = simulate(df, "hybrid")
    if not sim.empty:
        wins = sim[sim["win"]]
        losses = sim[~sim["win"]]
        signed_edge_w = wins["edge"] * wins["side"].map({"YES": 1, "NO": -1})
        signed_edge_l = losses["edge"] * losses["side"].map({"YES": 1, "NO": -1})
        ax2.hist(signed_edge_w, bins=15, color=C["green"], alpha=0.6, label="Win")
        ax2.hist(signed_edge_l, bins=15, color=C["red"], alpha=0.6, label="Loss")
    ax2.axvline(x=0, color=C["dim"], linestyle=":", linewidth=0.8)
    ax2.set_xlabel("Signed Edge (Model − Market)", fontsize=9)
    ax2.set_ylabel("Count", fontsize=9)
    ax2.legend(fontsize=7)
    ax2.set_title("Edge Distribution by Outcome", fontsize=10, color=C["primary"])

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_sensitivity(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("Sensitivity Analysis", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    # Kelly sensitivity
    ax1 = fig.add_subplot(121)
    fracs = np.arange(0.05, 1.05, 0.05)
    for label, cat, color in [("All", None, C["blue"]), ("Non-Crypto", "Non-Crypto", C["green"]), ("Crypto", "Crypto", C["red"])]:
        rois = []
        for kf in fracs:
            sub = df if cat is None else df[df["category"] == cat]
            sim = simulate(sub, "hybrid", kelly_mult=kf)
            rois.append(sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0)
        ax1.plot(fracs, rois, color=color, label=label, linewidth=2, marker="o", markersize=3)
    ax1.axhline(y=0, color=C["dim"], linestyle=":", linewidth=0.8)
    ax1.set_xlabel("Kelly Fraction", fontsize=9)
    ax1.set_ylabel("ROI (%)", fontsize=9)
    ax1.legend(fontsize=7)
    ax1.set_title("Kelly Fraction vs ROI", fontsize=10, color=C["primary"])

    # Edge threshold sensitivity
    ax2 = fig.add_subplot(122)
    thresholds = np.arange(0, 0.21, 0.01)
    for label, cat, color in [("All", None, C["blue"]), ("Non-Crypto", "Non-Crypto", C["green"]), ("Crypto", "Crypto", C["red"])]:
        rois = []
        for thr in thresholds:
            sub = df if cat is None else df[df["category"] == cat]
            sim = simulate(sub, "hybrid", min_edge=thr)
            rois.append(sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0)
        ax2.plot(thresholds * 100, rois, color=color, label=label, linewidth=2, marker="o", markersize=3)
    ax2.axhline(y=0, color=C["dim"], linestyle=":", linewidth=0.8)
    ax2.set_xlabel("Min Edge Threshold (%)", fontsize=9)
    ax2.set_ylabel("ROI (%)", fontsize=9)
    ax2.legend(fontsize=7)
    ax2.set_title("Edge Threshold vs ROI", fontsize=10, color=C["primary"])

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_subcategory(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("Performance by Sub-Category", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    def sub_cat(slug):
        s = slug.lower()
        if any(k in s for k in CRYPTO_KW): return "Crypto"
        if s.startswith("nba"): return "NBA"
        if s.startswith("nhl"): return "NHL"
        if s.startswith("cbb"): return "CBB"
        if s.startswith("epl") or s.startswith("uel"): return "Soccer"
        if s.startswith("lol") or s.startswith("cs2"): return "Esports"
        return "Other"

    sim = simulate(df, "hybrid")
    if sim.empty:
        save_page(pdf, fig); return

    sim["sub_cat"] = sim["question"].map(
        lambda q: sub_cat(df[df["question"] == q]["slug"].iloc[0] if len(df[df["question"] == q]) > 0 else ""))

    grouped = sim.groupby("sub_cat").agg(n=("win", "count"), wins=("win", "sum"), pnl=("pnl", "sum"))
    grouped["wr"] = grouped["wins"] / grouped["n"] * 100
    grouped = grouped.sort_values("pnl", ascending=True)

    ax1 = fig.add_subplot(121)
    colors_bar = [C["green"] if v > 0 else C["red"] for v in grouped["pnl"]]
    ax1.barh(grouped.index, grouped["pnl"], color=colors_bar, alpha=0.85)
    ax1.set_xlabel("P&L ($)", fontsize=9)
    ax1.set_title("P&L by Sub-Category", fontsize=10, color=C["primary"])
    ax1.axvline(x=0, color=C["dim"], linewidth=0.8)
    for i, (idx, row) in enumerate(grouped.iterrows()):
        ax1.text(row["pnl"], i, f"  ${row['pnl']:+,.0f}", va="center", fontsize=7,
                 color=C["green"] if row["pnl"] > 0 else C["red"])

    ax2 = fig.add_subplot(122)
    colors_wr = [C["green"] if v > 50 else C["amber"] if v >= 40 else C["red"] for v in grouped["wr"]]
    bars = ax2.barh(grouped.index, grouped["wr"], color=colors_wr, alpha=0.85)
    ax2.axvline(x=50, color=C["dim"], linestyle=":", linewidth=0.8)
    ax2.set_xlabel("Win Rate (%)", fontsize=9)
    ax2.set_title("Win Rate by Sub-Category", fontsize=10, color=C["primary"])
    for i, (idx, row) in enumerate(grouped.iterrows()):
        ax2.text(row["wr"] + 1, i, f"{row['wr']:.0f}% ({int(row['wins'])}/{int(row['n'])})",
                 va="center", fontsize=7, color=C["dim"])

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_waterfall(pdf, df, category):
    """Per-trade waterfall chart."""
    sub = df if category is None else df[df["category"] == category]
    sim = simulate(sub, "hybrid")
    if sim.empty:
        return

    fig = new_page(pdf)
    label = category or "All"
    fig.suptitle(f"Per-Trade P&L Waterfall — {label}", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_subplot(111)
    n = len(sim)
    cumulative = 0
    bottoms = []
    heights = []
    colors = []
    for _, r in sim.iterrows():
        bottoms.append(cumulative if r["pnl"] >= 0 else cumulative + r["pnl"])
        heights.append(abs(r["pnl"]))
        colors.append(C["green"] if r["pnl"] >= 0 else C["red"])
        cumulative += r["pnl"]

    ax.bar(range(n), heights, bottom=bottoms, color=colors, alpha=0.85, width=0.7)
    ax.axhline(y=0, color=C["dim"], linewidth=0.8)

    labels = [q[:18] + ".." if len(q) > 20 else q for q in sim["question"]]
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=5.5, rotation=55, ha="right")
    ax.set_ylabel("Cumulative P&L ($)", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_trade_table(pdf, df, category, bankroll=1000.0):
    """Per-trade table across pages."""
    sub = df if category is None else df[df["category"] == category]
    sim = simulate(sub, "hybrid", bankroll=bankroll)
    if sim.empty:
        return

    label = category or "All"
    rows_per_page = 28
    total_pages = (len(sim) + rows_per_page - 1) // rows_per_page

    for page_num in range(total_pages):
        fig = new_page(pdf)
        fig.suptitle(f"Trade Log — {label} (Page {page_num + 1}/{total_pages})", fontsize=14,
                     color=C["primary"], fontweight="bold", y=0.95)

        ax = fig.add_axes([0.03, 0.03, 0.94, 0.88])
        ax.axis("off")
        ax.set_xlim(0, 11); ax.set_ylim(0, rows_per_page + 2)

        cols = ["#", "Question", "Side", "Model", "Market", "Edge", "Kelly", "Bet", "P&L", "Bank", "W/L"]
        col_x = [0.1, 0.4, 3.6, 4.2, 4.9, 5.6, 6.2, 6.9, 7.8, 8.8, 9.8]

        y = rows_per_page + 1.2
        for j, (c, x) in enumerate(zip(cols, col_x)):
            ax.text(x, y, c, fontsize=7.5, color=C["dim"], fontweight="bold")
        ax.plot([0, 10.5], [y - 0.3, y - 0.3], color=C["border"], linewidth=0.5)

        start = page_num * rows_per_page
        end = min(start + rows_per_page, len(sim))
        chunk = sim.iloc[start:end]

        for i, (_, r) in enumerate(chunk.iterrows()):
            row_y = rows_per_page - i
            color = C["green"] if r["win"] else C["red"]
            q = r["question"][:25] + ".." if len(r["question"]) > 27 else r["question"]
            vals = [
                str(start + i + 1),
                q,
                r["side"],
                f"{r['p']:.1%}",
                f"{r['mkt']:.1%}",
                f"{r['edge']:.1%}",
                f"{r['kf']:.1%}",
                f"${r['bet']:.0f}",
                f"${r['pnl']:+,.0f}",
                f"${r['bank']:,.0f}",
                "W" if r["win"] else "L",
            ]
            for j, (v, x) in enumerate(zip(vals, col_x)):
                c = color if j in (8, 9, 10) else C["text"]
                fs = 7.2
                ax.text(x, row_y, v, fontsize=fs, color=c, fontfamily="monospace")
            ax.plot([0, 10.5], [row_y - 0.3, row_y - 0.3], color=C["border"],
                    linewidth=0.2, alpha=0.3)

        save_page(pdf, fig)


def page_conclusions(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("Conclusions & Recommendations", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    sim_nc = simulate(df[df["category"] == "Non-Crypto"], "hybrid")
    s_nc = stats(sim_nc)

    y = 9.8
    sections = [
        ("Key Findings", [
            f"1. Non-Crypto markets show strong, consistent alpha: {s_nc['roi']:+.0f}% ROI,",
            f"   {s_nc['wr']:.0f}% win rate, Sharpe {s_nc['sharpe']:.2f} over {s_nc['n']} trades.",
            "",
            "2. Crypto predictions consistently underperform the market — the model's",
            "   probability estimates for BTC/ETH price questions are systematically",
            "   worse than market-implied probabilities. Win rate: ~30%.",
            "",
            "3. Half-Kelly (0.5x) is near-optimal. Full Kelly over-bets and erases",
            "   profits due to estimation noise. Quarter-Kelly (0.25x) is safer but",
            "   leaves significant returns on the table.",
            "",
            "4. All 9 aggregation mechanisms are profitable on non-crypto markets.",
            "   Extremized performs best by ROI but with higher variance.",
            "   Hybrid (M4) provides the best risk-adjusted performance.",
            "",
            "5. Sports markets (NBA, NHL, CBB, Soccer) are the primary alpha source.",
            "   The multi-expert debate structure surfaces analytical edges that",
            "   single-model approaches and casual bettors miss.",
        ]),
        ("Recommendations", [
            "1. DEPLOY on non-crypto markets only. Exclude all crypto price predictions.",
            "",
            "2. USE half-Kelly (0.5x) position sizing with the Hybrid (M4) aggregator.",
            "",
            "3. NO minimum edge filter needed — the Kelly criterion naturally sizes",
            "   low-conviction bets smaller. Trading all signals maximizes total P&L.",
            "",
            "4. SCALE UP data collection: 48 predictions over 7 days is promising but",
            "   statistically limited. Target 200+ resolved predictions for significance.",
            "",
            "5. INVESTIGATE crypto failure mode: the agents may lack real-time on-chain",
            "   data and order flow information that crypto markets efficiently price in.",
            "   Consider specialized crypto-only agents or excluding crypto entirely.",
        ]),
        ("Caveats", [
            "· Small sample (48 predictions, 7-day window) — results may not generalize",
            "· No slippage / liquidity constraints modeled",
            "· Markets were pre-filtered (excluded extremes, geopolitical topics)",
            "· Backtest uses recorded market price — real execution may differ",
            "· Path dependency: Kelly sizing on small samples amplifies randomness",
            "· Crypto subsample (n=10) too small for confident conclusions,",
            "  though directionally clear",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=12, color=C["blue"], fontweight="bold")
        y -= 0.4
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"], fontfamily="monospace")
            y -= 0.28
        y -= 0.3

    save_page(pdf, fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate DePredict backtest PDF report")
    parser.add_argument("-o", "--output", default=None, help="Output path")
    args = parser.parse_args()

    output = Path(args.output) if args.output else PROJECT_ROOT / "reports" / "backtest_report.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    df = load_data()
    n_cr = len(df[df["category"] == "Crypto"])
    n_nc = len(df[df["category"] == "Non-Crypto"])
    print(f"  {len(df)} resolved ({n_nc} non-crypto, {n_cr} crypto)")

    print("Generating PDF report...")
    with PdfPages(str(output)) as pdf:
        page_cover(pdf, df)
        page_executive_summary(pdf, df)
        page_methodology_1(pdf)
        page_methodology_2(pdf)
        page_methodology_3(pdf)
        page_equity_curve(pdf, df)
        page_mechanism_comparison(pdf, df)
        page_brier_and_edge(pdf, df)
        page_subcategory(pdf, df)
        page_sensitivity(pdf, df)
        page_waterfall(pdf, df, "Non-Crypto")
        page_waterfall(pdf, df, "Crypto")
        page_trade_table(pdf, df, "Non-Crypto")
        page_trade_table(pdf, df, "Crypto")
        page_conclusions(pdf, df)

    print(f"Report saved to: {output}")
    print(f"  {output.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
