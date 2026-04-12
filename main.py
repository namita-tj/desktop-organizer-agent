"""
main.py — Entry point for the Desktop Organiser Agent.

Usage:
    python main.py                        # Dry run, no feedback prompts
    python main.py --move                 # Actually moves files
    python main.py --move --feedback      # Moves files + asks for corrections
    python main.py --threshold 0.7        # Only act on high-confidence results
    python main.py --stats                # Show what the agent has learned
    python main.py --clear-memory         # Wipe all learned patterns
"""

import argparse
from observer import observe_desktop
from classifier import classify_file
from actor import act, summarise_actions
from memory import save_correction, show_stats, clear_memory, get_all_categories, add_custom_category

VALID_CATEGORIES = [
    "Documents", "Images", "Code", "Archives",
    "Installers", "Videos", "Audio", "Unknown"
]


def ask_for_feedback(file_obs: dict, result: dict) -> None:
    print(f"\n  ❓ Was this correct?  {file_obs['name']} → {result['category']}")
    print(f"     [y] Yes  [n] No, correct it  [s] Skip")
    answer = input("     Your choice: ").strip().lower()

    if answer == "n":
        all_categories = get_all_categories()
        print(f"     Categories: {', '.join(all_categories)}")
        print(f"     (You can type a new category to create it)")
        correct = input("     Correct category: ").strip().capitalize()

        if not correct:
            print(f"     ✗ Empty input — skipping")
            return

        if correct in all_categories:
            save_correction(file_obs, correct)
            print(f"     ✓ Saved — next time I'll classify {file_obs['extension']} as {correct}")
        else:
            confirm = input(f"     '{correct}' doesn't exist yet. Create it? [y/N]: ").strip().lower()
            if confirm == "y":
                add_custom_category(correct)
                save_correction(file_obs, correct)
                print(f"     ✓ Created '{correct}' and saved correction")
            else:
                print(f"     Cancelled")

    elif answer == "y":
        print(f"     ✓ Got it")


def run_agent(
    dry_run: bool = True,
    confidence_threshold: float = 0.6,
    collect_feedback: bool = False
) -> None:

    print("\n── Desktop Organiser Agent ──────────────")
    print(f"  Mode:      {'DRY RUN' if dry_run else '⚠  LIVE — files will be moved'}")
    print(f"  Threshold: {confidence_threshold} confidence minimum")
    print(f"  Feedback:  {'on' if collect_feedback else 'off'}")
    print("─────────────────────────────────────────\n")

    observations = observe_desktop()
    if not observations:
        print("No files found on Desktop.")
        return
    print(f"Found {len(observations)} file(s) on Desktop.\n")

    action_log = []

    for file_obs in observations:

        # Step 1: Classify — memory → LLM → rules
        result = classify_file(file_obs)

        category   = result["category"]
        confidence = result["confidence"]
        method     = result["method"]
        reasoning  = result.get("reasoning", "")

        method_tag = {
            "memory":     "🧠 MEMORY",
            "llm":        "🤖 LLM",
            "rule-based": "📐 RULES"
        }.get(method, method.upper())

        print(f"  [{method_tag}] {file_obs['name']}")
        print(f"    Category:   {category}")
        print(f"    Confidence: {confidence}")
        if reasoning:
            print(f"    Reason:     {reasoning}")

        # Skip low-confidence
        if confidence < confidence_threshold:
            print(f"    ⚠ Skipping — below threshold ({confidence_threshold})\n")
            action_log.append({
                "name": file_obs["name"],
                "action": "skipped",
                "message": f"Low confidence: {confidence}"
            })
            if collect_feedback:
                ask_for_feedback(file_obs, result)
            continue

        # Skip unknown
        if category == "Unknown":
            print(f"    ⚠ Skipping — unknown category\n")
            action_log.append({
                "name": file_obs["name"],
                "action": "skipped",
                "message": "Unknown category"
            })
            if collect_feedback:
                ask_for_feedback(file_obs, result)
            continue

        # Step 2: Act
        action_result = act(file_obs, category, dry_run=dry_run)
        action_log.append(action_result)

        # Step 3: Collect feedback
        if collect_feedback:
            ask_for_feedback(file_obs, result)

        print()

    summarise_actions(action_log)

    if collect_feedback:
        print("  💡 Run 'python main.py --stats' to see what the agent has learned.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM-powered Desktop Organiser")

    parser.add_argument("--move", action="store_true",
                        help="Actually move files (default is dry run)")

    parser.add_argument("--feedback", action="store_true",
                        help="Ask for corrections after each classification")

    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Minimum confidence to act on (default: 0.6)")

    parser.add_argument("--stats", action="store_true",
                        help="Show memory stats and learned patterns")

    parser.add_argument("--clear-memory", action="store_true",
                        help="Wipe all learned patterns")

    args = parser.parse_args()

    if args.stats:
        show_stats()

    elif args.clear_memory:
        confirm = input("Clear all learned patterns? [y/N]: ")
        if confirm.lower() == "y":
            clear_memory()
        else:
            print("Cancelled.")

    else:
        run_agent(
            dry_run=not args.move,
            confidence_threshold=args.threshold,
            collect_feedback=args.feedback
        )