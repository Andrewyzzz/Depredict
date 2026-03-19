#!/usr/bin/env python3
"""
Check pending prospective predictions against Polymarket for resolution.

Can be run manually or via cron:
    python scripts/check_resolutions.py
    python scripts/check_resolutions.py --verbose
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root and backend to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.prospective_tracker import ProspectiveTracker
from app.services.polymarket_client import PolymarketClient


def main():
    parser = argparse.ArgumentParser(
        description="Check pending prospective predictions for resolution."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging output.",
    )
    parser.add_argument(
        "--stats-only", action="store_true",
        help="Only print current stats without checking resolutions.",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    tracker = ProspectiveTracker()

    if args.stats_only:
        stats = tracker.get_stats()
        print(json.dumps(stats, indent=2))
        return

    # Show current state
    pending = tracker.get_pending()
    print(f"Pending predictions: {len(pending)}")

    if not pending:
        print("No pending predictions to check.")
        stats = tracker.get_stats()
        print(f"\nOverall stats: {json.dumps(stats, indent=2)}")
        return

    # Check resolutions
    print("Checking Polymarket for resolutions...")
    client = PolymarketClient()
    result = tracker.check_resolutions(client)

    print(f"\nResolution check complete:")
    print(f"  Checked:        {result['checked']}")
    print(f"  Newly resolved: {result['newly_resolved']}")
    print(f"  Still pending:  {result['still_pending']}")
    print(f"  Total tracked:  {result['total']}")

    # Print updated stats
    stats = tracker.get_stats()
    print(f"\nOverall stats:")
    print(f"  Total predictions:   {stats['total']}")
    print(f"  Pending:             {stats['pending']}")
    print(f"  Resolved:            {stats['resolved']}")
    if stats['avg_model_brier'] is not None:
        print(f"  Avg model Brier:     {stats['avg_model_brier']:.4f}")
    if stats['avg_market_brier'] is not None:
        print(f"  Avg market Brier:    {stats['avg_market_brier']:.4f}")
    if stats['model_beats_market'] is not None:
        verdict = "YES" if stats['model_beats_market'] else "NO"
        print(f"  Model beats market:  {verdict}")


if __name__ == "__main__":
    main()
