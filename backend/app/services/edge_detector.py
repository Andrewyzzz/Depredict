"""
Edge detection service for prediction markets.

Compares model probabilities (from the debate pipeline) to market prices
to identify mispriced markets where the model disagrees with the crowd.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Edge:
    """Represents a detected edge between model probability and market price."""

    condition_id: str
    slug: str
    question: str
    category: str
    market_price: float        # Polymarket price (0-1)
    model_probability: float   # Our model's probability (0-1)
    edge: float               # model - market (positive = market underprices YES)
    abs_edge: float
    confidence: str           # "high", "medium", "low" based on mechanism agreement
    mechanisms: dict           # {method_name: probability} from aggregation
    volume_24h: float
    liquidity: float

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "condition_id": self.condition_id,
            "slug": self.slug,
            "question": self.question,
            "category": self.category,
            "market_price": round(self.market_price, 4),
            "model_probability": round(self.model_probability, 4),
            "edge": round(self.edge, 4),
            "abs_edge": round(self.abs_edge, 4),
            "direction": "underpriced" if self.edge > 0 else "overpriced",
            "confidence": self.confidence,
            "mechanisms": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in self.mechanisms.items()
            },
            "volume_24h": self.volume_24h,
            "liquidity": self.liquidity,
        }


class EdgeDetector:
    """Detects edges between model probabilities and market prices.

    Compares the debate pipeline's aggregated probability against live
    Polymarket prices to find potentially mispriced markets.
    """

    # All 9 aggregation mechanisms from the MechAgg framework
    MECHANISM_NAMES = [
        "simple_average",
        "median",
        "trimmed_mean",
        "bayesian",
        "extremize",
        "surprise",
        "meta_weight",
        "coherent",
        "hybrid",
    ]

    def __init__(self, polymarket_client, min_edge: float = 0.05, min_volume: float = 10000):
        """
        Args:
            polymarket_client: PolymarketClient instance for fetching market data.
            min_edge: Minimum absolute edge to report (default 5%).
            min_volume: Minimum 24h volume to consider a market.
        """
        self.polymarket_client = polymarket_client
        self.min_edge = min_edge
        self.min_volume = min_volume

    def scan_category(
        self,
        category: str,
        task_manager=None,
    ) -> list[Edge]:
        """Scan all active markets in a category for edges.

        WARNING: This is expensive -- it runs the full debate pipeline for
        each qualifying market. Use sparingly and provide progress updates.

        Args:
            category: Market category to scan (e.g. "crypto", "politics").
            task_manager: Optional TaskManager for progress updates.

        Returns:
            List of Edge objects for markets where |edge| >= min_edge.
        """
        from ..core.debate_pipeline import DebatePipeline

        markets = self.polymarket_client.get_active_markets(category=category, limit=50)

        # Filter by minimum volume
        markets = [m for m in markets if m.get("volume_24h", 0) >= self.min_volume]

        logger.info(
            "Scanning %d markets in category '%s' (min_volume=%s)",
            len(markets), category, self.min_volume,
        )

        edges: list[Edge] = []
        pipeline = DebatePipeline()

        for i, market in enumerate(markets):
            question = market["question"]
            market_price = market["market_price"]
            slug = market.get("slug", "")

            logger.info(
                "[%d/%d] Analyzing: %s (market=%.2f)",
                i + 1, len(markets), question, market_price,
            )

            if task_manager:
                pct = int((i / max(len(markets), 1)) * 100)
                task_manager_msg = f"Analyzing market {i+1}/{len(markets)}: {question[:60]}..."

            try:
                result = pipeline.run(question, market_price=market_price)
                edge = self.detect_edge(
                    debate_result=result,
                    market_price=market_price,
                    condition_id=market.get("condition_id", ""),
                    slug=slug,
                    question=question,
                    category=market.get("category", category),
                    volume_24h=market.get("volume_24h", 0),
                    liquidity=market.get("liquidity", 0),
                )
                if edge is not None:
                    edges.append(edge)
                    logger.info(
                        "  Edge found: %.1f%% (%s confidence)",
                        edge.edge * 100, edge.confidence,
                    )

            except Exception:
                logger.exception("  Failed to analyze market: %s", slug)
                continue

        return self.rank_edges(edges)

    def detect_edge(
        self,
        debate_result: dict,
        market_price: float,
        condition_id: str = "",
        slug: str = "",
        question: str = "",
        category: str = "",
        volume_24h: float = 0,
        liquidity: float = 0,
    ) -> Optional[Edge]:
        """Compute edge from a completed debate result and market price.

        Uses the hybrid mechanism probability as the primary signal and
        checks mechanism agreement for confidence level.

        Args:
            debate_result: Full result dict from DebatePipeline.run().
            market_price: Current Polymarket YES price (0-1).
            condition_id: Market condition ID.
            slug: Market URL slug.
            question: Market question text.
            category: Market category.
            volume_24h: 24h trading volume.
            liquidity: Available liquidity.

        Returns:
            Edge object if |edge| >= min_edge, else None.
        """
        mechanisms_data = debate_result.get("aggregation_mechanisms", {})

        # Extract hybrid probability (primary signal)
        # Pipeline returns probabilities on 0-100 scale
        hybrid_data = mechanisms_data.get("hybrid", {})
        hybrid_prob_100 = hybrid_data.get("probability")

        if hybrid_prob_100 is None:
            # Fallback to aggregated_probability if hybrid not available
            hybrid_prob_100 = debate_result.get("aggregated_probability")

        if hybrid_prob_100 is None:
            logger.warning("No hybrid or aggregated probability in debate result")
            return None

        # Convert from 0-100 to 0-1 scale
        model_probability = float(hybrid_prob_100) / 100.0
        model_probability = max(0.0, min(1.0, model_probability))  # clamp

        # Compute edge
        edge_value = model_probability - market_price

        # Check minimum edge threshold
        if abs(edge_value) < self.min_edge:
            return None

        # Extract all mechanism probabilities (convert 0-100 to 0-1)
        mechanism_probs: dict[str, float] = {}
        for name in self.MECHANISM_NAMES:
            mech = mechanisms_data.get(name, {})
            prob = mech.get("probability")
            if prob is not None:
                mechanism_probs[name] = float(prob) / 100.0

        # Determine confidence based on mechanism agreement
        confidence = self._compute_confidence(mechanism_probs, model_probability)

        return Edge(
            condition_id=condition_id,
            slug=slug,
            question=question or debate_result.get("question", ""),
            category=category,
            market_price=round(market_price, 4),
            model_probability=round(model_probability, 4),
            edge=round(edge_value, 4),
            abs_edge=round(abs(edge_value), 4),
            confidence=confidence,
            mechanisms=mechanism_probs,
            volume_24h=volume_24h,
            liquidity=liquidity,
        )

    def rank_edges(self, edges: list[Edge]) -> list[Edge]:
        """Sort edges by composite score: abs_edge * confidence_weight * log(volume).

        Higher scores indicate more attractive opportunities (large edge,
        high confidence, liquid market).

        Args:
            edges: List of Edge objects.

        Returns:
            Sorted list (highest score first).
        """
        def _score(e: Edge) -> float:
            conf_w = self._confidence_weight(e.confidence)
            # Use log(volume + 1) to avoid log(0); add 1 for safety
            vol_factor = math.log(max(e.volume_24h, 1) + 1)
            return e.abs_edge * conf_w * vol_factor

        return sorted(edges, key=_score, reverse=True)

    def _compute_confidence(
        self,
        mechanism_probs: dict[str, float],
        hybrid_prob: float,
    ) -> str:
        """Determine confidence level from mechanism agreement.

        Checks how many of the available mechanisms agree with the hybrid
        probability on direction (same side of 0.5).

        Args:
            mechanism_probs: {mechanism_name: probability} on 0-1 scale.
            hybrid_prob: The hybrid mechanism probability on 0-1 scale.

        Returns:
            "high", "medium", or "low".
        """
        if not mechanism_probs:
            return "low"

        hybrid_side = hybrid_prob >= 0.5  # True = YES side

        agree_count = 0
        total_count = 0
        for name, prob in mechanism_probs.items():
            total_count += 1
            mech_side = prob >= 0.5
            if mech_side == hybrid_side:
                agree_count += 1

        # Scale thresholds based on available mechanisms (up to 9)
        # Original thresholds: 7+ = high, 5-6 = medium, <5 = low (out of 9)
        if total_count == 0:
            return "low"

        agreement_ratio = agree_count / total_count

        if agreement_ratio >= 7 / 9:  # ~78%
            return "high"
        elif agreement_ratio >= 5 / 9:  # ~56%
            return "medium"
        else:
            return "low"

    @staticmethod
    def _confidence_weight(confidence: str) -> float:
        """Map confidence level to numeric weight for scoring.

        Returns:
            1.0 for high, 0.6 for medium, 0.3 for low.
        """
        return {"high": 1.0, "medium": 0.6, "low": 0.3}.get(confidence, 0.3)
