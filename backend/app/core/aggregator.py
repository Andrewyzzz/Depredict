"""
Aggregation mechanisms for multi-agent prediction systems.

Implements four mechanisms with increasing sophistication:
  M1: Reputation-Weighted Aggregation
  M2: LMSR Prediction Market
  M3: Peer Prediction (Bayesian Truth Serum)
  M4: Hybrid Mechanism (M1 + M2 + M3)

Each mechanism takes agent predictions and returns an aggregated probability.
"""

import math
import statistics
from dataclasses import dataclass, field


@dataclass
class AgentRecord:
    """Tracks an agent's historical performance for reputation scoring."""
    name: str
    reputation: float = 1.0
    total_questions: int = 0
    cumulative_brier: float = 0.0
    brier_history: list[float] = field(default_factory=list)


class ReputationTracker:
    """
    Maintains and updates agent reputations based on historical Brier Scores.

    Reputation update rule:
        r_i ← α * r_i + (1 - α) * (1 - BS_i)

    where BS_i is the Brier Score for agent i on the latest question.
    Higher reputation = better historical performance.
    """

    def __init__(self, agent_names: list[str], decay: float = 0.7):
        """
        Args:
            agent_names: List of agent names to track.
            decay: Exponential decay factor α. Higher = more weight on history.
        """
        self.decay = decay
        self.records: dict[str, AgentRecord] = {
            name: AgentRecord(name=name) for name in agent_names
        }

    def update(self, agent_name: str, brier_score: float):
        """Update an agent's reputation after observing a resolved question."""
        record = self.records[agent_name]
        performance = 1.0 - brier_score  # Higher is better
        record.reputation = self.decay * record.reputation + (1 - self.decay) * performance
        record.total_questions += 1
        record.cumulative_brier += brier_score
        record.brier_history.append(brier_score)

    def get_weights(self) -> dict[str, float]:
        """Return normalized reputation weights (sum to 1)."""
        total = sum(r.reputation for r in self.records.values())
        if total == 0:
            n = len(self.records)
            return {name: 1.0 / n for name in self.records}
        return {name: r.reputation / total for name, r in self.records.items()}

    def get_reputation(self, agent_name: str) -> float:
        return self.records[agent_name].reputation

    def snapshot(self) -> dict:
        """Return a serializable snapshot of all reputations."""
        return {
            name: {
                "reputation": round(r.reputation, 4),
                "total_questions": r.total_questions,
                "avg_brier": round(r.cumulative_brier / r.total_questions, 4)
                if r.total_questions > 0 else None,
            }
            for name, r in self.records.items()
        }


# ── M1: Reputation-Weighted Aggregation ────────────────────────────────────


def aggregate_reputation_weighted(
    predictions: list[dict],
    weights: dict[str, float],
) -> dict:
    """
    M1: Weighted average using reputation scores.

    Args:
        predictions: List of dicts with 'agent_name' and 'probability' keys.
        weights: Dict mapping agent_name -> weight (should sum to ~1).

    Returns:
        Dict with aggregated probability and per-agent weight details.
    """
    valid = [(p, weights.get(p["agent_name"], 0)) for p in predictions
             if p.get("probability") is not None]

    if not valid:
        return {"probability": None, "method": "reputation_weighted", "details": {}}

    # Re-normalize weights for valid agents only
    total_w = sum(w for _, w in valid)
    if total_w == 0:
        total_w = len(valid)
        valid = [(p, 1.0) for p, _ in valid]

    weighted_sum = sum(p["probability"] * w / total_w for p, w in valid)

    return {
        "probability": round(weighted_sum, 2),
        "method": "reputation_weighted",
        "details": {
            p["agent_name"]: {
                "prediction": p["probability"],
                "weight": round(w / total_w, 4),
            }
            for p, w in valid
        },
    }


# ── M2: LMSR Prediction Market ────────────────────────────────────────────


class LMSRMarket:
    """
    Logarithmic Market Scoring Rule (LMSR) prediction market.

    Hanson's LMSR provides:
      - Bounded loss for the market maker
      - Always-available liquidity
      - Information aggregation through trading

    Cost function: C(q) = b * ln(e^(q_yes/b) + e^(q_no/b))
    Price:         P(yes) = e^(q_yes/b) / (e^(q_yes/b) + e^(q_no/b))

    Each agent trades based on their belief vs current market price.
    """

    def __init__(self, liquidity: float = 100.0, initial_price: float = 0.5):
        """
        Args:
            liquidity: LMSR liquidity parameter b. Higher = less price impact per trade.
            initial_price: Starting market probability.
        """
        self.b = liquidity
        # Initialize quantities from initial price
        # P(yes) = initial_price => q_yes/b - q_no/b = ln(p/(1-p))
        log_odds = math.log(initial_price / (1 - initial_price)) if 0 < initial_price < 1 else 0
        self.q_yes = self.b * log_odds / 2
        self.q_no = -self.b * log_odds / 2
        self.trade_history: list[dict] = []

    def price(self) -> float:
        """Current market price for YES outcome."""
        exp_yes = math.exp(self.q_yes / self.b)
        exp_no = math.exp(self.q_no / self.b)
        return exp_yes / (exp_yes + exp_no)

    def cost(self) -> float:
        """Current cost function value."""
        return self.b * math.log(
            math.exp(self.q_yes / self.b) + math.exp(self.q_no / self.b)
        )

    def trade(self, agent_name: str, belief: float, budget: float) -> dict:
        """
        Agent trades based on divergence between belief and market price.

        Trading strategy: Kelly-criterion inspired sizing.
        Agent buys YES shares if belief > market price, NO shares otherwise.
        Trade size proportional to |belief - market_price| * budget.

        Args:
            agent_name: Name of the trading agent.
            belief: Agent's probability estimate (0-1 scale).
            budget: Agent's available budget for this trade.

        Returns:
            Dict with trade details.
        """
        current_price = self.price()
        edge = belief - current_price

        # Kelly-inspired: stake proportional to edge
        # Cap at 80% of budget to avoid degenerate cases
        stake = min(abs(edge) * budget, budget * 0.8)

        if abs(edge) < 0.01:
            # No meaningful edge, skip trade
            return {
                "agent_name": agent_name,
                "action": "hold",
                "shares": 0,
                "cost": 0,
                "price_before": current_price,
                "price_after": current_price,
            }

        cost_before = self.cost()

        if edge > 0:
            # Buy YES shares
            # Find delta_q such that cost change = stake
            delta_q = self._solve_delta(stake, direction="yes")
            self.q_yes += delta_q
            action = "buy_yes"
        else:
            # Buy NO shares
            delta_q = self._solve_delta(stake, direction="no")
            self.q_no += delta_q
            action = "buy_no"

        cost_after = self.cost()
        actual_cost = cost_after - cost_before
        new_price = self.price()

        trade_record = {
            "agent_name": agent_name,
            "action": action,
            "belief": belief,
            "shares": round(delta_q, 4),
            "cost": round(actual_cost, 4),
            "price_before": round(current_price, 4),
            "price_after": round(new_price, 4),
            "edge": round(edge, 4),
        }
        self.trade_history.append(trade_record)
        return trade_record

    def _solve_delta(self, target_cost: float, direction: str, tol: float = 0.01) -> float:
        """
        Binary search for share quantity that costs approximately target_cost.

        Args:
            target_cost: Desired cost of the trade.
            direction: 'yes' or 'no'.
            tol: Tolerance for cost matching.

        Returns:
            Number of shares to buy.
        """
        lo, hi = 0.0, self.b * 10  # Upper bound on shares

        for _ in range(100):
            mid = (lo + hi) / 2
            # Simulate the trade
            if direction == "yes":
                new_cost = self.b * math.log(
                    math.exp((self.q_yes + mid) / self.b) + math.exp(self.q_no / self.b)
                )
            else:
                new_cost = self.b * math.log(
                    math.exp(self.q_yes / self.b) + math.exp((self.q_no + mid) / self.b)
                )

            current_cost = self.cost()
            cost_diff = new_cost - current_cost

            if abs(cost_diff - target_cost) < tol:
                return mid
            elif cost_diff < target_cost:
                lo = mid
            else:
                hi = mid

        return (lo + hi) / 2


def aggregate_lmsr(
    predictions: list[dict],
    budgets: dict[str, float] | None = None,
    liquidity: float = 100.0,
) -> dict:
    """
    M2: LMSR prediction market aggregation.

    Agents trade in the market based on their beliefs. Final market price
    is the aggregated probability.

    The initial market price is set to the median agent prediction (not 50%),
    so the market starts from a reasonable anchor and agents trade to adjust.

    Args:
        predictions: List of dicts with 'agent_name' and 'probability'.
        budgets: Optional dict of agent budgets. Defaults to equal budgets.
        liquidity: LMSR liquidity parameter.

    Returns:
        Dict with final market price and trade history.
    """
    valid = [p for p in predictions if p.get("probability") is not None]
    if not valid:
        return {"probability": None, "method": "lmsr_market", "details": {}}

    # Default: equal budgets
    if budgets is None:
        budgets = {p["agent_name"]: 100.0 for p in valid}

    # Use median prediction as initial price (avoids 50% anchor bias)
    beliefs = sorted(p["probability"] / 100.0 for p in valid)
    initial_price = beliefs[len(beliefs) // 2]
    initial_price = max(0.01, min(0.99, initial_price))  # Clamp to avoid log(0)

    market = LMSRMarket(liquidity=liquidity, initial_price=initial_price)

    # Each agent trades once based on their Round 3 prediction
    for pred in valid:
        belief = pred["probability"] / 100.0  # Convert to 0-1 scale
        budget = budgets.get(pred["agent_name"], 100.0)
        market.trade(pred["agent_name"], belief, budget)

    final_price = market.price()

    return {
        "probability": round(final_price * 100, 2),  # Convert back to 0-100 scale
        "method": "lmsr_market",
        "details": {
            "liquidity": liquidity,
            "trade_history": market.trade_history,
            "initial_price": 50.0,
            "final_price": round(final_price * 100, 4),
        },
    }


# ── M3: Peer Prediction (Bayesian Truth Serum) ────────────────────────────


def aggregate_peer_prediction(
    predictions: list[dict],
    meta_predictions: dict[str, float] | None = None,
) -> dict:
    """
    M3: Bayesian Truth Serum (BTS) aggregation.

    Each agent provides:
      1. Their own prediction p_i
      2. A meta-prediction m_i: what they think the average prediction will be

    BTS score rewards agents who are "surprisingly common":
      score_i = ln(p_i / geometric_mean(p_j)) + information_score(m_i)

    The information score rewards agents whose meta-predictions are accurate,
    indicating they understand the information landscape.

    Agents with higher BTS scores get more weight in the final aggregation.

    Args:
        predictions: List of dicts with 'agent_name' and 'probability'.
        meta_predictions: Dict mapping agent_name -> predicted average (0-100).
                         If None, falls back to simple average.

    Returns:
        Dict with BTS-weighted probability and score details.
    """
    valid = [p for p in predictions if p.get("probability") is not None]
    if not valid:
        return {"probability": None, "method": "peer_prediction", "details": {}}

    probs_01 = {p["agent_name"]: p["probability"] / 100.0 for p in valid}
    actual_avg = statistics.mean(probs_01.values())

    if meta_predictions is None:
        # No meta-predictions available, fall back to simple average
        return {
            "probability": round(actual_avg * 100, 2),
            "method": "peer_prediction",
            "details": {"note": "no meta-predictions, used simple average"},
        }

    # Calculate BTS scores
    scores = {}
    eps = 1e-6  # Avoid log(0)

    for pred in valid:
        name = pred["agent_name"]
        p_i = probs_01[name]

        # Geometric mean of others' predictions
        others = [v for k, v in probs_01.items() if k != name]
        if others:
            log_geo_mean = statistics.mean(math.log(max(v, eps)) for v in others)
            geo_mean = math.exp(log_geo_mean)
        else:
            geo_mean = 0.5

        # Information score: how well did agent predict the average?
        meta_pred = meta_predictions.get(name, actual_avg * 100) / 100.0
        meta_error = abs(meta_pred - actual_avg)
        information_score = 1.0 - meta_error  # Simple: closer to actual avg = better

        # BTS score: surprisingness + information quality
        surprisingness = math.log(max(p_i, eps) / max(geo_mean, eps))
        bts_score = surprisingness + information_score

        scores[name] = {
            "prediction": p_i,
            "meta_prediction": meta_pred,
            "surprisingness": round(surprisingness, 4),
            "information_score": round(information_score, 4),
            "bts_score": round(bts_score, 4),
        }

    # Convert BTS scores to weights using softmax
    bts_values = {name: s["bts_score"] for name, s in scores.items()}
    max_bts = max(bts_values.values())
    exp_scores = {name: math.exp(v - max_bts) for name, v in bts_values.items()}
    total_exp = sum(exp_scores.values())
    weights = {name: v / total_exp for name, v in exp_scores.items()}

    # Weighted aggregation
    weighted_prob = sum(probs_01[name] * w for name, w in weights.items())

    # Add weights to score details
    for name in scores:
        scores[name]["weight"] = round(weights[name], 4)

    return {
        "probability": round(weighted_prob * 100, 2),
        "method": "peer_prediction",
        "details": {
            "actual_average": round(actual_avg * 100, 2),
            "agent_scores": scores,
        },
    }


# ── M4: Hybrid Mechanism ──────────────────────────────────────────────────


def aggregate_hybrid(
    predictions: list[dict],
    reputation_weights: dict[str, float],
    meta_predictions: dict[str, float] | None = None,
    lmsr_liquidity: float = 100.0,
    lambda_market: float = 0.4,
    lambda_reputation: float = 0.3,
    lambda_bts: float = 0.3,
) -> dict:
    """
    M4: Hybrid mechanism combining M1 + M2 + M3.

    Final prediction:
      P = λ1 * P_market + λ2 * P_reputation + λ3 * P_bts

    The hybrid uses:
      - M3 (BTS) to estimate agent quality without ground truth
      - M1 reputation (from historical data) for long-term calibration
      - M2 (LMSR) for information aggregation with market dynamics

    Budget allocation in LMSR is informed by reputation:
      budget_i = base_budget * (1 + reputation_weight_i)

    Args:
        predictions: Agent predictions.
        reputation_weights: From ReputationTracker.
        meta_predictions: For BTS scoring.
        lmsr_liquidity: LMSR liquidity parameter.
        lambda_market: Weight for LMSR component.
        lambda_reputation: Weight for reputation-weighted component.
        lambda_bts: Weight for BTS component.

    Returns:
        Dict with hybrid probability and component details.
    """
    # M1: Reputation-weighted
    m1_result = aggregate_reputation_weighted(predictions, reputation_weights)

    # M2: LMSR with reputation-informed budgets
    budgets = {
        name: 100.0 * (1 + w)
        for name, w in reputation_weights.items()
    }
    m2_result = aggregate_lmsr(predictions, budgets=budgets, liquidity=lmsr_liquidity)

    # M3: Peer prediction
    m3_result = aggregate_peer_prediction(predictions, meta_predictions)

    # Combine
    components = {
        "reputation_weighted": m1_result.get("probability"),
        "lmsr_market": m2_result.get("probability"),
        "peer_prediction": m3_result.get("probability"),
    }

    valid_components = {k: v for k, v in components.items() if v is not None}

    if not valid_components:
        return {"probability": None, "method": "hybrid", "details": {}}

    # Weighted combination (re-normalize if some components are missing)
    weight_map = {
        "reputation_weighted": lambda_reputation,
        "lmsr_market": lambda_market,
        "peer_prediction": lambda_bts,
    }

    total_lambda = sum(weight_map[k] for k in valid_components)
    hybrid_prob = sum(
        v * weight_map[k] / total_lambda
        for k, v in valid_components.items()
    )

    return {
        "probability": round(hybrid_prob, 2),
        "method": "hybrid",
        "details": {
            "components": components,
            "lambdas": {
                "market": lambda_market,
                "reputation": lambda_reputation,
                "bts": lambda_bts,
            },
            "m1_details": m1_result.get("details", {}),
            "m2_details": m2_result.get("details", {}),
            "m3_details": m3_result.get("details", {}),
        },
    }


# ── Simple Average Baseline ───────────────────────────────────────────────


def aggregate_simple_average(predictions: list[dict]) -> dict:
    """Baseline: simple arithmetic mean (existing method)."""
    valid = [p["probability"] for p in predictions if p.get("probability") is not None]
    if not valid:
        return {"probability": None, "method": "simple_average", "details": {}}

    return {
        "probability": round(statistics.mean(valid), 2),
        "method": "simple_average",
        "details": {"n_agents": len(valid)},
    }


# ── Extremized Average ────────────────────────────────────────────────────


def aggregate_extremized(predictions: list[dict], d: float = 2.5) -> dict:
    """
    Extremized average: push aggregate away from 50% to correct for
    information underweighting in simple averages.

    Formula: p_ext = p_avg^d / (p_avg^d + (1-p_avg)^d)

    Recommended d ≈ 2.5 based on forecasting literature (Baron et al., 2014).

    Args:
        predictions: Agent predictions.
        d: Extremization parameter. d > 1 pushes away from 50%.
    """
    valid = [p["probability"] / 100.0 for p in predictions
             if p.get("probability") is not None]
    if not valid:
        return {"probability": None, "method": "extremized", "details": {}}

    avg = statistics.mean(valid)

    # Extremize
    eps = 1e-10
    avg_clamped = max(eps, min(1 - eps, avg))
    numerator = avg_clamped ** d
    denominator = avg_clamped ** d + (1 - avg_clamped) ** d
    extremized = numerator / denominator

    return {
        "probability": round(extremized * 100, 2),
        "method": "extremized",
        "details": {
            "raw_average": round(avg * 100, 2),
            "extremization_d": d,
        },
    }


# ── Median Aggregation ──────────────────────────────────────────────────


def aggregate_median(predictions: list[dict]) -> dict:
    """Median aggregation: robust to outlier agents."""
    valid = [p["probability"] for p in predictions if p.get("probability") is not None]
    if not valid:
        return {"probability": None, "method": "median", "details": {}}

    return {
        "probability": round(statistics.median(valid), 2),
        "method": "median",
        "details": {"n_agents": len(valid)},
    }


# ── Logit (Log-Odds) Average ────────────────────────────────────────────


def aggregate_logit_average(predictions: list[dict]) -> dict:
    """
    Log-odds averaging (Satopaa et al., 2014).

    Transform each p_i to log-odds, average, transform back.
    Theoretically motivated: equivalent to geometric opinion pooling.
    """
    valid = [p["probability"] / 100.0 for p in predictions
             if p.get("probability") is not None]
    if not valid:
        return {"probability": None, "method": "logit_average", "details": {}}

    eps = 1e-6
    log_odds = [math.log(max(p, eps) / max(1 - p, eps)) for p in valid]
    avg_log_odds = statistics.mean(log_odds)
    prob = 1.0 / (1.0 + math.exp(-avg_log_odds))

    return {
        "probability": round(prob * 100, 2),
        "method": "logit_average",
        "details": {
            "avg_log_odds": round(avg_log_odds, 4),
            "n_agents": len(valid),
        },
    }


# ── Trimmed Mean ────────────────────────────────────────────────────────


def aggregate_trimmed_mean(predictions: list[dict], trim_frac: float = 0.1) -> dict:
    """
    Trimmed mean: remove top and bottom trim_frac of predictions, then average.

    Default trims 10% from each end (removes 1 agent from each side with N=10).
    """
    valid = sorted(
        p["probability"] for p in predictions if p.get("probability") is not None
    )
    if not valid:
        return {"probability": None, "method": "trimmed_mean", "details": {}}

    n = len(valid)
    trim_count = max(1, int(n * trim_frac))
    trimmed = valid[trim_count: n - trim_count]
    if not trimmed:
        trimmed = valid  # fallback if too few

    return {
        "probability": round(statistics.mean(trimmed), 2),
        "method": "trimmed_mean",
        "details": {
            "n_original": n,
            "n_trimmed": len(trimmed),
            "trim_frac": trim_frac,
        },
    }


# ── Single Best Agent (Oracle) ──────────────────────────────────────────


def get_oracle_single_agent(
    all_results: list[dict],
    actuals: list[bool],
) -> dict:
    """
    Oracle baseline: find the single agent with lowest cumulative Brier Score.

    This is a post-hoc oracle (not a real method), used to show that
    aggregation beats even the best individual agent.

    Args:
        all_results: List of per-question result dicts (each containing rounds.round3).
        actuals: List of actual outcomes corresponding to each result.

    Returns:
        Dict with best agent name, their predictions, and Brier score.
    """
    agent_briers: dict[str, list[float]] = {}
    agent_preds: dict[str, list[float]] = {}

    for result, actual in zip(all_results, actuals):
        round3 = result.get("rounds", {}).get("round3", [])
        outcome = 1.0 if actual else 0.0
        for agent_result in round3:
            name = agent_result.get("agent_name")
            prob = agent_result.get("probability")
            if name and prob is not None:
                p = prob / 100.0
                bs = (p - outcome) ** 2
                agent_briers.setdefault(name, []).append(bs)
                agent_preds.setdefault(name, []).append(p)

    if not agent_briers:
        return {"agent": None, "brier": float("nan"), "predictions": []}

    avg_briers = {name: statistics.mean(scores) for name, scores in agent_briers.items()}
    best_agent = min(avg_briers, key=avg_briers.get)

    return {
        "agent": best_agent,
        "brier": avg_briers[best_agent],
        "predictions": agent_preds[best_agent],
        "all_agent_briers": {name: round(b, 6) for name, b in sorted(avg_briers.items(), key=lambda x: x[1])},
    }
