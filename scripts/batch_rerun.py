#!/usr/bin/env python3
"""
Batch re-run debate pipeline for questions with null/failed results.

Usage:
    python scripts/batch_rerun.py [--dry-run] [--limit N] [--patch-only]

Options:
    --dry-run     List questions that need re-running without actually running them
    --limit N     Only re-run the first N questions
    --patch-only  Only patch existing results with missing aggregation methods (no LLM calls)
"""

import json
import os
import sys
import time
import argparse
import statistics
from pathlib import Path

# Add project root and backend to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

DATA_DIR = PROJECT_ROOT / "data"
QUESTIONS_FILE = DATA_DIR / "questions.json"
RESULTS_DIR = DATA_DIR / "results"


def load_questions() -> list[dict]:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_result(question_id: str) -> dict | None:
    path = RESULTS_DIR / f"{question_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_result(question_id: str, result: dict):
    path = RESULTS_DIR / f"{question_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


def needs_rerun(result: dict) -> bool:
    """Check if a result has null probabilities (failed debate)."""
    if result is None:
        return True
    hybrid_prob = result.get("aggregation_mechanisms", {}).get("hybrid", {}).get("probability")
    return hybrid_prob is None


def needs_patch(result: dict) -> bool:
    """Check if a result is missing aggregation methods that can be computed from existing round3 data."""
    if result is None:
        return False
    mechs = result.get("aggregation_mechanisms", {})
    required = ["median", "trimmed_mean", "logit_average"]
    return any(m not in mechs for m in required)


def patch_aggregation_methods(result: dict) -> dict:
    """Add missing aggregation methods computed from round3 data. No LLM calls needed."""
    from backend.app.core.aggregator import (
        aggregate_median,
        aggregate_trimmed_mean,
        aggregate_logit_average,
    )

    round3 = result.get("rounds", {}).get("round3", [])
    if not round3:
        return result

    mechs = result.get("aggregation_mechanisms", {})

    if "median" not in mechs:
        res = aggregate_median(round3)
        mechs["median"] = {"probability": res["probability"], "details": res.get("details", {})}

    if "trimmed_mean" not in mechs:
        res = aggregate_trimmed_mean(round3)
        mechs["trimmed_mean"] = {"probability": res["probability"], "details": res.get("details", {})}

    if "logit_average" not in mechs:
        res = aggregate_logit_average(round3)
        mechs["logit_average"] = {"probability": res["probability"], "details": res.get("details", {})}

    result["aggregation_mechanisms"] = mechs
    return result


def run_debate(question: str, market_price: float | None) -> dict:
    """Run the debate pipeline for a single question."""
    from backend.app.core.debate_pipeline import DebatePipeline

    pipeline = DebatePipeline()
    return pipeline.run(question, market_price=market_price)


def main():
    parser = argparse.ArgumentParser(description="Batch re-run failed debates")
    parser.add_argument("--dry-run", action="store_true", help="List without running")
    parser.add_argument("--limit", type=int, default=0, help="Max questions to re-run")
    parser.add_argument("--patch-only", action="store_true", help="Only patch missing aggregation methods")
    args = parser.parse_args()

    questions = load_questions()
    print(f"Total questions: {len(questions)}")

    # Step 1: Patch existing good results with missing aggregation methods
    patched = 0
    for q in questions:
        result = load_result(q["id"])
        if result and not needs_rerun(result) and needs_patch(result):
            result = patch_aggregation_methods(result)
            save_result(q["id"], result)
            patched += 1

    print(f"Patched {patched} results with missing aggregation methods")

    if args.patch_only:
        return

    # Step 2: Find questions needing re-run
    to_rerun = []
    for q in questions:
        result = load_result(q["id"])
        if needs_rerun(result):
            to_rerun.append(q)

    print(f"Questions needing re-run: {len(to_rerun)}")

    if args.dry_run:
        for q in to_rerun:
            print(f"  {q['id']}: {q['question'][:80]}")
        return

    limit = args.limit if args.limit > 0 else len(to_rerun)
    to_rerun = to_rerun[:limit]
    print(f"Will re-run {len(to_rerun)} questions\n")

    success = 0
    failed = 0
    for i, q in enumerate(to_rerun):
        print(f"\n[{i+1}/{len(to_rerun)}] {q['question'][:70]}...")
        try:
            result = run_debate(q["question"], market_price=q.get("market_price"))
            # Preserve metadata
            result["question_id"] = q["id"]
            result["actual"] = q.get("resolution")
            save_result(q["id"], result)
            hybrid = result.get("aggregation_mechanisms", {}).get("hybrid", {}).get("probability")
            print(f"  -> Hybrid: {hybrid}%, saved to {q['id']}.json")
            success += 1
        except Exception as e:
            print(f"  -> FAILED: {e}")
            failed += 1

        # Rate limiting between debates
        if i < len(to_rerun) - 1:
            time.sleep(2)

    print(f"\nDone: {success} success, {failed} failed out of {len(to_rerun)}")


if __name__ == "__main__":
    main()
