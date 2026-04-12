"""
actor.py — Moves classified files into organised subfolders.

Always defaults to dry_run=True so nothing is moved unless
the user explicitly opts in. Safety first.
"""

import shutil
from pathlib import Path
from datetime import datetime


# Where organised folders will be created (sibling of Desktop)
ORGANISED_ROOT = Path.home() / "Desktop" / "Organised"


def act(file_obs: dict, category: str, dry_run: bool = True) -> dict:
    """
    Move a file into Desktop/Organised/<category>/.

    Args:
        file_obs:  The file observation dict from observer.py
        category:  The category string from classifier.py
        dry_run:   If True, only prints what would happen (default: True)

    Returns:
        {
            name:        str,
            action:      "moved" | "skipped" | "dry_run" | "error",
            source:      str,
            destination: str,
            message:     str
        }
    """
    source = Path(file_obs["path"])
    destination_dir = ORGANISED_ROOT / category
    destination = destination_dir / file_obs["name"]

    result = {
        "name": file_obs["name"],
        "source": str(source),
        "destination": str(destination),
    }

    # Don't move files that are already inside Organised/
    if ORGANISED_ROOT in source.parents:
        result.update({"action": "skipped", "message": "Already organised"})
        return result

    # Handle filename collisions — append timestamp
    if destination.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = destination.stem
        suffix = destination.suffix
        destination = destination_dir / f"{stem}_{timestamp}{suffix}"
        result["destination"] = str(destination)

    if dry_run:
        print(f"  [DRY RUN] Would move:")
        print(f"    {source}")
        print(f"    → {destination}")
        result.update({"action": "dry_run", "message": "Dry run — no files moved"})
        return result

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        print(f"  ✓ Moved: {file_obs['name']} → {category}/")
        result.update({"action": "moved", "message": "Success"})

    except PermissionError:
        msg = f"Permission denied moving {file_obs['name']}"
        print(f"  ✗ {msg}")
        result.update({"action": "error", "message": msg})

    except Exception as e:
        msg = f"Unexpected error: {e}"
        print(f"  ✗ {msg}")
        result.update({"action": "error", "message": msg})

    return result


def summarise_actions(action_log: list[dict]) -> None:
    """Print a clean summary of what the agent did."""
    counts = {}
    for entry in action_log:
        action = entry.get("action", "unknown")
        counts[action] = counts.get(action, 0) + 1

    print("\n── Summary ──────────────────────────────")
    for action, count in counts.items():
        print(f"  {action:12s}: {count} file(s)")
    print("─────────────────────────────────────────\n")