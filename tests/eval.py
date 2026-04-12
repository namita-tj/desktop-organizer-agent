"""
eval.py — Measures rule-based classification accuracy against a fixed labeled dataset.

Run this before and after any change to classifier.py to check
you haven't broken anything or to measure improvement.

Usage:
    python tests/eval.py                  # Full report
    python tests/eval.py --failures-only  # Only show misclassified files
    python tests/eval.py --category Code  # Drill into one category

Exit codes:
    0 — accuracy at or above TARGET_ACCURACY
    1 — accuracy below TARGET_ACCURACY (useful for CI)
"""

import json
import sys
import argparse
from pathlib import Path

# Add project root to path so src imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.classifier import _rule_based_classify

DATASET_PATH = Path(__file__).parent / "eval_dataset.json"
TARGET_ACCURACY = 90.0  # percent — CI fails below this


def load_dataset() -> list:
    with open(DATASET_PATH) as f:
        return json.load(f)


def run_eval(dataset: list) -> list:
    results = []
    for item in dataset:
        file_obs = {
            "name": item["name"],
            "extension": item["extension"],
            "size_bytes": item["size_bytes"]
        }
        result = _rule_based_classify(file_obs)
        results.append({
            "file":       item["name"],
            "expected":   item["expected"],
            "got":        result["category"],
            "confidence": result["confidence"],
            "method":     result["method"],
            "correct":    result["category"] == item["expected"]
        })
    return results


def print_report(results: list, failures_only: bool = False, filter_category: str = None) -> float:
    if filter_category:
        results = [r for r in results if r["expected"] == filter_category]

    total   = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total * 100 if total else 0.0

    print(f"\n{'─' * 50}")
    print(f"  Desktop Organiser — Classification Eval")
    print(f"{'─' * 50}")
    if filter_category:
        print(f"  Category filter:  {filter_category}")
    print(f"  Dataset size:     {total} files")
    print(f"  Correct:          {correct}")
    print(f"  Accuracy:         {accuracy:.1f}%  (target: {TARGET_ACCURACY}%)")
    print(f"{'─' * 50}\n")

    # Per-category breakdown
    categories = sorted(set(r["expected"] for r in results))
    print("  Per-category breakdown:")
    for cat in categories:
        cat_results = [r for r in results if r["expected"] == cat]
        cat_correct = sum(1 for r in cat_results if r["correct"])
        cat_acc = cat_correct / len(cat_results) * 100
        bar = "█" * int(cat_acc / 10) + "░" * (10 - int(cat_acc / 10))
        print(f"    {cat:<12s} {bar}  {cat_acc:5.1f}%  ({cat_correct}/{len(cat_results)})")

    # Failures
    failures = [r for r in results if not r["correct"]]
    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for f in failures:
            print(f"    ✗  {f['file']}")
            print(f"       expected: {f['expected']}")
            print(f"       got:      {f['got']}  (confidence: {f['confidence']})")
    elif not failures_only:
        print("\n  ✓ No failures")

    if not failures_only:
        # Full results table
        print(f"\n  {'File':<45s} {'Expected':<12s} {'Got':<12s} {'Conf':>6s}  OK")
        print(f"  {'─'*45} {'─'*12} {'─'*12} {'─'*6}  ──")
        for r in results:
            tick = "✓" if r["correct"] else "✗"
            print(f"  {r['file']:<45s} {r['expected']:<12s} {r['got']:<12s} {r['confidence']:>6.2f}  {tick}")

    print(f"\n{'─' * 50}\n")
    return accuracy


def main():
    parser = argparse.ArgumentParser(description="Evaluate rule-based classifier accuracy")
    parser.add_argument("--failures-only", action="store_true", help="Only show misclassified files")
    parser.add_argument("--category", type=str, default=None, help="Filter to a single category")
    args = parser.parse_args()

    dataset = load_dataset()
    results = run_eval(dataset)
    accuracy = print_report(results, failures_only=args.failures_only, filter_category=args.category)

    # Exit 1 if below target — lets CI catch regressions
    sys.exit(0 if accuracy >= TARGET_ACCURACY else 1)


if __name__ == "__main__":
    main()