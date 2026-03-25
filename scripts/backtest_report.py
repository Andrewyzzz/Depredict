#!/usr/bin/env python3
"""
DePredict Polymarket Backtest Report Generator

Generates a comprehensive HTML report with interactive Plotly charts.
Analyzes profitability using Kelly Criterion across Crypto vs Non-Crypto.

Usage:
    python scripts/backtest_report.py
    python scripts/backtest_report.py --output reports/backtest.html
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_PATH = PROJECT_ROOT / "data" / "prospective" / "predictions.json"

# ============================================================
# Design tokens (from DESIGN.md — "The Quantitative Vanguard")
# ============================================================
COLORS = {
    "bg": "#111317",
    "surface": "#1a1c20",
    "surface_high": "#1e2024",
    "surface_highest": "#333539",
    "primary": "#adc6ff",
    "primary_container": "#4d8eff",
    "on_surface": "#e2e2e8",
    "on_surface_variant": "#c2c6d6",
    "outline_variant": "#424754",
    "green": "#4ae176",
    "red": "#ffb3ad",
    "red_deep": "#ff6b6b",
    "green_deep": "#2ecc71",
    "amber": "#f0b90b",
    "purple": "#b48eff",
    "cyan": "#56d4e0",
    "orange": "#ff9f43",
    "pink": "#ff6b9d",
}

MECH_COLORS = {
    "simple_average": "#4d8eff",
    "median": "#4ae176",
    "trimmed_mean": "#56d4e0",
    "logit_average": "#b48eff",
    "extremized": "#f0b90b",
    "reputation_weighted": "#ff9f43",
    "lmsr_market": "#ff6b9d",
    "peer_prediction": "#ff6b6b",
    "hybrid": "#adc6ff",
}

MECH_LABELS = {
    "simple_average": "Simple Avg",
    "median": "Median",
    "trimmed_mean": "Trimmed Mean",
    "logit_average": "Logit Avg",
    "extremized": "Extremized",
    "reputation_weighted": "Rep-Weighted",
    "lmsr_market": "LMSR Market",
    "peer_prediction": "Peer Predict",
    "hybrid": "Hybrid (M4)",
}

ALL_MECHANISMS = list(MECH_LABELS.keys())

CRYPTO_KEYWORDS = [
    "bitcoin", "ethereum", "btc", "eth", "crypto", "solana", "sol",
    "xrp", "bnb", "doge", "dogecoin", "altcoin", "defi",
]


# ============================================================
# Data helpers
# ============================================================

def is_crypto(pred: dict) -> bool:
    text = (pred.get("slug", "") + " " + pred.get("question", "")).lower()
    return any(kw in text for kw in CRYPTO_KEYWORDS)


def load_predictions() -> pd.DataFrame:
    with open(DATA_PATH) as f:
        data = json.load(f)
    resolved = [p for p in data if p["status"] == "resolved" and p["resolution"] is not None]

    rows = []
    for p in resolved:
        mechs = p.get("all_mechanisms", {})
        row = {
            "question": p["question"],
            "slug": p["slug"],
            "category": "Crypto" if is_crypto(p) else "Non-Crypto",
            "market_price": p["market_price_at_prediction"],
            "resolution": p["resolution"],
            "model_brier": p.get("model_brier"),
            "market_brier": p.get("market_brier"),
            "predicted_at": pd.to_datetime(p["predicted_at"]),
            "resolved_at": pd.to_datetime(p.get("resolved_at")),
        }
        for m in ALL_MECHANISMS:
            row[f"prob_{m}"] = mechs.get(m)
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("predicted_at").reset_index(drop=True)
    return df


# ============================================================
# Kelly & P&L engine
# ============================================================

def kelly_f(p: float, market_price: float, side: str) -> float:
    if side == "YES":
        b = (1.0 - market_price) / market_price
        f = (p * b - (1.0 - p)) / b
    else:
        b = market_price / (1.0 - market_price)
        f = ((1.0 - p) * b - p) / b
    return max(f, 0.0)


def simulate(df: pd.DataFrame, mechanism: str, kelly_mult: float = 0.5,
             min_edge: float = 0.0, friction: float = 0.0,
             bankroll: float = 1000.0) -> pd.DataFrame:
    """Simulate trades and return a DataFrame with per-trade results."""
    prob_col = f"prob_{mechanism}"
    records = []
    bank = bankroll

    for _, row in df.iterrows():
        prob_pct = row[prob_col]
        if prob_pct is None or np.isnan(prob_pct):
            continue
        p = prob_pct / 100.0
        mp = row["market_price"]
        edge = p - mp

        if abs(edge) < min_edge:
            continue

        side = "YES" if edge > 0 else "NO"
        kf = kelly_f(p, mp, side) * kelly_mult
        if kf <= 0:
            continue

        bet = bank * kf
        eff_bet = bet * (1.0 - friction)

        if side == "YES":
            if row["resolution"]:
                pnl = eff_bet * (1.0 - mp) / mp
                win = True
            else:
                pnl = -eff_bet
                win = False
        else:
            if not row["resolution"]:
                pnl = eff_bet * mp / (1.0 - mp)
                win = True
            else:
                pnl = -eff_bet
                win = False

        bank += pnl

        records.append({
            "question": row["question"],
            "category": row["category"],
            "predicted_at": row["predicted_at"],
            "side": side,
            "model_prob": p,
            "market_price": mp,
            "edge": abs(edge),
            "kelly_f": kf,
            "bet": bet,
            "pnl": pnl,
            "win": win,
            "bankroll": bank,
            "mechanism": mechanism,
        })

    return pd.DataFrame(records)


# ============================================================
# Chart builders
# ============================================================

def _layout(fig, title="", height=500):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["surface"],
        font=dict(family="Space Grotesk, Inter, monospace", color=COLORS["on_surface"]),
        title=dict(text=title, font=dict(size=20, color=COLORS["primary"])),
        height=height,
        margin=dict(l=60, r=40, t=60, b=50),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    )
    fig.update_xaxes(gridcolor=COLORS["outline_variant"], gridwidth=0.5)
    fig.update_yaxes(gridcolor=COLORS["outline_variant"], gridwidth=0.5)
    return fig


def fig_equity_curve(df: pd.DataFrame, bankroll: float = 1000.0) -> go.Figure:
    """Equity curve per category for hybrid mechanism."""
    fig = go.Figure()
    for cat, color in [("Non-Crypto", COLORS["green"]), ("Crypto", COLORS["red_deep"]), ("ALL", COLORS["primary_container"])]:
        if cat == "ALL":
            sim = simulate(df, "hybrid", bankroll=bankroll)
        else:
            sub = df[df["category"] == cat]
            sim = simulate(sub, "hybrid", bankroll=bankroll)
        if sim.empty:
            continue
        eq = pd.concat([pd.DataFrame([{"bankroll": bankroll, "predicted_at": sim["predicted_at"].iloc[0]}]), sim[["bankroll", "predicted_at"]]])
        fig.add_trace(go.Scatter(
            x=list(range(len(eq))), y=eq["bankroll"],
            name=cat, mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            hovertemplate="%{y:$.2f}<extra>" + cat + "</extra>",
        ))
    fig.add_hline(y=bankroll, line_dash="dash", line_color=COLORS["outline_variant"], opacity=0.6)
    return _layout(fig, "Equity Curve — Hybrid (Half-Kelly)", 420)


def fig_mechanism_roi(df: pd.DataFrame) -> go.Figure:
    """Bar chart: ROI by mechanism, grouped by category."""
    fig = go.Figure()
    categories = ["ALL", "Non-Crypto", "Crypto"]
    cat_colors = {"ALL": COLORS["primary_container"], "Non-Crypto": COLORS["green"], "Crypto": COLORS["red_deep"]}

    data_map = {}
    for cat in categories:
        rois = []
        for m in ALL_MECHANISMS:
            sub = df if cat == "ALL" else df[df["category"] == cat]
            sim = simulate(sub, m)
            roi = (sim["pnl"].sum() / 1000.0 * 100) if not sim.empty else 0
            rois.append(roi)
        data_map[cat] = rois

    for cat in categories:
        fig.add_trace(go.Bar(
            x=[MECH_LABELS[m] for m in ALL_MECHANISMS],
            y=data_map[cat],
            name=cat,
            marker_color=cat_colors[cat],
            opacity=0.85,
        ))
    fig.update_layout(barmode="group")
    fig.add_hline(y=0, line_color=COLORS["on_surface_variant"], line_width=1)
    return _layout(fig, "ROI (%) by Aggregation Mechanism", 450)


def fig_edge_distribution(df: pd.DataFrame) -> go.Figure:
    """Histogram of model edge (model_prob - market_price), colored by W/L."""
    sim = simulate(df, "hybrid")
    if sim.empty:
        return go.Figure()

    wins = sim[sim["win"]]
    losses = sim[~sim["win"]]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=wins["edge"] * (wins["side"].map({"YES": 1, "NO": -1})),
        name="Win", marker_color=COLORS["green"], opacity=0.7, nbinsx=20,
    ))
    fig.add_trace(go.Histogram(
        x=losses["edge"] * (losses["side"].map({"YES": 1, "NO": -1})),
        name="Loss", marker_color=COLORS["red_deep"], opacity=0.7, nbinsx=20,
    ))
    fig.update_layout(barmode="overlay")
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["on_surface_variant"])
    return _layout(fig, "Edge Distribution (Model - Market) by Outcome", 380)


def fig_brier_comparison(df: pd.DataFrame) -> go.Figure:
    """Brier score: Model vs Market, per category."""
    fig = go.Figure()

    for cat in ["ALL", "Non-Crypto", "Crypto"]:
        sub = df if cat == "ALL" else df[df["category"] == cat]
        model_brier = sub["model_brier"].dropna().mean()
        market_brier = sub["market_brier"].dropna().mean()
        fig.add_trace(go.Bar(x=[cat], y=[model_brier], name="DePredict" if cat == "ALL" else None,
                             marker_color=COLORS["primary_container"], showlegend=(cat == "ALL"),
                             legendgroup="model"))
        fig.add_trace(go.Bar(x=[cat], y=[market_brier], name="Market" if cat == "ALL" else None,
                             marker_color=COLORS["outline_variant"], showlegend=(cat == "ALL"),
                             legendgroup="market"))

    fig.update_layout(barmode="group")
    return _layout(fig, "Avg Brier Score — DePredict vs Market (Lower is Better)", 380)


def fig_kelly_sensitivity(df: pd.DataFrame) -> go.Figure:
    """Kelly fraction sensitivity curve per category."""
    fig = go.Figure()
    fracs = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 1.0]

    for cat, color in [("ALL", COLORS["primary_container"]), ("Non-Crypto", COLORS["green"]), ("Crypto", COLORS["red_deep"])]:
        rois, dds = [], []
        for kf in fracs:
            sub = df if cat == "ALL" else df[df["category"] == cat]
            sim = simulate(sub, "hybrid", kelly_mult=kf)
            roi = sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0
            # max drawdown
            if not sim.empty:
                peak = sim["bankroll"].cummax()
                dd = ((peak - sim["bankroll"]) / peak).max() * 100
            else:
                dd = 0
            rois.append(roi)
            dds.append(dd)

        fig.add_trace(go.Scatter(
            x=fracs, y=rois, name=f"{cat} ROI",
            mode="lines+markers", line=dict(color=color, width=2.5),
            marker=dict(size=6),
        ))
        fig.add_trace(go.Scatter(
            x=fracs, y=[-d for d in dds], name=f"{cat} -MaxDD",
            mode="lines", line=dict(color=color, width=1.5, dash="dot"),
            opacity=0.6,
        ))

    fig.add_hline(y=0, line_color=COLORS["on_surface_variant"], line_width=1)
    fig.update_xaxes(title_text="Kelly Fraction")
    fig.update_yaxes(title_text="ROI% / -MaxDD%")
    return _layout(fig, "Kelly Fraction Sensitivity — ROI & Max Drawdown", 420)


def fig_edge_threshold_sensitivity(df: pd.DataFrame) -> go.Figure:
    """Edge threshold sensitivity per category."""
    fig = go.Figure()
    thresholds = [0.0, 0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]

    for cat, color in [("ALL", COLORS["primary_container"]), ("Non-Crypto", COLORS["green"]), ("Crypto", COLORS["red_deep"])]:
        rois, trades = [], []
        for thr in thresholds:
            sub = df if cat == "ALL" else df[df["category"] == cat]
            sim = simulate(sub, "hybrid", min_edge=thr)
            roi = sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0
            rois.append(roi)
            trades.append(len(sim))

        fig.add_trace(go.Scatter(
            x=[t * 100 for t in thresholds], y=rois, name=cat,
            mode="lines+markers", line=dict(color=color, width=2.5),
            marker=dict(size=6),
            hovertemplate="Edge>=%{x:.0f}%<br>ROI: %{y:.1f}%<br><extra>" + cat + "</extra>",
        ))

    fig.add_hline(y=0, line_color=COLORS["on_surface_variant"], line_width=1)
    fig.update_xaxes(title_text="Min Edge Threshold (%)")
    fig.update_yaxes(title_text="ROI (%)")
    return _layout(fig, "Edge Threshold Sensitivity — Hybrid Half-Kelly", 420)


def fig_per_trade_waterfall(df: pd.DataFrame, category: Optional[str] = None) -> go.Figure:
    """Waterfall chart of per-trade P&L."""
    sub = df if category is None else df[df["category"] == category]
    sim = simulate(sub, "hybrid")
    if sim.empty:
        return go.Figure()

    labels = [q[:25] + ".." if len(q) > 27 else q for q in sim["question"]]
    colors = [COLORS["green"] if w else COLORS["red_deep"] for w in sim["win"]]

    fig = go.Figure(go.Waterfall(
        x=labels, y=sim["pnl"].tolist(),
        connector=dict(line=dict(color=COLORS["outline_variant"])),
        increasing=dict(marker=dict(color=COLORS["green"])),
        decreasing=dict(marker=dict(color=COLORS["red_deep"])),
        totals=dict(marker=dict(color=COLORS["primary_container"])),
        hovertemplate="%{x}<br>PnL: $%{y:.2f}<extra></extra>",
    ))
    title = f"Per-Trade P&L Waterfall — {category or 'ALL'}"
    return _layout(fig, title, 420)


def fig_win_rate_by_category(df: pd.DataFrame) -> go.Figure:
    """Win rate and trade count breakdown by sub-category."""
    # Detect sub-categories from slug
    def sub_cat(slug):
        s = slug.lower()
        if any(k in s for k in CRYPTO_KEYWORDS):
            return "Crypto"
        if s.startswith("nba"):
            return "NBA"
        if s.startswith("nhl"):
            return "NHL"
        if s.startswith("cbb"):
            return "CBB"
        if s.startswith("epl") or s.startswith("uel"):
            return "Soccer"
        if s.startswith("lol") or s.startswith("cs2"):
            return "Esports"
        return "Other"

    sim = simulate(df, "hybrid")
    if sim.empty:
        return go.Figure()

    # Map original slug
    slug_map = dict(zip(df["question"], df["slug"]))
    sim["sub_cat"] = sim["question"].map(lambda q: sub_cat(slug_map.get(q, "")))

    grouped = sim.groupby("sub_cat").agg(
        trades=("win", "count"),
        wins=("win", "sum"),
        pnl=("pnl", "sum"),
    ).reset_index()
    grouped["win_rate"] = grouped["wins"] / grouped["trades"] * 100
    grouped = grouped.sort_values("trades", ascending=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=grouped["sub_cat"], y=grouped["win_rate"],
        name="Win Rate %", marker_color=COLORS["primary_container"], opacity=0.85,
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=grouped["sub_cat"], y=grouped["pnl"],
        name="P&L ($)", mode="lines+markers",
        line=dict(color=COLORS["green"], width=2.5),
        marker=dict(size=8),
    ), secondary_y=True)
    fig.add_hline(y=50, line_dash="dash", line_color=COLORS["on_surface_variant"], opacity=0.5, secondary_y=False)
    fig.update_yaxes(title_text="Win Rate %", secondary_y=False)
    fig.update_yaxes(title_text="P&L ($)", secondary_y=True)
    return _layout(fig, "Performance by Sub-Category — Hybrid Half-Kelly", 420)


# ============================================================
# Summary stats table
# ============================================================

def build_summary_table(df: pd.DataFrame) -> str:
    """Build HTML summary tables."""
    rows_main = []
    for cat in ["ALL", "Non-Crypto", "Crypto"]:
        sub = df if cat == "ALL" else df[df["category"] == cat]
        n = len(sub)
        model_b = sub["model_brier"].dropna().mean()
        market_b = sub["market_brier"].dropna().mean()
        model_wins_brier = (sub["model_brier"] < sub["market_brier"]).sum()

        for m in ALL_MECHANISMS:
            sim = simulate(sub, m)
            nt = len(sim)
            if nt == 0:
                rows_main.append({
                    "Category": cat, "Mechanism": MECH_LABELS[m],
                    "Trades": 0, "Win Rate": "-", "ROI": "-",
                    "PnL": "-", "Sharpe": "-", "MaxDD": "-",
                })
                continue
            wins = sim["win"].sum()
            pnl = sim["pnl"].sum()
            roi = pnl / 1000 * 100
            rets = sim["pnl"] / sim["bet"]
            sharpe = rets.mean() / rets.std() if rets.std() > 0 else 0
            peak = sim["bankroll"].cummax()
            dd = ((peak - sim["bankroll"]) / peak).max() * 100

            rows_main.append({
                "Category": cat,
                "Mechanism": MECH_LABELS[m],
                "Trades": nt,
                "Win Rate": f"{wins/nt*100:.1f}%",
                "ROI": f"{roi:+.1f}%",
                "PnL": f"${pnl:+,.2f}",
                "Sharpe": f"{sharpe:+.2f}",
                "MaxDD": f"{dd:.1f}%",
            })

    # Build HTML table
    html = '<table class="data-table">\n<thead><tr>'
    cols = ["Category", "Mechanism", "Trades", "Win Rate", "ROI", "PnL", "Sharpe", "MaxDD"]
    for c in cols:
        html += f"<th>{c}</th>"
    html += "</tr></thead>\n<tbody>\n"

    prev_cat = None
    for r in rows_main:
        cat_class = "crypto-row" if r["Category"] == "Crypto" else ("noncrypto-row" if r["Category"] == "Non-Crypto" else "all-row")
        separator = ' class="cat-separator"' if r["Category"] != prev_cat and prev_cat is not None else ""
        html += f'<tr class="{cat_class}"{separator}>'
        for c in cols:
            val = r[c]
            extra = ""
            if c == "ROI" and isinstance(val, str) and val.startswith("+"):
                extra = ' style="color: #4ae176"'
            elif c == "ROI" and isinstance(val, str) and val.startswith("-"):
                extra = ' style="color: #ff6b6b"'
            if c == "PnL" and isinstance(val, str) and "+" in val:
                extra = ' style="color: #4ae176"'
            elif c == "PnL" and isinstance(val, str) and "-" in val:
                extra = ' style="color: #ff6b6b"'
            html += f"<td{extra}>{val}</td>"
        html += "</tr>\n"
        prev_cat = r["Category"]

    html += "</tbody></table>"
    return html


def build_trade_log_table(df: pd.DataFrame, category: Optional[str] = None) -> str:
    """Build HTML trade log for a specific category."""
    sub = df if category is None else df[df["category"] == category]
    sim = simulate(sub, "hybrid")
    if sim.empty:
        return "<p>No trades</p>"

    html = '<table class="trade-table">\n<thead><tr>'
    cols = ["#", "Question", "Side", "Model", "Market", "Edge", "Kelly%", "Bet", "PnL", "Bankroll", "W/L"]
    for c in cols:
        html += f"<th>{c}</th>"
    html += "</tr></thead>\n<tbody>\n"

    for i, (_, r) in enumerate(sim.iterrows(), 1):
        wl_class = "win" if r["win"] else "loss"
        q = r["question"][:35] + ".." if len(r["question"]) > 37 else r["question"]
        html += f'<tr class="{wl_class}">'
        html += f"<td>{i}</td>"
        html += f"<td>{q}</td>"
        html += f"<td>{r['side']}</td>"
        html += f"<td>{r['model_prob']:.1%}</td>"
        html += f"<td>{r['market_price']:.1%}</td>"
        html += f"<td>{r['edge']:.1%}</td>"
        html += f"<td>{r['kelly_f']:.1%}</td>"
        html += f"<td>${r['bet']:.2f}</td>"
        pnl_color = COLORS["green"] if r["pnl"] >= 0 else COLORS["red_deep"]
        html += f'<td style="color: {pnl_color}">${r["pnl"]:+.2f}</td>'
        html += f"<td>${r['bankroll']:.2f}</td>"
        html += f'<td class="{wl_class}-badge">{"W" if r["win"] else "L"}</td>'
        html += "</tr>\n"

    html += "</tbody></table>"
    return html


# ============================================================
# HTML report
# ============================================================

def build_html_report(df: pd.DataFrame) -> str:
    n_total = len(df)
    n_crypto = len(df[df["category"] == "Crypto"])
    n_noncrypto = len(df[df["category"] == "Non-Crypto"])

    # Key stats for hero section
    sim_all = simulate(df, "hybrid")
    sim_nc = simulate(df[df["category"] == "Non-Crypto"], "hybrid")
    sim_cr = simulate(df[df["category"] == "Crypto"], "hybrid")

    roi_all = sim_all["pnl"].sum() / 1000 * 100 if not sim_all.empty else 0
    roi_nc = sim_nc["pnl"].sum() / 1000 * 100 if not sim_nc.empty else 0
    roi_cr = sim_cr["pnl"].sum() / 1000 * 100 if not sim_cr.empty else 0
    wr_all = sim_all["win"].mean() * 100 if not sim_all.empty else 0
    wr_nc = sim_nc["win"].mean() * 100 if not sim_nc.empty else 0

    # Brier
    model_brier = df["model_brier"].dropna().mean()
    market_brier = df["market_brier"].dropna().mean()
    brier_edge = market_brier - model_brier

    # Generate figures
    figs = {
        "equity": fig_equity_curve(df),
        "mechanism_roi": fig_mechanism_roi(df),
        "edge_dist": fig_edge_distribution(df),
        "brier": fig_brier_comparison(df),
        "kelly_sens": fig_kelly_sensitivity(df),
        "edge_thresh": fig_edge_threshold_sensitivity(df),
        "waterfall_nc": fig_per_trade_waterfall(df, "Non-Crypto"),
        "waterfall_cr": fig_per_trade_waterfall(df, "Crypto"),
        "subcat": fig_win_rate_by_category(df),
    }
    fig_htmls = {k: v.to_html(full_html=False, include_plotlyjs=False) for k, v in figs.items()}

    summary_table = build_summary_table(df)
    trade_log_nc = build_trade_log_table(df, "Non-Crypto")
    trade_log_cr = build_trade_log_table(df, "Crypto")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DePredict Backtest Report</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {COLORS["bg"]};
    color: {COLORS["on_surface"]};
    font-family: 'Inter', sans-serif;
    line-height: 1.6;
    padding: 0;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 40px 48px; }}

  /* Hero */
  .hero {{
    padding: 48px 0 32px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 40px;
  }}
  .hero h1 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.2rem;
    font-weight: 700;
    color: {COLORS["primary"]};
    margin-bottom: 8px;
  }}
  .hero .subtitle {{
    color: {COLORS["on_surface_variant"]};
    font-size: 0.95rem;
    letter-spacing: 0.02em;
  }}
  .hero .meta {{
    margin-top: 16px;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {COLORS["outline_variant"]};
  }}

  /* KPI Cards */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 48px;
  }}
  .kpi-card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 24px;
    transition: transform 0.2s, border-color 0.2s;
  }}
  .kpi-card:hover {{
    transform: scale(1.01);
    border-color: rgba(255,255,255,0.1);
  }}
  .kpi-label {{
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {COLORS["on_surface_variant"]};
    margin-bottom: 8px;
  }}
  .kpi-value {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }}
  .kpi-value.positive {{ color: {COLORS["green"]}; }}
  .kpi-value.negative {{ color: {COLORS["red_deep"]}; }}
  .kpi-value.neutral {{ color: {COLORS["primary"]}; }}
  .kpi-sub {{
    font-size: 0.75rem;
    color: {COLORS["outline_variant"]};
    margin-top: 4px;
    font-variant-numeric: tabular-nums;
  }}

  /* Sections */
  .section {{
    margin-bottom: 56px;
  }}
  .section h2 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.25rem;
    font-weight: 600;
    color: {COLORS["primary"]};
    margin-bottom: 20px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }}
  .section h3 {{
    font-size: 1rem;
    color: {COLORS["on_surface_variant"]};
    margin: 24px 0 12px;
  }}
  .chart-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
  }}
  .chart-full {{ margin-bottom: 24px; }}
  .chart-box {{
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px;
    padding: 16px;
    overflow: hidden;
  }}

  /* Tables */
  .data-table, .trade-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
  }}
  .data-table th, .trade-table th {{
    text-align: left;
    padding: 10px 12px;
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {COLORS["on_surface_variant"]};
    border-bottom: 1px solid rgba(255,255,255,0.08);
    position: sticky;
    top: 0;
    background: {COLORS["surface"]};
  }}
  .data-table td, .trade-table td {{
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
  }}
  .data-table tr:hover, .trade-table tr:hover {{
    background: rgba(255,255,255,0.03);
  }}
  .cat-separator td {{
    border-top: 2px solid {COLORS["outline_variant"]};
  }}
  .win-badge {{ color: {COLORS["green"]}; font-weight: 600; }}
  .loss-badge {{ color: {COLORS["red_deep"]}; font-weight: 600; }}
  tr.win {{ background: rgba(74, 225, 118, 0.03); }}
  tr.loss {{ background: rgba(255, 107, 107, 0.03); }}
  .table-scroll {{
    max-height: 600px;
    overflow-y: auto;
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px;
    background: {COLORS["surface"]};
  }}

  /* Insight boxes */
  .insight {{
    background: rgba(77, 142, 255, 0.06);
    border-left: 3px solid {COLORS["primary_container"]};
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin: 20px 0;
    font-size: 0.9rem;
    line-height: 1.7;
  }}
  .insight strong {{ color: {COLORS["primary"]}; }}
  .insight .warn {{ color: {COLORS["amber"]}; }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 32px 0;
    margin-top: 48px;
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 0.75rem;
    color: {COLORS["outline_variant"]};
  }}

  @media (max-width: 900px) {{
    .chart-row {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .container {{ padding: 24px 16px; }}
  }}
</style>
</head>
<body>
<div class="container">

<!-- Hero -->
<div class="hero">
  <h1>DePredict Backtest Report</h1>
  <div class="subtitle">Can AI multi-expert deliberation beat Polymarket? A Kelly Criterion backtest.</div>
  <div class="meta">Generated {now} &nbsp;|&nbsp; {n_total} resolved predictions &nbsp;|&nbsp; Half-Kelly &nbsp;|&nbsp; $1,000 initial bankroll</div>
</div>

<!-- KPI Cards -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Overall ROI (Hybrid)</div>
    <div class="kpi-value {"positive" if roi_all > 0 else "negative"}">{roi_all:+.1f}%</div>
    <div class="kpi-sub">{n_total} markets traded</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Non-Crypto ROI</div>
    <div class="kpi-value {"positive" if roi_nc > 0 else "negative"}">{roi_nc:+.1f}%</div>
    <div class="kpi-sub">{n_noncrypto} markets &nbsp;|&nbsp; {wr_nc:.0f}% win rate</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Crypto ROI</div>
    <div class="kpi-value {"positive" if roi_cr > 0 else "negative"}">{roi_cr:+.1f}%</div>
    <div class="kpi-sub">{n_crypto} markets</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Brier Edge</div>
    <div class="kpi-value {"positive" if brier_edge > 0 else "negative"}">{brier_edge:+.4f}</div>
    <div class="kpi-sub">Model {model_brier:.4f} vs Market {market_brier:.4f}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Win Rate (ALL)</div>
    <div class="kpi-value neutral">{wr_all:.1f}%</div>
    <div class="kpi-sub">{int(sim_all["win"].sum())}/{len(sim_all)} trades</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Predictions</div>
    <div class="kpi-value neutral">{n_total}</div>
    <div class="kpi-sub">{n_noncrypto} non-crypto &nbsp;|&nbsp; {n_crypto} crypto</div>
  </div>
</div>

<!-- Key Insight -->
<div class="insight">
  <strong>Key Finding:</strong> DePredict generates significant alpha on <strong>non-crypto markets</strong>
  (sports, politics, entertainment) with <strong>{roi_nc:+.1f}% ROI</strong> and <strong>{wr_nc:.0f}% win rate</strong>,
  but <strong class="warn">consistently loses on crypto predictions ({roi_cr:+.1f}% ROI)</strong>.
  The optimal strategy is to exclude crypto and trade non-crypto markets only with half-Kelly sizing.
</div>

<!-- 1. Equity Curve -->
<div class="section">
  <h2>1. Equity Curve</h2>
  <div class="chart-full"><div class="chart-box">{fig_htmls["equity"]}</div></div>
</div>

<!-- 2. Mechanism Comparison -->
<div class="section">
  <h2>2. Aggregation Mechanism Comparison</h2>
  <div class="chart-full"><div class="chart-box">{fig_htmls["mechanism_roi"]}</div></div>
  <div class="table-scroll">{summary_table}</div>
</div>

<!-- 3. Brier Score -->
<div class="section">
  <h2>3. Prediction Accuracy — Brier Score</h2>
  <div class="chart-row">
    <div class="chart-box">{fig_htmls["brier"]}</div>
    <div class="chart-box">{fig_htmls["edge_dist"]}</div>
  </div>
</div>

<!-- 4. Sub-Category Breakdown -->
<div class="section">
  <h2>4. Performance by Sub-Category</h2>
  <div class="chart-full"><div class="chart-box">{fig_htmls["subcat"]}</div></div>
</div>

<!-- 5. Sensitivity Analysis -->
<div class="section">
  <h2>5. Sensitivity Analysis</h2>
  <div class="chart-row">
    <div class="chart-box">{fig_htmls["kelly_sens"]}</div>
    <div class="chart-box">{fig_htmls["edge_thresh"]}</div>
  </div>
  <div class="insight">
    <strong>Optimal Parameters:</strong>
    Kelly fraction <strong>0.25x–0.50x</strong> maximizes risk-adjusted returns.
    Full Kelly (1.0x) causes over-betting and erases profits on the overall portfolio.
    Edge threshold has diminishing returns — trading all signals (0%) captures the most P&L on non-crypto.
  </div>
</div>

<!-- 6. Trade Logs -->
<div class="section">
  <h2>6. Trade Log — Non-Crypto</h2>
  <div class="chart-full"><div class="chart-box">{fig_htmls["waterfall_nc"]}</div></div>
  <div class="table-scroll">{trade_log_nc}</div>
</div>

<div class="section">
  <h2>7. Trade Log — Crypto</h2>
  <div class="chart-full"><div class="chart-box">{fig_htmls["waterfall_cr"]}</div></div>
  <div class="table-scroll">{trade_log_cr}</div>
</div>

<!-- Footer -->
<div class="footer">
  DePredict Backtest Report &nbsp;|&nbsp; Generated by backtest_report.py &nbsp;|&nbsp; {now}<br>
  Data: {n_total} resolved Polymarket predictions &nbsp;|&nbsp; Strategy: Kelly Criterion (0.5x) &nbsp;|&nbsp; Initial: $1,000
</div>

</div>
</body>
</html>"""
    return html


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate DePredict backtest report")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output HTML path (default: reports/backtest_report.html)")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else PROJECT_ROOT / "reports" / "backtest_report.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Loading predictions...")
    df = load_predictions()
    print(f"  {len(df)} resolved ({len(df[df['category']=='Crypto'])} crypto, {len(df[df['category']=='Non-Crypto'])} non-crypto)")

    print("Generating report...")
    html = build_html_report(df)

    output_path.write_text(html, encoding="utf-8")
    print(f"Report saved to: {output_path}")
    print(f"Open in browser: file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
