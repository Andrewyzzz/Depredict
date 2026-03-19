#!/usr/bin/env python3
"""Run 12 diverse sports/crypto predictions that resolve within 24h."""

import json
import os
import time
import requests

os.environ["NO_PROXY"] = "localhost,127.0.0.1"

API_BASE = "http://localhost:5001"
POLL_INTERVAL = 10

MARKETS = [
    # CS2 esports (~12h)
    {"question": "Counter-Strike: PARIVISION vs NIP (BO3) - BLAST Open Rotterdam Group B",
     "slug": "cs2-prv-nip-2026-03-19", "market_price": 0.64},
    {"question": "Counter-Strike: PARIVISION vs NIP - Map 1 Winner",
     "slug": "cs2-prv-nip-2026-03-19-game1", "market_price": 0.57},

    # Football/Soccer Europa League (~16h)
    {"question": "Will AS Roma win on 2026-03-19?",
     "slug": "uel-rom1-bol1-2026-03-19-rom1", "market_price": 0.55},
    {"question": "Will AS Roma vs. Bologna FC 1909 end in a draw?",
     "slug": "uel-rom1-bol1-2026-03-19-draw", "market_price": 0.26},

    # LoL esports (~15h)
    {"question": "Game Handicap: GEN (-2.5) vs LYON (+2.5)",
     "slug": "lol-gen-ly-2026-03-19-game-handicap-away-2pt5", "market_price": 0.77},
    {"question": "LoL: Gen.G vs LYON - Game 4 Winner",
     "slug": "lol-gen-ly-2026-03-19-game4", "market_price": 0.57},

    # NBA (~21h)
    {"question": "Bucks vs. Jazz",
     "slug": "nba-mil-uta-2026-03-19", "market_price": 0.66},

    # NHL (~22h)
    {"question": "Utah vs. Golden Knights",
     "slug": "nhl-utah-las-2026-03-19", "market_price": 0.46},
    {"question": "Utah vs. Golden Knights: O/U 5.5",
     "slug": "nhl-utah-las-2026-03-19-total-5pt5", "market_price": 0.56},

    # Crypto prices (~12h)
    {"question": "Will the price of Bitcoin be above $72,000 on March 19?",
     "slug": "bitcoin-above-72k-on-march-19", "market_price": 0.28},
    {"question": "Will the price of Ethereum be above $2,200 on March 19?",
     "slug": "ethereum-above-2200-on-march-19", "market_price": 0.60},
    {"question": "Will the price of Bitcoin be between $70,000 and $72,000 on March 19?",
     "slug": "will-the-price-of-bitcoin-be-between-70000-72000-on-march-19", "market_price": 0.52},
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
    print(f"Running {len(MARKETS)} predictions...\n")
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
