"""
Flask Blueprint for Polymarket integration endpoints.

Uses real Polymarket Gamma API via PolymarketClient for live market data,
with in-memory caching to avoid excessive API calls.
"""

import logging
import time

from flask import Blueprint, request, jsonify

from ..services.polymarket_client import PolymarketClient
from ..services.edge_detector import EdgeDetector

logger = logging.getLogger(__name__)

market_bp = Blueprint("market", __name__, url_prefix="/api/market")

# Shared client instances
_polymarket_client = PolymarketClient()
_edge_detector = EdgeDetector(_polymarket_client, min_edge=0.05, min_volume=10000)

# Simple in-memory cache: key -> (timestamp, data)
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 60  # seconds


def _get_cached(key: str):
    """Return cached value if still valid, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _set_cached(key: str, data):
    """Store a value in the cache."""
    _cache[key] = (time.monotonic(), data)


@market_bp.route("/active", methods=["GET"])
def get_active_markets():
    """
    Get list of active Polymarket markets.

    Query params:
        category (optional): Filter by category/tag (crypto, politics, sports, etc.)
        limit (optional): Max number of markets to return (default 50, max 100)

    Returns: { markets: [...], total: int, source: "polymarket" }
    """
    category = request.args.get("category")
    limit = request.args.get("limit", 50, type=int)
    limit = min(max(limit, 1), 100)

    cache_key = f"active:{category or 'all'}:{limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return jsonify(cached)

    markets = _polymarket_client.get_active_markets(category=category, limit=limit)

    response_data = {
        "markets": markets,
        "total": len(markets),
        "source": "polymarket",
    }
    _set_cached(cache_key, response_data)

    return jsonify(response_data)


@market_bp.route("/search", methods=["GET"])
def search_markets():
    """
    Search markets by keyword.

    Query params:
        q (required): Search query string
        limit (optional): Max results (default 20)

    Returns: { markets: [...], total: int, query: str }
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "query parameter 'q' is required"}), 400

    limit = request.args.get("limit", 20, type=int)
    limit = min(max(limit, 1), 100)

    markets = _polymarket_client.search_markets(query, limit=limit)

    return jsonify({
        "markets": markets,
        "total": len(markets),
        "query": query,
        "source": "polymarket",
    })


@market_bp.route("/<slug>/price", methods=["GET"])
def get_market_price(slug: str):
    """
    Get current price for a specific market by slug.

    Returns: normalized market dict with current prices.
    """
    cache_key = f"slug:{slug}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return jsonify(cached)

    market = _polymarket_client.get_market_by_slug(slug)
    if market is None:
        return jsonify({"error": f"market '{slug}' not found"}), 404

    _set_cached(cache_key, market)
    return jsonify(market)


@market_bp.route("/id/<condition_id>", methods=["GET"])
def get_market_by_id(condition_id: str):
    """
    Get a single market by its condition_id.

    Returns: normalized market dict.
    """
    cache_key = f"cid:{condition_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return jsonify(cached)

    market = _polymarket_client.get_market(condition_id)
    if market is None:
        return jsonify({"error": f"market '{condition_id}' not found"}), 404

    _set_cached(cache_key, market)
    return jsonify(market)


@market_bp.route("/scan", methods=["GET"])
def scan_edges():
    """
    Return active markets ensuring every category has representation.

    Fetches multiple pages from Polymarket (up to 300 markets), auto-classifies
    them, then picks the top markets from each category so every tab has content.

    Query params:
        min_volume (optional): Minimum 24h volume filter (default 5000)
        per_category (optional): Min markets per category (default 5)
    """
    min_volume = request.args.get("min_volume", 1000, type=float)
    per_category = request.args.get("per_category", 5, type=int)

    cache_key = f"scan:diverse:{min_volume}:{per_category}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return jsonify(cached)

    # Fetch multiple pages + different sort orders for category diversity
    all_markets = []
    seen_slugs: set[str] = set()

    def _add_batch(batch: list[dict]):
        for m in batch:
            slug = m.get("slug", "")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                all_markets.append(m)

    # Page 1-3 by volume
    for offset in (0, 100, 200):
        try:
            batch = _polymarket_client.get_active_markets(
                limit=100, offset=offset, order="volume24hr",
            )
            if not batch:
                break
            _add_batch(batch)
        except Exception:
            break

    # Additional fetch by liquidity to find different markets
    try:
        _add_batch(_polymarket_client.get_active_markets(
            limit=100, order="liquidity",
        ))
    except Exception:
        pass

    # Filter by minimum volume
    all_markets = [m for m in all_markets if m.get("volume_24h", 0) >= min_volume]

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for m in all_markets:
        cat = m.get("category", "Other") or "Other"
        by_category.setdefault(cat, []).append(m)

    # Sort each category by volume descending
    for cat in by_category:
        by_category[cat].sort(key=lambda m: m.get("volume_24h", 0), reverse=True)

    # Build final list: ensure at least `per_category` from each, fill rest by volume
    selected_slugs = set()
    final_markets = []

    # First pass: pick top N from each category
    for cat, cat_markets in by_category.items():
        for m in cat_markets[:per_category]:
            slug = m.get("slug", "")
            if slug not in selected_slugs:
                selected_slugs.add(slug)
                final_markets.append(m)

    # Second pass: fill with remaining top-volume markets
    remaining = [m for m in all_markets if m.get("slug", "") not in selected_slugs]
    remaining.sort(key=lambda m: m.get("volume_24h", 0), reverse=True)
    for m in remaining[:50]:
        selected_slugs.add(m.get("slug", ""))
        final_markets.append(m)

    # Final sort by volume
    final_markets.sort(key=lambda m: m.get("volume_24h", 0), reverse=True)

    # Category summary for frontend
    cat_counts = {}
    for m in final_markets:
        cat = m.get("category", "Other")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    response_data = {
        "markets": final_markets,
        "total": len(final_markets),
        "categories": cat_counts,
        "source": "polymarket",
    }
    _set_cached(cache_key, response_data)

    return jsonify(response_data)


@market_bp.route("/edge", methods=["POST"])
def compute_edge():
    """
    Compute edge for a single market given a completed debate result.

    This is called after a debate finishes to compare model vs market.

    Body: {
        "debate_result": dict,    # Full result from debate pipeline
        "market_price": float,    # Current market YES price (0-1)
        "condition_id": str,      # Optional
        "slug": str,              # Optional
        "question": str,          # Optional
        "category": str,          # Optional
        "volume_24h": float,      # Optional
        "liquidity": float,       # Optional
    }

    Returns: edge dict or { "edge": null } if below threshold.
    """
    data = request.get_json(force=True)

    debate_result = data.get("debate_result")
    market_price = data.get("market_price")

    if debate_result is None or market_price is None:
        return jsonify({
            "error": "debate_result and market_price are required",
        }), 400

    try:
        market_price = float(market_price)
    except (ValueError, TypeError):
        return jsonify({"error": "market_price must be a number"}), 400

    edge = _edge_detector.detect_edge(
        debate_result=debate_result,
        market_price=market_price,
        condition_id=data.get("condition_id", ""),
        slug=data.get("slug", ""),
        question=data.get("question", ""),
        category=data.get("category", ""),
        volume_24h=data.get("volume_24h", 0),
        liquidity=data.get("liquidity", 0),
    )

    if edge is None:
        return jsonify({
            "edge": None,
            "message": f"No significant edge detected (threshold: {_edge_detector.min_edge*100:.0f}%)",
        })

    return jsonify({"edge": edge.to_dict()})
