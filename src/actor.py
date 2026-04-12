"""
actor.py — Moves classified files into organised subfolders.

Always defaults to dry_run=True so nothing is moved unless
the user explicitly opts in. Safety first.

Every move is appended to logs/moves.log as a JSON audit trail.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from src.logger import get_logger

log = get_logger(__name__)

# Where organised folders will be created
ORGANISED_ROOT = Path.home() / "Desktop" / "Organised"

# Audit log — one JSON object per line
MOVES_LOG = Path(__file__).parent.parent / "logs" / "moves.log"


def _write_audit(entry: dict) -> None:
    """Append a single JSON line to the moves audit log."""
    try:
        MOVES_LOG.parent.mkdir(exist_ok=True)
        with open(MOVES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        log.warning("Could not write to audit log: %s", e)


def act(file_obs: dict, category: str, dry_run: bool = True) -> dict:
    """
    Move a file into <ORGANISED_ROOT>/<category>/.

    Args:
        file_obs:  The file observation dict from observer.py
        category:  The category string from classifier.py
        dry_run:   If True, only logs what would happen (default: True)

    Returns:
        {
            name:        str,
            action:      "moved" | "skipped" | "dry_run" | "error",
            source:      str,
            destination: str,
            message:     str
        }
    """
    source          = Path(file_obs["path"])
    destination_dir = ORGANISED_ROOT / category
    destination     = destination_dir / file_obs["name"]

    result = {
        "name":        file_obs["name"],
        "source":      str(source),
        "destination": str(destination),
    }

    # Don't move files already inside Organised/
    if ORGANISED_ROOT in source.parents:
        log.info("Skipping %s — already organised", file_obs["name"])
        result.update({"action": "skipped", "message": "Already organised"})
        return result

    # Handle filename collisions — append timestamp
    if destination.exists():
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = destination_dir / f"{destination.stem}_{timestamp}{destination.suffix}"
        result["destination"] = str(destination)
        log.debug("Collision detected — renamed to %s", destination.name)

    if dry_run:
        log.info("[DRY RUN] Would move: %s -> %s", source.name, destination)
        result.update({"action": "dry_run", "message": "Dry run — no files moved"})
        return result

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        log.info("Moved: %s -> %s/", file_obs["name"], category)
        result.update({"action": "moved", "message": "Success"})

        _write_audit({
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "action":      "moved",
            "name":        file_obs["name"],
            "source":      str(source),
            "destination": str(destination),
            "category":    category
        })

    except PermissionError:
        msg = f"Permission denied moving {file_obs['name']}"
        log.error(msg)
        result.update({"action": "error", "message": msg})
        _write_audit({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action":    "error",
            "name":      file_obs["name"],
            "source":    str(source),
            "message":   msg
        })

    except Exception as e:
        msg = f"Unexpected error: {e}"
        log.error("Error moving %s: %s", file_obs["name"], e)
        result.update({"action": "error", "message": msg})
        _write_audit({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action":    "error",
            "name":      file_obs["name"],
            "source":    str(source),
            "message":   msg
        })

    return result


def summarise_actions(action_log: list[dict]) -> None:
    """Log a clean summary of what the agent did."""
    counts = {}
    for entry in action_log:
        action = entry.get("action", "unknown")
        counts[action] = counts.get(action, 0) + 1

    log.info("── Summary ──────────────────────────────")
    for action, count in counts.items():
        log.info("  %-12s: %d file(s)", action, count)
    log.info("─────────────────────────────────────────")