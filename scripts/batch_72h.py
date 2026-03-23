#!/usr/bin/env python3
"""
Batch-run predictions on diverse markets resolving within 72 hours.

Filters for high-quality, independent markets:
- Skips derivative markets (O/U, Spread, player props)
- Skips extreme prices (<10% or >90%)
- Deduplicates by event (one market per event)
- Mixes sports + crypto + general

Usage:
    python scripts/batch_72h.py [--limit N] [--dry-run] [--max-hours H]
"""

import argparse
import json
import os
import re
import sys
import time

import requests

os.environ["NO_PROXY"] = "localhost,127.0.0.1"

API_BASE = "http://localhost:5001"
GAMMA_API = "https://gamma-api.polymarket.com"
POLL_INTERVAL = 10


def is_derivative_market(question: str) -> bool:
    """Check if a market is a low-quality derivative (player props, exact scores)."""
    q = question.lower()
    patterns = [
        r": points o/u", r": assists o/u", r": rebounds o/u",
        r"odd/even", r"odd even",
        r": points$", r"points o/u",
        r": assists$", r": rebounds$",
        r"exact score", r"first goal",
    ]
    for p in patterns:
        if re.search(p, q):
            return True
    return False


def is_price_range_market(question: str) -> bool:
    """Check if market is a narrow price range (e.g., 'between $68k and $70k')."""
    q = question.lower()
    if "between" in q and ("$" in q or "°" in q):
        return True
    if re.search(r"be \d+°c on", q):
        return True
    return False


def fetch_diverse_markets(max_hours: float = 72, limit: int = 30) -> list[dict]:
    """Fetch diverse, high-quality markets from Polymarket."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=max_hours)

    all_candidates = []
    seen_slugs = set()
    seen_events = {}  # event_slug -> count

    # Fetch from multiple tags
    tags = ["sports", "crypto", "politics", "science", "entertainment", ""]

    for tag in tags:
        params = {
            "active": "true",
            "limit": 200,
            "order": "volume24hr",
            "ascending": "false",
        }
        if tag:
            params["tag"] = tag

        try:
            resp = requests.get(f"{GAMMA_API}/events", params=params, timeout=30)
            resp.raise_for_status()
            events = resp.json()
        except Exception as e:
            print(f"  Warning: failed to fetch tag={tag}: {e}")
            continue

        for event in events:
            end = event.get("endDate", "") or ""
            if not end:
                continue
            try:
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except Exception:
                continue
            if end_dt < now or end_dt > cutoff:
                continue

            hours_left = (end_dt - now).total_seconds() / 3600
            event_title = event.get("title", "")
            event_slug = event.get("slug", event_title[:40])

            for mkt in event.get("markets", []):
                slug = mkt.get("slug", "")
                if not slug or slug in seen_slugs:
                    continue

                q = mkt.get("question", "") or event_title

                # Skip derivative markets
                if is_derivative_market(q):
                    continue

                # Skip narrow price range markets
                if is_price_range_market(q):
                    continue

                # Parse price
                price_str = mkt.get("outcomePrices", "[]")
                try:
                    prices = json.loads(price_str)
                    price = float(prices[0]) if prices else 0
                except Exception:
                    price = 0

                # Skip extreme prices
                if price < 0.05 or price > 0.95:
                    continue

                # Allow up to 2 markets per event
                event_count = seen_events.get(event_slug, 0)
                if event_count >= 2:
                    continue

                vol_str = mkt.get("volume", "0")
                try:
                    vol = float(vol_str)
                except Exception:
                    vol = 0

                # Skip very low volume
                if vol < 1000:
                    continue

                seen_slugs.add(slug)
                seen_events[event_slug] = event_count + 1

                # Determine category
                category = "general"
                q_lower = q.lower()
                if any(s in q_lower for s in ["vs.", "win the", "nba", "nfl", "nhl", "premier", "champions"]):
                    category = "sports"
                elif any(s in q_lower for s in ["bitcoin", "ethereum", "btc", "eth", "crypto", "dip to"]):
                    category = "crypto"
                elif any(s in q_lower for s in ["tweet", "elon", "musk", "post"]):
                    category = "social"

                all_candidates.append({
                    "question": q,
                    "slug": slug,
                    "market_price": round(price, 4),
                    "volume": vol,
                    "hours_left": round(hours_left, 1),
                    "end_date": end,
                    "category": category,
                })

    # Sort: soonest first, then by volume
    all_candidates.sort(key=lambda m: (m["hours_left"], -m["volume"]))
    return all_candidates[:limit]


# DeepSeek safety filter
UNSAFE_KEYWORDS = [
    "iran", "ukraine", "russia", "gaza", "israel", "netanyahu",
    "taiwan", "assassination", "kill", "war ", "nuclear", "missile",
    "military", "invasion", "troops", "terrorist", "hamas", "hezbollah",
    "putin", "zelensky", "ayatollah", "khamenei", "regime", "coup",
]


def is_safe(question: str) -> bool:
    q = question.lower()
    return not any(kw in q for kw in UNSAFE_KEYWORDS)


def run_prediction(market: dict) -> dict | None:
    """Start a debate and wait for completion."""
    question = market["question"]
    market_price = market["market_price"]
    slug = market["slug"]

    print(f"\n{'='*60}")
    print(f"  Q: {question}")
    print(f"  Market: {market_price*100:.1f}%  |  {market['hours_left']}h  |  {market['category']}")
    print(f"  Slug: {slug}")
    print(f"{'='*60}")

    try:
        resp = requests.post(f"{API_BASE}/api/debate/start", json={
            "question": question,
            "market_price": market_price,
            "slug": slug,
        }, timeout=15)
        resp.raise_for_status()
        task_id = resp.json()["task_id"]
    except Exception as e:
        print(f"  FAILED to start: {e}")
        return None

    start_time = time.time()
    max_wait = 600
    last_stage = ""

    while time.time() - start_time < max_wait:
        time.sleep(POLL_INTERVAL)
        try:
            status_resp = requests.get(f"{API_BASE}/api/debate/{task_id}/status", timeout=10)
            status_data = status_resp.json()
            stage = status_data.get("current_stage", "")
            pct = status_data.get("progress_percent", 0)

            if stage != last_stage:
                elapsed = int(time.time() - start_time)
                print(f"  [{elapsed}s] {stage} ({pct}%)")
                last_stage = stage

            if status_data.get("status") == "COMPLETED":
                result_resp = requests.get(f"{API_BASE}/api/debate/{task_id}/result", timeout=10)
                result = result_resp.json()
                hybrid = result.get("aggregation_mechanisms", {}).get("hybrid", {}).get("probability")
                if hybrid is not None:
                    edge = hybrid / 100 - market_price
                    print(f"  -> Model: {hybrid:.1f}%  |  Market: {market_price*100:.1f}%  |  Edge: {edge*100:+.1f}%")
                return result

            if status_data.get("status") == "FAILED":
                print(f"  -> FAILED: {status_data.get('error', 'unknown')}")
                return None

        except Exception as e:
            print(f"  Poll error: {e}")

    print(f"  -> TIMEOUT after {max_wait}s")
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch-run 72h market predictions")
    parser.add_argument("--limit", type=int, default=30, help="Max markets to run")
    parser.add_argument("--max-hours", type=float, default=72, help="Max hours until resolution")
    parser.add_argument("--dry-run", action="store_true", help="Show markets but don't run")
    args = parser.parse_args()

    print(f"Fetching diverse markets resolving within {args.max_hours}h...")
    markets = fetch_diverse_markets(max_hours=args.max_hours, limit=args.limit * 2)

    # Apply safety filter
    markets = [m for m in markets if is_safe(m["question"])]
    markets = markets[:args.limit]

    print(f"Found {len(markets)} eligible markets\n")

    if not markets:
        print("No markets found. Try increasing --max-hours.")
        return

    # Show category breakdown
    cats = {}
    for m in markets:
        cats[m["category"]] = cats.get(m["category"], 0) + 1
    print(f"Categories: {cats}\n")

    for i, m in enumerate(markets, 1):
        print(f"  [{i:2d}] [{m['category']:7s}] [{m['hours_left']:5.1f}h] {m['question'][:55]}  price={m['market_price']*100:.0f}%")

    if args.dry_run:
        print("\n(dry run, not executing)")
        return

    print(f"\nRunning {len(markets)} predictions...")
    success = 0
    failed = 0

    for i, m in enumerate(markets, 1):
        print(f"\n[{i}/{len(markets)}] Starting...")
        result = run_prediction(m)
        if result:
            success += 1
        else:
            failed += 1

        if i < len(markets):
            time.sleep(3)

    print(f"\n{'='*60}")
    print(f"Done: {success} success, {failed} failed out of {len(markets)}")
    print(f"{'='*60}")

    # Show prospective stats
    try:
        stats_resp = requests.get(f"{API_BASE}/api/history/prospective", timeout=10)
        stats = stats_resp.json().get("stats", {})
        print(f"\nProspective Stats:")
        print(f"  Total predictions: {stats.get('total', 0)}")
        print(f"  Pending: {stats.get('pending', 0)}")
        print(f"  Resolved: {stats.get('resolved', 0)}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
