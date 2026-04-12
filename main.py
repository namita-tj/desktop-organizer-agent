"""
main.py — Entry point for the Desktop Organiser Agent.

Usage:
    python main.py              # Dry run (safe, shows what would happen)
    python main.py --move       # Actually moves files
    python main.py --threshold 0.7   # Only move files with confidence >= 0.7
"""

import argparse
from observer import observe_desktop
from classifier import classify_file
from actor import act, summarise_actions


def run_agent(dry_run: bool = True, confidence_threshold: float = 0.6) -> None:
    print("\n── Desktop Organiser Agent ──────────────")
    print(f"  Mode:      {'DRY RUN' if dry_run else '⚠ LIVE — files will be moved'}")
    print(f"  Threshold: {confidence_threshold} confidence minimum")
    print("─────────────────────────────────────────\n")

    # Step 1: Observe
    observations = observe_desktop()
    if not observations:
        print("No files found on Desktop.")
        return
    print(f"Found {len(observations)} file(s) on Desktop.\n")

    # Step 2 & 3: Classify then Act
    action_log = []

    for file_obs in observations:
        result = classify_file(file_obs)

        category = result["category"]
        confidence = result["confidence"]
        method = result["method"]
        reasoning = result.get("reasoning", "")

        print(f"  [{method.upper()}] {file_obs['name']}")
        print(f"    Category:   {category}")
        print(f"    Confidence: {confidence}")
        if reasoning:
            print(f"    Reason:     {reasoning}")

        # Skip low-confidence classifications
        if confidence < confidence_threshold:
            print(f"    ⚠ Skipping — confidence below threshold ({confidence_threshold})\n")
            action_log.append({"name": file_obs["name"], "action": "skipped",
                                "message": f"Low confidence: {confidence}"})
            continue

        # Skip unknown category
        if category == "Unknown":
            print(f"    ⚠ Skipping — could not determine category\n")
            action_log.append({"name": file_obs["name"], "action": "skipped",
                                "message": "Unknown category"})
            continue

        # Act
        action_result = act(file_obs, category, dry_run=dry_run)
        action_log.append(action_result)
        print()

    # Summary
    summarise_actions(action_log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM-powered Desktop Organiser")
    parser.add_argument("--move", action="store_true",
                        help="Actually move files (default is dry run)")
    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Minimum confidence to act on (default: 0.6)")
    args = parser.parse_args()

    run_agent(
        dry_run=not args.move,
        confidence_threshold=args.threshold
    )