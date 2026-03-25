#!/usr/bin/env python3
"""
Backtest: Can DePredict predictions make money on Polymarket?

Uses Kelly Criterion for position sizing across all 9 aggregation methods.
Splits results into Crypto vs Non-Crypto categories.

Usage:
    python scripts/backtest_kelly.py
    python scripts/backtest_kelly.py --bankroll 1000 --friction 0.02
    python scripts/backtest_kelly.py --kelly-fraction 0.5   # half-kelly
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_PATH = PROJECT_ROOT / "data" / "prospective" / "predictions.json"

# --- Category Detection ---

CRYPTO_KEYWORDS = [
    "bitcoin", "ethereum", "btc", "eth", "crypto", "solana", "sol",
    "xrp", "bnb", "doge", "dogecoin", "altcoin", "defi",
]


def is_crypto(pred: dict) -> bool:
    slug = pred.get("slug", "").lower()
    question = pred.get("question", "").lower()
    text = slug + " " + question
    return any(kw in text for kw in CRYPTO_KEYWORDS)


def categorize(pred: dict) -> str:
    return "crypto" if is_crypto(pred) else "non_crypto"


# --- Kelly Criterion ---


def kelly_fraction(p: float, market_price: float, side: str) -> float:
    """
    Kelly fraction for a binary Polymarket bet.

    Buy YES at cost `market_price`, pays 1 if YES.
      odds b = (1 - market_price) / market_price  (net profit per $1 risked)
      f* = (p * b - q) / b  where q = 1 - p

    Buy NO at cost `1 - market_price`, pays 1 if NO.
      odds b = market_price / (1 - market_price)
      f* = ((1-p) * b - p) / b
    """
    if side == "YES":
        cost = market_price
        b = (1.0 - cost) / cost  # net odds
        f = (p * b - (1.0 - p)) / b
    else:  # NO
        cost = 1.0 - market_price
        b = market_price / (1.0 - market_price)
        f = ((1.0 - p) * b - p) / b
    return max(f, 0.0)


# --- Trade Logic ---


@dataclass
class Trade:
    question: str
    slug: str
    category: str
    side: str  # YES or NO
    model_prob: float
    market_price: float
    edge: float
    kelly_f: float
    bet_size: float
    pnl: float
    resolution: bool
    win: bool
    mechanism: str
    predicted_at: str


@dataclass
class Portfolio:
    bankroll: float
    initial_bankroll: float
    trades: list = field(default_factory=list)
    peak: float = 0.0
    max_drawdown: float = 0.0

    def update_drawdown(self):
        if self.bankroll > self.peak:
            self.peak = self.bankroll
        dd = (self.peak - self.bankroll) / self.peak if self.peak > 0 else 0
        if dd > self.max_drawdown:
            self.max_drawdown = dd


def run_backtest(
    predictions: list[dict],
    mechanism: str,
    bankroll: float = 1000.0,
    kelly_mult: float = 1.0,
    min_edge: float = 0.0,
    friction: float = 0.0,
    category_filter: Optional[str] = None,
) -> Portfolio:
    """
    Run backtest for a single aggregation mechanism.

    Args:
        predictions: list of resolved prediction dicts
        mechanism: which aggregation method to use for model_prob
        bankroll: starting capital
        kelly_mult: Kelly multiplier (1.0 = full Kelly, 0.5 = half Kelly)
        min_edge: minimum |model_prob - market_price| to trade
        friction: transaction cost as fraction (e.g., 0.02 = 2%)
        category_filter: "crypto", "non_crypto", or None for all
    """
    portfolio = Portfolio(bankroll=bankroll, initial_bankroll=bankroll, peak=bankroll)

    # Sort by prediction time
    sorted_preds = sorted(predictions, key=lambda x: x.get("predicted_at", ""))

    for pred in sorted_preds:
        # Filter by category
        cat = categorize(pred)
        if category_filter and cat != category_filter:
            continue

        # Get model probability for this mechanism
        mechs = pred.get("all_mechanisms", {})
        if mechanism not in mechs:
            continue
        model_prob_pct = mechs[mechanism]
        if model_prob_pct is None:
            continue
        model_prob = model_prob_pct / 100.0  # convert to 0-1

        market_price = pred["market_price_at_prediction"]
        resolution = pred["resolution"]

        # Determine side
        edge = model_prob - market_price
        if abs(edge) < min_edge:
            continue  # edge too small, skip

        if edge > 0:
            side = "YES"
        else:
            side = "NO"

        # Kelly sizing
        kf = kelly_fraction(model_prob, market_price, side)
        kf *= kelly_mult  # apply fractional Kelly
        if kf <= 0:
            continue  # Kelly says don't bet

        bet_size = portfolio.bankroll * kf
        if bet_size <= 0:
            continue

        # Apply friction
        effective_bet = bet_size * (1.0 - friction)

        # P&L calculation
        if side == "YES":
            cost = market_price
            if resolution:
                pnl = effective_bet * (1.0 - cost) / cost  # profit
                win = True
            else:
                pnl = -effective_bet  # lose entire bet
                win = False
        else:  # NO
            cost = 1.0 - market_price
            if not resolution:
                pnl = effective_bet * market_price / (1.0 - market_price)  # profit
                win = True
            else:
                pnl = -effective_bet  # lose entire bet
                win = False

        portfolio.bankroll += pnl
        portfolio.update_drawdown()

        trade = Trade(
            question=pred["question"],
            slug=pred["slug"],
            category=cat,
            side=side,
            model_prob=model_prob,
            market_price=market_price,
            edge=abs(edge),
            kelly_f=kf,
            bet_size=bet_size,
            pnl=pnl,
            resolution=resolution,
            win=win,
            mechanism=mechanism,
            predicted_at=pred.get("predicted_at", ""),
        )
        portfolio.trades.append(trade)

    return portfolio


# --- Reporting ---


def print_portfolio_summary(
    portfolio: Portfolio, label: str, mechanism: str
) -> dict:
    trades = portfolio.trades
    n = len(trades)
    if n == 0:
        print(f"  {label:12s} | {mechanism:22s} | No trades")
        return {}

    wins = sum(1 for t in trades if t.win)
    total_pnl = portfolio.bankroll - portfolio.initial_bankroll
    roi = total_pnl / portfolio.initial_bankroll * 100
    avg_edge = sum(t.edge for t in trades) / n
    avg_pnl = total_pnl / n

    returns = [t.pnl / t.bet_size if t.bet_size > 0 else 0 for t in trades]
    mean_ret = sum(returns) / len(returns)
    if len(returns) > 1:
        var = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_ret = var**0.5
        sharpe = mean_ret / std_ret if std_ret > 0 else 0
    else:
        std_ret = 0
        sharpe = 0

    result = {
        "label": label,
        "mechanism": mechanism,
        "trades": n,
        "wins": wins,
        "win_rate": wins / n * 100,
        "total_pnl": total_pnl,
        "roi": roi,
        "avg_edge": avg_edge,
        "avg_pnl": avg_pnl,
        "sharpe": sharpe,
        "max_drawdown": portfolio.max_drawdown * 100,
        "final_bankroll": portfolio.bankroll,
    }

    print(
        f"  {label:12s} | {mechanism:22s} | "
        f"Trades: {n:3d} | Win: {wins}/{n} ({result['win_rate']:5.1f}%) | "
        f"PnL: ${total_pnl:+8.2f} | ROI: {roi:+6.1f}% | "
        f"Sharpe: {sharpe:+5.2f} | MaxDD: {result['max_drawdown']:5.1f}%"
    )
    return result


def print_trade_log(trades: list[Trade], label: str):
    if not trades:
        return
    print(f"\n  {'─' * 120}")
    print(f"  Trade Log: {label}")
    print(f"  {'─' * 120}")
    print(
        f"  {'#':>3s}  {'Question':<40s}  {'Side':>4s}  {'Model':>6s}  {'Market':>6s}  "
        f"{'Edge':>5s}  {'Kelly%':>6s}  {'Bet':>8s}  {'PnL':>9s}  {'W/L':>3s}"
    )
    print(f"  {'─' * 120}")
    cumulative = 0
    for i, t in enumerate(trades, 1):
        cumulative += t.pnl
        q = t.question[:38] + ".." if len(t.question) > 40 else t.question
        wl = "W" if t.win else "L"
        print(
            f"  {i:3d}  {q:<40s}  {t.side:>4s}  {t.model_prob:6.1%}  {t.market_price:6.1%}  "
            f"{t.edge:5.1%}  {t.kelly_f:6.1%}  ${t.bet_size:7.2f}  ${t.pnl:+8.2f}  {wl:>3s}"
        )
    print(f"  {'─' * 120}")


def main():
    parser = argparse.ArgumentParser(description="DePredict Polymarket Backtest")
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Starting bankroll (default: $1000)")
    parser.add_argument("--kelly-fraction", type=float, default=0.5, help="Kelly multiplier (default: 0.5 = half-Kelly)")
    parser.add_argument("--min-edge", type=float, default=0.0, help="Minimum edge to trade (default: 0.0)")
    parser.add_argument("--friction", type=float, default=0.0, help="Transaction cost fraction (default: 0)")
    parser.add_argument("--show-trades", action="store_true", help="Print individual trade logs")
    parser.add_argument("--mechanisms", nargs="+", default=None, help="Specific mechanisms to test (default: all)")
    args = parser.parse_args()

    # Load data
    with open(DATA_PATH) as f:
        all_preds = json.load(f)
    resolved = [p for p in all_preds if p["status"] == "resolved" and p["resolution"] is not None]
    print(f"Loaded {len(resolved)} resolved predictions\n")

    # Category breakdown
    crypto = [p for p in resolved if is_crypto(p)]
    non_crypto = [p for p in resolved if not is_crypto(p)]
    print(f"  Crypto:     {len(crypto)} predictions")
    print(f"  Non-Crypto: {len(non_crypto)} predictions\n")

    ALL_MECHANISMS = [
        "simple_average", "median", "trimmed_mean", "logit_average",
        "extremized", "reputation_weighted", "lmsr_market",
        "peer_prediction", "hybrid",
    ]
    mechanisms = args.mechanisms or ALL_MECHANISMS

    categories = [
        ("ALL", None),
        ("CRYPTO", "crypto"),
        ("NON-CRYPTO", "non_crypto"),
    ]

    all_results = []

    for cat_label, cat_filter in categories:
        print(f"{'=' * 130}")
        print(f"  Category: {cat_label}  |  Bankroll: ${args.bankroll:.0f}  |  Kelly: {args.kelly_fraction}x  |  Min Edge: {args.min_edge:.1%}  |  Friction: {args.friction:.1%}")
        print(f"{'=' * 130}")

        for mech in mechanisms:
            portfolio = run_backtest(
                resolved,
                mechanism=mech,
                bankroll=args.bankroll,
                kelly_mult=args.kelly_fraction,
                min_edge=args.min_edge,
                friction=args.friction,
                category_filter=cat_filter,
            )
            result = print_portfolio_summary(portfolio, cat_label, mech)
            if result:
                all_results.append(result)

            if args.show_trades and portfolio.trades:
                print_trade_log(portfolio.trades, f"{cat_label} / {mech}")

        print()

    # --- Edge threshold sensitivity ---
    print(f"\n{'=' * 130}")
    print("  EDGE THRESHOLD SENSITIVITY (hybrid, half-Kelly)")
    print(f"{'=' * 130}")
    thresholds = [0.0, 0.03, 0.05, 0.08, 0.10, 0.15]
    for cat_label, cat_filter in categories:
        print(f"\n  >> {cat_label}")
        for thr in thresholds:
            portfolio = run_backtest(
                resolved,
                mechanism="hybrid",
                bankroll=args.bankroll,
                kelly_mult=args.kelly_fraction,
                min_edge=thr,
                friction=args.friction,
                category_filter=cat_filter,
            )
            n = len(portfolio.trades)
            if n == 0:
                print(f"     Edge >= {thr:5.1%}  |  No trades")
                continue
            wins = sum(1 for t in portfolio.trades if t.win)
            pnl = portfolio.bankroll - portfolio.initial_bankroll
            roi = pnl / portfolio.initial_bankroll * 100
            print(
                f"     Edge >= {thr:5.1%}  |  Trades: {n:3d}  |  "
                f"Win: {wins}/{n} ({wins/n*100:5.1f}%)  |  "
                f"PnL: ${pnl:+8.2f}  |  ROI: {roi:+6.1f}%  |  "
                f"MaxDD: {portfolio.max_drawdown*100:5.1f}%"
            )

    # --- Kelly fraction sensitivity ---
    print(f"\n{'=' * 130}")
    print("  KELLY FRACTION SENSITIVITY (hybrid, no min edge)")
    print(f"{'=' * 130}")
    kelly_fracs = [0.1, 0.25, 0.5, 0.75, 1.0]
    for cat_label, cat_filter in categories:
        print(f"\n  >> {cat_label}")
        for kf in kelly_fracs:
            portfolio = run_backtest(
                resolved,
                mechanism="hybrid",
                bankroll=args.bankroll,
                kelly_mult=kf,
                min_edge=args.min_edge,
                friction=args.friction,
                category_filter=cat_filter,
            )
            n = len(portfolio.trades)
            if n == 0:
                print(f"     Kelly {kf:4.2f}x  |  No trades")
                continue
            pnl = portfolio.bankroll - portfolio.initial_bankroll
            roi = pnl / portfolio.initial_bankroll * 100
            print(
                f"     Kelly {kf:4.2f}x  |  Trades: {n:3d}  |  "
                f"PnL: ${pnl:+8.2f}  |  ROI: {roi:+6.1f}%  |  "
                f"Final: ${portfolio.bankroll:8.2f}  |  "
                f"MaxDD: {portfolio.max_drawdown*100:5.1f}%"
            )

    # --- Summary: Best mechanism per category ---
    print(f"\n{'=' * 130}")
    print("  BEST MECHANISM PER CATEGORY (by ROI)")
    print(f"{'=' * 130}")
    for cat_label, _ in categories:
        cat_results = [r for r in all_results if r["label"] == cat_label]
        if not cat_results:
            continue
        best = max(cat_results, key=lambda x: x["roi"])
        worst = min(cat_results, key=lambda x: x["roi"])
        print(
            f"  {cat_label:12s}  |  Best: {best['mechanism']:22s} "
            f"(ROI: {best['roi']:+6.1f}%, Sharpe: {best['sharpe']:+5.2f})  |  "
            f"Worst: {worst['mechanism']:22s} "
            f"(ROI: {worst['roi']:+6.1f}%, Sharpe: {worst['sharpe']:+5.2f})"
        )

    print()


if __name__ == "__main__":
    main()
