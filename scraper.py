"""
Manifold Markets data scraper for building evaluation datasets.

Fetches resolved binary prediction markets across multiple categories
for use in aggregation mechanism experiments.

Usage:
    python scraper.py                    # Fetch and save questions
    python scraper.py --min-volume 1000  # Filter by minimum volume
"""

import argparse
import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime

from config import DATA_DIR

MANIFOLD_API = "https://api.manifold.markets/v0"

# Search terms for diverse categories
SEARCH_QUERIES = {
    "politics": [
        "president election 2024",
        "Trump policy 2025",
        "government shutdown",
        "Supreme Court ruling",
        "NATO Russia Ukraine",
    ],
    "ai_tech": [
        "GPT-5 OpenAI model",
        "AI benchmark score",
        "Anthropic Claude",
        "LLM release 2025",
        "AGI artificial intelligence",
    ],
    "economics": [
        "Federal Reserve interest rate",
        "inflation CPI 2025",
        "recession GDP",
        "stock market S&P 500",
        "unemployment rate jobs",
    ],
    "crypto": [
        "Bitcoin price BTC",
        "Ethereum ETH crypto",
    ],
    "geopolitics": [
        "China Taiwan conflict",
        "Iran nuclear",
        "Israel Palestine ceasefire",
        "North Korea missile",
    ],
    "science": [
        "SpaceX Starship launch",
        "climate temperature record",
        "FDA drug approval",
    ],
    "sports": [
        "Super Bowl NFL champion",
        "NBA finals champion",
        "World Cup FIFA",
        "Olympics medal",
    ],
}


def fetch_markets(term: str, limit: int = 50) -> list[dict]:
    """Fetch resolved binary markets from Manifold API."""
    params = urllib.parse.urlencode({
        "term": term,
        "sort": "score",
        "filter": "resolved",
        "limit": limit,
        "contractType": "BINARY",
    })
    url = f"{MANIFOLD_API}/search-markets?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PredictionMarketDebater/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  Failed to fetch '{term}': {e}")
        return []


def is_quality_market(market: dict, min_volume: float = 500) -> bool:
    """Filter for high-quality, well-formed markets."""
    # Must be resolved YES or NO (not CANCEL)
    resolution = market.get("resolution")
    if resolution not in ("YES", "NO"):
        return False

    # Must have sufficient trading volume
    if market.get("volume", 0) < min_volume:
        return False

    # Must have a real question (not personal/trivial)
    question = market.get("question", "")
    trivial_patterns = [
        "will I ", "will i ", "will my ", "will we ",
        "@", "coin flip", "random", "dice",
        "will jim", "will thomas", "potato",
    ]
    question_lower = question.lower()
    if any(p in question_lower for p in trivial_patterns):
        return False

    # Must be reasonably long
    if len(question) < 20:
        return False

    return True


def market_to_question(market: dict, category: str) -> dict:
    """Convert a Manifold market to our question format."""
    resolution = market["resolution"] == "YES"
    prob = market.get("probability", 0.5)

    return {
        "id": f"manifold_{market['id'][:12]}",
        "question": market["question"],
        "category": category,
        "market_price": round(prob, 4),
        "resolved": True,
        "resolution": resolution,
        "source": "manifold",
        "volume": round(market.get("volume", 0), 2),
    }


def scrape_all(min_volume: float = 500, limit_per_query: int = 50) -> list[dict]:
    """Scrape markets across all categories."""
    all_questions = []
    seen_ids = set()

    for category, queries in SEARCH_QUERIES.items():
        print(f"\n[{category}]")
        for query in queries:
            print(f"  Searching: '{query}'...")
            markets = fetch_markets(query, limit=limit_per_query)

            count = 0
            for m in markets:
                if m["id"] in seen_ids:
                    continue
                if not is_quality_market(m, min_volume=min_volume):
                    continue

                seen_ids.add(m["id"])
                q = market_to_question(m, category)
                all_questions.append(q)
                count += 1

            print(f"    Found {count} quality markets")
            time.sleep(0.5)  # Rate limiting

    return all_questions


def main():
    parser = argparse.ArgumentParser(description="Scrape Manifold Markets for evaluation data")
    parser.add_argument("--min-volume", type=float, default=500, help="Minimum trading volume")
    parser.add_argument("--output", default=None, help="Output file path")
    args = parser.parse_args()

    print("Scraping Manifold Markets...")
    questions = scrape_all(min_volume=args.min_volume)

    # Merge with existing questions
    existing_path = os.path.join(DATA_DIR, "questions.json")
    if os.path.exists(existing_path):
        with open(existing_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_ids = {q["id"] for q in existing}
        new_questions = [q for q in questions if q["id"] not in existing_ids]
        all_questions = existing + new_questions
        print(f"\nExisting: {len(existing)}, New: {len(new_questions)}, Total: {len(all_questions)}")
    else:
        all_questions = questions
        print(f"\nTotal: {len(all_questions)}")

    # Save
    output_path = args.output or os.path.join(DATA_DIR, "questions.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output_path}")

    # Category breakdown
    from collections import Counter
    cats = Counter(q["category"] for q in all_questions if q.get("resolved"))
    print("\nResolved questions by category:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
