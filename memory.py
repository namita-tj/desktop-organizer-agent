"""
memory.py — Persistent learning layer for the Desktop Organiser Agent.

How it works:
    Every time the user corrects a classification, that correction is saved
    here as a "pattern". Next time a similar file appears, the memory is
    checked first — before calling Ollama — so the agent learns over time.

Storage:
    All patterns are saved to memory.json in the project directory.
    This file grows with every correction and is the agent's "brain".

Pattern matching logic:
    1. Exact extension match         → confidence 0.92
    2. Exact filename match          → confidence 0.98 (strongest signal)
    3. Keyword overlap in filename   → confidence 0.75
    4. No match                      → returns None (fall through to Ollama)
"""

import json
from pathlib import Path
from datetime import datetime

# Where the memory file lives — same folder as the scripts
MEMORY_FILE = Path(__file__).parent / "memory.json"

DEFAULT_CATEGORIES = [
    "Documents", "Images", "Code", "Archives",
    "Installers", "Videos", "Audio", "Unknown"
]
# ── Internal helpers ───────────────────────────────────────────────────────────

def _load() -> dict:
    """Load memory from disk. Returns empty structure if file doesn't exist."""
    if not MEMORY_FILE.exists():
        return {"patterns": [], "custom_categories": [], "stats": {"total_corrections": 0, "total_lookups": 0}}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Corrupted file — start fresh
        return {"patterns": [], "custom_categories": [], "stats": {"total_corrections": 0, "total_lookups": 0}}


def _save(memory: dict) -> None:
    """Write memory to disk."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def _extract_keywords(filename: str) -> set[str]:
    """
    Split a filename into meaningful keywords.
    e.g. "resume_final_v3.pdf" → {"resume", "final", "v3"}
    """
    # Remove extension, lowercase, split on common separators
    stem = Path(filename).stem.lower()
    for sep in ["_", "-", ".", " "]:
        stem = stem.replace(sep, " ")
    return set(w for w in stem.split() if len(w) > 2)  # skip tiny tokens


# ── Public interface ───────────────────────────────────────────────────────────

def lookup(file_obs: dict) -> dict | None:
    """
    Check memory for a pattern matching this file.

    Matching priority (strongest → weakest):
        1. Exact filename match  → 0.98 confidence
        2. Exact extension match → 0.92 confidence
        3. Keyword overlap       → 0.75 confidence

    Returns a result dict (same shape as classify_file) or None if no match.
    """
    memory = _load()
    memory["stats"]["total_lookups"] += 1
    _save(memory)

    patterns = memory["patterns"]
    if not patterns:
        return None

    filename = file_obs["name"].lower()
    extension = file_obs["extension"].lower()
    incoming_keywords = _extract_keywords(file_obs["name"])

    best_match = None
    best_score = 0.0

    for pattern in patterns:
        score = 0.0
        match_type = ""

        # Signal 1 — exact filename (strongest)
        if pattern["filename"].lower() == filename:
            score = 0.98
            match_type = "exact-filename"

        # Signal 2 — exact extension
        elif pattern["extension"].lower() == extension:
            score = 0.92
            match_type = "exact-extension"

        # Signal 3 — keyword overlap
        else:
            pattern_keywords = _extract_keywords(pattern["filename"])
            overlap = incoming_keywords & pattern_keywords
            if overlap:
                # More overlap = higher confidence, capped at 0.75
                score = min(0.5 + (len(overlap) * 0.1), 0.75)
                match_type = f"keyword-overlap:{','.join(overlap)}"

        if score > best_score:
            best_score = score
            best_match = {
                "name": file_obs["name"],
                "category": pattern["correct_category"],
                "confidence": round(score, 2),
                "reasoning": f"Learned from past correction ({match_type})",
                "method": "memory"
            }

    # Only return if confidence is meaningful
    if best_match and best_match["confidence"] >= 0.75:
        return best_match

    return None


def save_correction(file_obs: dict, correct_category: str) -> None:
    """
    Save a user correction to memory.
    Called when the user says the agent got a classification wrong.

    Args:
        file_obs:          The file that was misclassified
        correct_category:  What the user said it should be
    """
    memory = _load()

    # Check if we already have a pattern for this exact filename
    # If so, update it rather than adding a duplicate
    for pattern in memory["patterns"]:
        if pattern["filename"].lower() == file_obs["name"].lower():
            pattern["correct_category"] = correct_category
            pattern["last_updated"] = datetime.now().isoformat()
            pattern["correction_count"] = pattern.get("correction_count", 1) + 1
            _save(memory)
            print(f"  [MEMORY] Updated existing pattern for {file_obs['name']}")
            return

    # New pattern — add it
    new_pattern = {
        "filename": file_obs["name"],
        "extension": file_obs["extension"].lower(),
        "correct_category": correct_category,
        "first_seen": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "correction_count": 1
    }

    memory["patterns"].append(new_pattern)
    memory["stats"]["total_corrections"] += 1
    _save(memory)
    print(f"  [MEMORY] Saved: {file_obs['name']} → {correct_category}")

def get_all_categories() -> list:
    """Return built-in + user-created categories."""
    memory = _load()
    return DEFAULT_CATEGORIES + memory.get("custom_categories", [])


def add_custom_category(name: str) -> bool:
    """Add a new category to memory. Returns False if it already exists."""
    name = name.strip().capitalize()
    if name in get_all_categories():
        return False
    memory = _load()
    if "custom_categories" not in memory:
        memory["custom_categories"] = []
    memory["custom_categories"].append(name)
    _save(memory)
    print(f"  [MEMORY] New category created: '{name}'")
    return True

def show_stats() -> None:
    """Print a summary of what the memory currently knows."""
    memory = _load()
    patterns = memory["patterns"]
    stats = memory["stats"]

    print("\n── Memory Stats ─────────────────────────────")
    print(f"  Patterns stored:    {len(patterns)}")
    print(f"  Total corrections:  {stats['total_corrections']}")
    print(f"  Total lookups:      {stats['total_lookups']}")

    if patterns:
        print("\n  Known patterns:")
        for p in patterns:
            print(f"    {p['extension']:8s} | {p['filename']:35s} → {p['correct_category']}")
    print("─────────────────────────────────────────────\n")


def clear_memory() -> None:
    """Wipe all learned patterns. Use with caution."""
    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
    print("  [MEMORY] Cleared all patterns.")