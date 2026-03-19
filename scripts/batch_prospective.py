#!/usr/bin/env python3
"""
Batch-run prospective predictions on DeepSeek-safe active markets.

Usage:
    python scripts/batch_prospective.py [--limit N] [--dry-run]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

# Bypass system proxy for local API calls
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

API_BASE = "http://localhost:5001"
POLL_INTERVAL = 10  # seconds


def get_safe_markets(limit: int = 20) -> list[dict]:
    """Fetch markets from scanner and filter for DeepSeek-safe ones."""
    resp = requests.get(f"{API_BASE}/api/market/scan", timeout=120)
    resp.raise_for_status()
    markets = resp.json().get("markets", [])

    # Keywords that indicate DeepSeek will likely block
    unsafe_keywords = [
        "iran", "ukraine", "russia", "gaza", "israel", "netanyahu",
        "taiwan", "china", "assassination", "kill", "war ",
        "nuclear", "missile", "military", "invasion", "troops",
        "terrorist", "hamas", "hezbollah", "putin", "zelensky",
        "ayatollah", "khamenei", "regime", "coup",
    ]

    safe = []
    for m in markets:
        q = m.get("question", "").lower()
        price = m.get("market_price", 0)

        # Skip near-certain outcomes
        if price < 0.02 or price > 0.98:
            continue

        # Skip if no slug (can't track)
        if not m.get("slug"):
            continue

        # Check for unsafe keywords
        is_unsafe = any(kw in q for kw in unsafe_keywords)
        if is_unsafe:
            continue

        safe.append(m)

    # Sort by volume descending
    safe.sort(key=lambda m: m.get("volume_24h", 0), reverse=True)
    return safe[:limit]


def run_prediction(market: dict) -> dict | None:
    """Start a debate and wait for completion."""
    question = market["question"]
    market_price = market["market_price"]
    slug = market["slug"]

    print(f"\n{'='*60}")
    print(f"  Q: {question}")
    print(f"  Market: {market_price*100:.1f}%  |  Slug: {slug}")
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
                # Get result
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
    parser = argparse.ArgumentParser(description="Batch-run prospective predictions")
    parser.add_argument("--limit", type=int, default=10, help="Max markets to run")
    parser.add_argument("--dry-run", action="store_true", help="Show markets but don't run")
    args = parser.parse_args()

    print("Fetching safe markets...")
    markets = get_safe_markets(limit=args.limit)
    print(f"Found {len(markets)} safe markets\n")

    for i, m in enumerate(markets, 1):
        cat = m.get("category", "?")
        price = m.get("market_price", 0)
        vol = m.get("volume_24h", 0)
        print(f"  [{i}] [{cat}] {m['question'][:60]}  price={price*100:.1f}%  vol={vol:.0f}")

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

        # Small delay between runs to be nice to APIs
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
