"""
memory.py — Persistent learning layer for the Desktop Organiser Agent.
"""

import json
from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path(__file__).parent / "memory.json"

DEFAULT_CATEGORIES = [
    "Documents", "Images", "Code", "Archives",
    "Installers", "Videos", "Audio", "Unknown"
]


def _load(memory_file=None) -> dict:
    path = Path(memory_file) if memory_file else MEMORY_FILE
    empty = {"patterns": [], "custom_categories": [], "stats": {"total_corrections": 0, "total_lookups": 0}}
    if not path.exists():
        return empty
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return empty


def _save(memory: dict, memory_file=None) -> None:
    path = Path(memory_file) if memory_file else MEMORY_FILE
    with open(path, "w") as f:
        json.dump(memory, f, indent=2)


def _extract_keywords(filename: str) -> set:
    stem = Path(filename).stem.lower()
    for sep in ["_", "-", ".", " "]:
        stem = stem.replace(sep, " ")
    return set(w for w in stem.split() if len(w) > 2)


def lookup(file_obs: dict, memory_file=None) -> dict | None:
    path = memory_file or MEMORY_FILE
    memory = _load(path)
    memory["stats"]["total_lookups"] += 1
    _save(memory, path)

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

        if pattern["filename"].lower() == filename:
            score = 0.98
            match_type = "exact-filename"
        elif pattern["extension"].lower() == extension:
            score = 0.92
            match_type = "exact-extension"
        else:
            pattern_keywords = _extract_keywords(pattern["filename"])
            overlap = incoming_keywords & pattern_keywords
            if overlap:
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

    if best_match and best_match["confidence"] >= 0.6:
        return best_match
    return None


def save_correction(file_obs: dict, correct_category: str, memory_file=None) -> None:
    path = memory_file or MEMORY_FILE
    all_categories = get_all_categories(path)
    if correct_category not in all_categories:
        add_custom_category(correct_category, path)

    memory = _load(path)

    for pattern in memory["patterns"]:
        if pattern["filename"].lower() == file_obs["name"].lower():
            pattern["correct_category"] = correct_category
            pattern["last_updated"] = datetime.now().isoformat()
            pattern["correction_count"] = pattern.get("correction_count", 1) + 1
            _save(memory, path)
            print(f"  [MEMORY] Updated existing pattern for {file_obs['name']}")
            return

    memory["patterns"].append({
        "filename": file_obs["name"],
        "extension": file_obs["extension"].lower(),
        "correct_category": correct_category,
        "first_seen": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "correction_count": 1
    })
    memory["stats"]["total_corrections"] += 1
    _save(memory, path)
    print(f"  [MEMORY] Saved: {file_obs['name']} → {correct_category}")


def get_all_categories(memory_file=None) -> list:
    path = memory_file or MEMORY_FILE
    memory = _load(path)
    return DEFAULT_CATEGORIES + memory.get("custom_categories", [])


def add_custom_category(name: str, memory_file=None) -> bool:
    path = memory_file or MEMORY_FILE
    name = name.strip().capitalize()
    if name in get_all_categories(path):
        return False
    memory = _load(path)
    if "custom_categories" not in memory:
        memory["custom_categories"] = []
    memory["custom_categories"].append(name)
    _save(memory, path)
    print(f"  [MEMORY] New category created: '{name}'")
    return True


def show_stats(memory_file=None) -> None:
    path = memory_file or MEMORY_FILE
    memory = _load(path)
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


def clear_memory(memory_file=None) -> None:
    path = Path(memory_file) if memory_file else MEMORY_FILE
    if path.exists():
        path.unlink()
    print("  [MEMORY] Cleared all patterns.")