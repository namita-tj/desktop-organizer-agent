"""
main.py — Entry point for the Desktop Organiser Agent.

Usage:
    python main.py                        # Dry run on ~/Desktop
    python main.py --move                 # Actually moves files
    python main.py --move --feedback      # Moves files + asks for corrections
    python main.py --threshold 0.7        # Only act on high-confidence results
    python main.py --path ~/Documents     # Organise any folder, not just Desktop
    python main.py --stats                # Show what the agent has learned
    python main.py --clear-memory         # Wipe all learned patterns
    python main.py --undo                 # Undo the last run
    python main.py --audit                # Show recent audit log entries
"""

import argparse
from src.observer import observe_desktop
from src.classifier import classify_file
from src.actor import act, summarise_actions, undo_last_run, show_audit_log
from src.memory import save_correction, show_stats, clear_memory, get_all_categories, add_custom_category
from src.logger import get_logger

log = get_logger(__name__)


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
            print("     Empty input — skipping")
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
                print("     Cancelled")

    elif answer == "y":
        print("     ✓ Got it")


def run_agent(
    scan_path=None,
    dry_run: bool = True,
    confidence_threshold: float = 0.6,
    collect_feedback: bool = False
) -> None:

    log.info("=== Desktop Organiser Agent starting ===")
    log.info("Mode:      %s", "DRY RUN" if dry_run else "LIVE — files will be moved")
    log.info("Threshold: %.2f", confidence_threshold)
    log.info("Path:      %s", scan_path or "~/Desktop (default)")

    print("\n── Desktop Organiser Agent ──────────────")
    print(f"  Mode:      {'DRY RUN' if dry_run else '⚠  LIVE — files will be moved'}")
    print(f"  Threshold: {confidence_threshold} confidence minimum")
    print(f"  Feedback:  {'on' if collect_feedback else 'off'}")
    if scan_path:
        print(f"  Path:      {scan_path}")
    print("─────────────────────────────────────────\n")

    observations = observe_desktop(path=scan_path)
    if not observations:
        log.info("No files found — exiting")
        print("No files found.")
        return

    print(f"Found {len(observations)} file(s).\n")
    action_log = []

    for file_obs in observations:

        # Step 1: Classify — memory → LLM → rules
        result     = classify_file(file_obs)
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
        if result.get("subcategory"):
            print(f"    Subcategory: {result['subcategory']}")
        if result.get("suggested_filename"):
            print(f"    Suggested:  {result['suggested_filename']}")
        if result.get("is_sensitive"):
            print(f"    ⚠  SENSITIVE document")

        # Skip low-confidence
        if confidence < confidence_threshold:
            log.info("Skipping %s — low confidence (%.2f)", file_obs["name"], confidence)
            print(f"    ⚠ Skipping — below threshold ({confidence_threshold})\n")
            action_log.append({"name": file_obs["name"], "action": "skipped",
                                "message": f"Low confidence: {confidence}"})
            if collect_feedback:
                ask_for_feedback(file_obs, result)
            continue

        # Skip unknown
        if category == "Unknown":
            log.info("Skipping %s — unknown category", file_obs["name"])
            print("    ⚠ Skipping — unknown category\n")
            action_log.append({"name": file_obs["name"], "action": "skipped",
                                "message": "Unknown category"})
            if collect_feedback:
                ask_for_feedback(file_obs, result)
            continue

        # Step 2: Act — pass full classification for audit log enrichment
        action_result = act(
            file_obs,
            category,
            dry_run=dry_run,
            classification=result
        )
        action_log.append(action_result)

        if collect_feedback:
            ask_for_feedback(file_obs, result)

        print()

    summarise_actions(action_log)
    log.info("=== Agent finished ===")

    if not dry_run:
        print("  💡 Run 'python main.py --audit' to see the full audit trail.")
        print("  💡 Run 'python main.py --undo' to reverse this run.\n")

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

    parser.add_argument("--path", type=str, default=None,
                        help="Path to organise (default: ~/Desktop)")

    parser.add_argument("--stats", action="store_true",
                        help="Show memory stats and learned patterns")

    parser.add_argument("--clear-memory", action="store_true",
                        help="Wipe all learned patterns")

    parser.add_argument("--undo", action="store_true",
                        help="Undo the last run — moves files back to original locations")

    parser.add_argument("--audit", action="store_true",
                        help="Show recent audit log entries")

    parser.add_argument("--audit-lines", type=int, default=20,
                        help="Number of audit log lines to show (default: 20)")

    args = parser.parse_args()

    if args.stats:
        show_stats()

    elif args.clear_memory:
        confirm = input("Clear all learned patterns? [y/N]: ")
        if confirm.lower() == "y":
            clear_memory()
        else:
            print("Cancelled.")

    elif args.undo:
        undo_last_run()

    elif args.audit:
        show_audit_log(last_n=args.audit_lines)

    else:
        run_agent(
            scan_path=args.path,
            dry_run=not args.move,
            confidence_threshold=args.threshold,
            collect_feedback=args.feedback
        )