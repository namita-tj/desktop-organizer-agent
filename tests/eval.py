"""
eval.py — Enterprise KPI evaluation system for Desktop Organiser Agent.

Adds:
- Accuracy
- Precision / Recall / F1 per category
- Confusion matrix
- Latency tracking
- CSV export
- CI gating via TARGET_ACCURACY
"""

import json
import sys
import argparse
import time
import csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.classifier import _rule_based_classify

DATASET_PATH = Path(__file__).parent / "eval_dataset.json"
TARGET_ACCURACY = 90.0


# ─────────────────────────────────────────────────────────────
# Load dataset
# ─────────────────────────────────────────────────────────────

def load_dataset():
    with open(DATASET_PATH) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# Evaluation runner
# ─────────────────────────────────────────────────────────────

def run_eval(dataset):
    results = []
    confusion = defaultdict(lambda: defaultdict(int))
    latency_stats = []

    for item in dataset:
        file_obs = {
            "name": item["name"],
            "extension": item["extension"],
            "size_bytes": item["size_bytes"]
        }

        start = time.time()
        result = _rule_based_classify(file_obs)
        latency = time.time() - start

        predicted = result["category"]
        actual = item["expected"]

        confusion[actual][predicted] += 1
        latency_stats.append(latency)

        results.append({
            "file": item["name"],
            "expected": actual,
            "got": predicted,
            "confidence": result["confidence"],
            "correct": predicted == actual,
            "latency_ms": round(latency * 1000, 2)
        })

    return results, confusion, latency_stats


# ─────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────

def compute_metrics(results, confusion):
    categories = sorted(set(r["expected"] for r in results))

    metrics = {}

    for cat in categories:
        tp = confusion[cat][cat]
        fp = sum(confusion[o][cat] for o in categories if o != cat)
        fn = sum(confusion[cat][o] for o in categories if o != cat)

        precision = tp / (tp + fp) if (tp + fp) else 0
        recall = tp / (tp + fn) if (tp + fn) else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0

        metrics[cat] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn
        }

    return metrics


# ─────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────

def print_report(results, confusion, metrics, latency_stats):
    total = len(results)
    correct = sum(r["correct"] for r in results)
    accuracy = correct / total * 100 if total else 0

    avg_latency = sum(latency_stats) / len(latency_stats) * 1000

    print("\n" + "═" * 70)
    print("  📊 Enterprise Document Classification KPI Report")
    print("═" * 70)

    print(f"\nOverall Accuracy: {accuracy:.2f}% (target: {TARGET_ACCURACY}%)")
    print(f"Avg Latency:      {avg_latency:.2f} ms per file")

    print("\n📌 Per-category metrics:\n")

    for cat, m in metrics.items():
        print(
            f"{cat:<12} "
            f"P={m['precision']:.2f}  "
            f"R={m['recall']:.2f}  "
            f"F1={m['f1']:.2f}  "
            f"Support={m['support']}"
        )

    print("\n📉 Confusion Matrix:\n")

    cats = sorted(confusion.keys())
    header = "Pred → " + "  ".join(f"{c:>10}" for c in cats)
    print(header)

    for actual in cats:
        row = f"{actual:<10}"
        for pred in cats:
            row += f"{confusion[actual][pred]:>10}"
        print(row)

    print("\n" + "═" * 70)

    return accuracy


# ─────────────────────────────────────────────────────────────
# CSV Export (for dashboards / BI tools)
# ─────────────────────────────────────────────────────────────

def export_csv(results, path="eval_results.csv"):
    keys = results[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n📁 Exported results → {path}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--failures-only", action="store_true")
    parser.add_argument("--category", type=str)
    parser.add_argument("--export-csv", action="store_true")
    args = parser.parse_args()

    dataset = load_dataset()
    results, confusion, latency_stats = run_eval(dataset)
    metrics = compute_metrics(results, confusion)

    accuracy = print_report(results, confusion, metrics, latency_stats)

    if args.export_csv:
        export_csv(results)

    # CI gate
    sys.exit(0 if accuracy >= TARGET_ACCURACY else 1)


if __name__ == "__main__":
    main()