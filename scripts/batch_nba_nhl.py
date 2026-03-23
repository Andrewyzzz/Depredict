#!/usr/bin/env python3
"""
Batch-run predictions on specific NBA and NHL markets.
Includes main lines, spreads, and totals.
"""

import os
import sys
import time
import requests

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
API_BASE = "http://localhost:5001"
POLL_INTERVAL = 10

MARKETS = [
    # NBA: Lakers vs Pistons
    {"question": "Lakers vs. Pistons", "slug": "nba-lal-det-2026-03-23", "market_price": 0.555},
    {"question": "Spread: Lakers (-2.5)", "slug": "nba-lal-det-2026-03-23-spread-away-2pt5", "market_price": 0.49},
    {"question": "Spread: Lakers (-1.5)", "slug": "nba-lal-det-2026-03-23-spread-away-1pt5", "market_price": 0.52},
    {"question": "Lakers vs. Pistons: O/U 227.5", "slug": "nba-lal-det-2026-03-23-total-227pt5", "market_price": 0.48},

    # NBA: Warriors vs Mavericks
    {"question": "Warriors vs. Mavericks", "slug": "nba-gsw-dal-2026-03-23", "market_price": 0.555},
    {"question": "Spread: Warriors (-2.5)", "slug": "nba-gsw-dal-2026-03-23-spread-away-2pt5", "market_price": 0.50},
    {"question": "Warriors vs. Mavericks: O/U 229.5", "slug": "nba-gsw-dal-2026-03-23-total-229pt5", "market_price": 0.52},
    {"question": "Warriors vs. Mavericks: O/U 231.5", "slug": "nba-gsw-dal-2026-03-23-total-231pt5", "market_price": 0.48},

    # NHL: Senators vs Rangers
    {"question": "Senators vs. Rangers", "slug": "nhl-ott-nyr-2026-03-23", "market_price": 0.635},
    {"question": "Senators vs. Rangers: O/U 5.5", "slug": "nhl-ott-nyr-2026-03-23-total-5pt5", "market_price": 0.55},
    {"question": "Senators vs. Rangers: O/U 6.5", "slug": "nhl-ott-nyr-2026-03-23-total-6pt5", "market_price": 0.44},
    {"question": "Spread: Senators (-1.5)", "slug": "nhl-ott-nyr-2026-03-23-spread-away-1pt5", "market_price": 0.41},
]


def run_prediction(market):
    question = market["question"]
    market_price = market["market_price"]
    slug = market["slug"]

    print(f"\n{'='*60}")
    print(f"  Q: {question}")
    print(f"  Market: {market_price*100:.1f}%  |  Slug: {slug}")
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
    print(f"Running {len(MARKETS)} NBA/NHL predictions...\n")

    for i, m in enumerate(MARKETS, 1):
        print(f"  [{i:2d}] {m['question'][:55]}  price={m['market_price']*100:.0f}%")

    success = 0
    failed = 0

    for i, m in enumerate(MARKETS, 1):
        print(f"\n[{i}/{len(MARKETS)}] Starting...")
        result = run_prediction(m)
        if result:
            success += 1
        else:
            failed += 1
        if i < len(MARKETS):
            time.sleep(3)

    print(f"\n{'='*60}")
    print(f"Done: {success} success, {failed} failed out of {len(MARKETS)}")
    print(f"{'='*60}")

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
