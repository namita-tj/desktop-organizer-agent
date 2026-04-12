"""
actor.py — Moves classified files and writes a structured audit trail.

Every move is logged to moves.log as a JSON line containing:
- original filename, source, destination
- category, subcategory, confidence
- extracted entities (amounts, dates, references)
- whether the document was flagged as sensitive
- suggested renamed filename (enterprise naming convention)
- timestamp and operator (llm / memory / rule-based)

This audit trail is what compliance teams in legal, accounting,
and healthcare actually pay for.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Where organised folders will be created
ORGANISED_ROOT = Path.home() / "Desktop" / "Organised"

# Audit log — one JSON object per line (JSON Lines format)
MOVES_LOG = Path(__file__).parent.parent / "logs" / "moves.log"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _write_audit(entry: dict) -> None:
    """Append one JSON line to moves.log."""
    try:
        MOVES_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(MOVES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"  [AUDIT] Warning — could not write to log: {e}")


def _build_audit_entry(
    action: str,
    file_obs: dict,
    category: str,
    source: Path,
    destination: Path | None,
    classification: dict | None,
    message: str = ""
) -> dict:
    """
    Build a structured audit entry from all available information.
    classification is the full result dict from classify_file().
    """
    entry = {
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "action":          action,
        "name":            file_obs["name"],
        "source":          str(source),
        "destination":     str(destination) if destination else None,
        "category":        category,
        "message":         message,
    }

    # Enrich with classification metadata if available
    if classification:
        entry.update({
            "subcategory":        classification.get("subcategory", ""),
            "confidence":         classification.get("confidence", 0.0),
            "operator":           classification.get("method", "unknown"),
            "suggested_filename": classification.get("suggested_filename", ""),
            "reasoning":          classification.get("reasoning", ""),
            "entities":           classification.get("entities", {}),
            "is_sensitive":       classification.get("is_sensitive", False),
        })

    return entry


# ── Public interface ───────────────────────────────────────────────────────────

def act(
    file_obs: dict,
    category: str,
    dry_run: bool = True,
    classification: dict | None = None
) -> dict:
    """
    Move a file into Organised/<category>/ and write to audit log.

    Args:
        file_obs:       File observation dict from observer.py
        category:       Category string from classifier.py
        dry_run:        If True, only shows what would happen (default: True)
        classification: Full classification result — used to enrich audit log

    Returns:
        {
            name, action, source, destination, message
        }
    """
    source = Path(file_obs["path"])
    destination_dir = ORGANISED_ROOT / category
    destination = destination_dir / file_obs["name"]

    result = {
        "name":        file_obs["name"],
        "source":      str(source),
        "destination": str(destination),
    }

    # Skip files already inside Organised/
    if ORGANISED_ROOT in source.parents:
        result.update({"action": "skipped", "message": "Already organised"})
        _write_audit(_build_audit_entry(
            "skipped", file_obs, category, source, None, classification,
            "Already organised"
        ))
        return result

    # Handle filename collisions — append timestamp, never overwrite
    if destination.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = destination.stem
        suffix = destination.suffix
        destination = destination_dir / f"{stem}_{timestamp}{suffix}"
        result["destination"] = str(destination)

    # Dry run — log intent but don't move
    if dry_run:
        print(f"  [DRY RUN] Would move:")
        print(f"    {source}")
        print(f"    → {destination}")
        result.update({"action": "dry_run", "message": "Dry run — no files moved"})
        return result  # dry runs are not written to audit log

    # Live move
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        print(f"  ✓ Moved: {file_obs['name']} → {category}/")
        result.update({"action": "moved", "message": "Success"})

        # Write full audit entry
        _write_audit(_build_audit_entry(
            "moved", file_obs, category, source, destination,
            classification, "Success"
        ))

        # Warn if sensitive
        if classification and classification.get("is_sensitive"):
            print(f"  ⚠  SENSITIVE document flagged — check audit log")

    except PermissionError:
        msg = f"Permission denied moving {file_obs['name']}"
        print(f"  ✗ {msg}")
        result.update({"action": "error", "message": msg})
        _write_audit(_build_audit_entry(
            "error", file_obs, category, source, None, classification, msg
        ))

    except Exception as e:
        msg = f"Unexpected error: {e}"
        print(f"  ✗ {msg}")
        result.update({"action": "error", "message": msg})
        _write_audit(_build_audit_entry(
            "error", file_obs, category, source, None, classification, msg
        ))

    return result


def undo_last_run() -> None:
    """
    Read moves.log in reverse and move files back to their original location.
    Only undoes the most recent run (entries since last agent start).
    """
    if not MOVES_LOG.exists():
        print("  No move log found — nothing to undo.")
        return

    with open(MOVES_LOG, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    # Only undo successful moves
    moves = [e for e in entries if e["action"] == "moved"]

    if not moves:
        print("  No moves found in log — nothing to undo.")
        return

    # Find entries from the most recent run — same minute as last entry
    last_timestamp = moves[-1]["timestamp"][:16]  # "2026-04-12T20:02"
    last_run = [m for m in moves if m["timestamp"][:16] == last_timestamp]

    print(f"\n── Undoing {len(last_run)} move(s) ──────────────")

    undone = 0
    failed = 0

    for entry in reversed(last_run):
        source = Path(entry["destination"])   # where it was moved TO
        destination = Path(entry["source"])   # where it originally was

        if not source.exists():
            print(f"  ✗ Can't find {source.name} — skipping")
            failed += 1
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            print(f"  ✓ Restored: {source.name} → {destination.parent}")

            # Log the undo
            _write_audit({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "undone",
                "name": entry["name"],
                "source": str(source),
                "destination": str(destination),
                "category": entry.get("category", ""),
                "message": "Undo successful"
            })
            undone += 1

        except Exception as e:
            print(f"  ✗ Failed to restore {source.name}: {e}")
            failed += 1

    print(f"\n  Restored: {undone}  Failed: {failed}")
    print("─────────────────────────────────────────\n")


def show_audit_log(last_n: int = 20) -> None:
    """Print the last N entries from the audit log in a readable format."""
    if not MOVES_LOG.exists():
        print("  No audit log found.")
        return

    with open(MOVES_LOG, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    recent = entries[-last_n:]
    print(f"\n── Audit Log (last {len(recent)} entries) ────────")

    for e in recent:
        ts = e["timestamp"][:19].replace("T", " ")
        action = e["action"].upper()
        name = e["name"]
        cat = e.get("category", "")
        sensitive = " ⚠ SENSITIVE" if e.get("is_sensitive") else ""
        print(f"  {ts}  [{action:8s}]  {name} → {cat}{sensitive}")

    print("─────────────────────────────────────────\n")


def summarise_actions(action_log: list[dict]) -> None:
    """Print a clean summary of what the agent did this run."""
    counts = {}
    for entry in action_log:
        action = entry.get("action", "unknown")
        counts[action] = counts.get(action, 0) + 1

    print("\n── Summary ──────────────────────────────")
    for action, count in counts.items():
        print(f"  {action:12s}: {count} file(s)")
    print("─────────────────────────────────────────\n")