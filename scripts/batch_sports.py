#!/usr/bin/env python3
"""
Batch-run predictions on sports/esports markets resolving soon.

Usage:
    python scripts/batch_sports.py [--limit N] [--dry-run] [--max-hours H]
"""

import argparse
import json
import os
import sys
import time

import requests

# Bypass system proxy for local API calls
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

API_BASE = "http://localhost:5001"
GAMMA_API = "https://gamma-api.polymarket.com"
POLL_INTERVAL = 10  # seconds


def fetch_sports_markets(max_hours: float = 24, limit: int = 15) -> list[dict]:
    """Fetch sports/esports markets resolving within max_hours from Polymarket."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=max_hours)

    # Fetch sports events
    resp = requests.get(
        f"{GAMMA_API}/events",
        params={
            "active": "true",
            "limit": 200,
            "order": "volume24hr",
            "ascending": "false",
            "tag": "sports",
        },
        timeout=30,
    )
    resp.raise_for_status()
    events = resp.json()

    candidates = []
    seen_slugs = set()

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

        for mkt in event.get("markets", []):
            slug = mkt.get("slug", "")
            if not slug or slug in seen_slugs:
                continue

            price_str = mkt.get("outcomePrices", "[]")
            try:
                prices = json.loads(price_str)
                price = float(prices[0]) if prices else 0
            except Exception:
                price = 0

            # Skip extreme prices
            if price < 0.10 or price > 0.90:
                continue

            q = mkt.get("question", "") or event.get("title", "")

            # Skip odd/even markets (pure coin flips)
            if "odd/even" in q.lower() or "odd even" in q.lower():
                continue

            vol_str = mkt.get("volume", "0")
            try:
                vol = float(vol_str)
            except Exception:
                vol = 0

            seen_slugs.add(slug)
            candidates.append({
                "question": q,
                "slug": slug,
                "market_price": round(price, 4),
                "volume": vol,
                "hours_left": round(hours_left, 1),
                "end_date": end,
            })

    # Sort by hours_left (soonest first), then volume
    candidates.sort(key=lambda m: (m["hours_left"], -m["volume"]))
    return candidates[:limit]


def run_prediction(market: dict) -> dict | None:
    """Start a debate and wait for completion."""
    question = market["question"]
    market_price = market["market_price"]
    slug = market["slug"]

    print(f"\n{'='*60}")
    print(f"  Q: {question}")
    print(f"  Market: {market_price*100:.1f}%  |  Resolves in: {market['hours_left']}h")
    print(f"  Slug: {slug}")
    print(f"{'='*60}")

    # Start debate
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

    # Poll for completion
    start_time = time.time()
    max_wait = 600  # 10 minutes max
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
                else:
                    print(f"  -> Completed but no hybrid probability")
                return result

            if status_data.get("status") == "FAILED":
                print(f"  -> FAILED: {status_data.get('error', 'unknown')}")
                return None

        except Exception as e:
            print(f"  Poll error: {e}")

    print(f"  -> TIMEOUT after {max_wait}s")
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch-run sports predictions")
    parser.add_argument("--limit", type=int, default=12, help="Max markets to run")
    parser.add_argument("--max-hours", type=float, default=24, help="Max hours until resolution")
    parser.add_argument("--dry-run", action="store_true", help="Show markets but don't run")
    args = parser.parse_args()

    print("Fetching sports/esports markets resolving soon...")
    markets = fetch_sports_markets(max_hours=args.max_hours, limit=args.limit)
    print(f"Found {len(markets)} eligible markets\n")

    if not markets:
        print("No markets found. Try increasing --max-hours.")
        return

    for i, m in enumerate(markets, 1):
        print(f"  [{i}] [{m['hours_left']}h] {m['question'][:65]}  price={m['market_price']*100:.0f}%")

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


if __name__ == "__main__":
    main()
