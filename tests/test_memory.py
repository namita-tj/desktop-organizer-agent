"""
test_memory.py — Tests for memory.py

Pass criteria:
    1.  Save and retrieve exact filename    → 0.98 confidence
    2.  Extension match on different file   → 0.92 confidence
    3.  No match returns None
    4.  Keyword overlap match               → 0.75 confidence
    5.  Correction updates existing pattern — no duplicate
    6.  Custom category created and persists
    7.  Duplicate category not added twice
    8.  save_correction auto-creates new category
    9.  clear_memory wipes patterns and custom categories
    10. Corrupted JSON handled gracefully
    11. Stats increment correctly

Isolation:
    Every test uses tmp_path to redirect MEMORY_FILE to a fresh
    temporary location. No test ever touches the real memory.json.
"""

import json
import pytest
from pathlib import Path
from src.memory import (
    lookup,
    save_correction,
    get_all_categories,
    add_custom_category,
    show_stats,
    clear_memory,
    DEFAULT_CATEGORIES,
    MEMORY_FILE,
    _load,
)


# ── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_memory(tmp_path, monkeypatch):
    """
    Redirect MEMORY_FILE to a temp location for every test automatically.
    autouse=True means this runs for every test without needing to declare it.
    """
    fake_memory = tmp_path / "memory.json"
    monkeypatch.setattr("src.memory.MEMORY_FILE", fake_memory)
    return fake_memory


# ── Sample file observations ───────────────────────────────────────────────────

LNK_FILE = {"name": "arcade_adventure.lnk", "extension": ".lnk", "size_bytes": 100}
PY_FILE  = {"name": "data_pipeline.py",      "extension": ".py",  "size_bytes": 8192}
PDF_FILE = {"name": "resume_final.pdf",       "extension": ".pdf", "size_bytes": 204800}


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_lookup_returns_none_when_memory_empty():
    """No patterns saved → lookup must return None, not crash."""
    result = lookup(LNK_FILE)
    assert result is None


def test_save_and_lookup_exact_filename():
    """Saving a correction then looking up the same filename → 0.98 confidence."""
    save_correction(LNK_FILE, "App")
    result = lookup(LNK_FILE)

    assert result is not None
    assert result["category"] == "App"
    assert result["confidence"] == 0.98
    assert result["method"] == "memory"


def test_extension_match_gives_lower_confidence():
    """
    Save a pattern for one .lnk file, look up a DIFFERENT .lnk file.
    Should match on extension → 0.92 confidence, not 0.98.
    """
    save_correction(LNK_FILE, "App")

    different_lnk = {"name": "docker_desktop.lnk", "extension": ".lnk", "size_bytes": 100}
    result = lookup(different_lnk)

    assert result is not None
    assert result["category"] == "App"
    assert result["confidence"] == 0.92


def test_no_match_returns_none():
    """A file with no matching pattern or extension → None."""
    save_correction(LNK_FILE, "App")

    unknown_file = {"name": "random_xyz.blob", "extension": ".blob", "size_bytes": 100}
    result = lookup(unknown_file)

    assert result is None


def test_keyword_overlap_match():
    """
    Filename keyword overlap should produce a match.
    'arcade_adventure' and 'arcade_game' share 'arcade' → keyword match.
    """
    save_correction(LNK_FILE, "App")  # saves "arcade_adventure.lnk"

    similar_file = {"name": "arcade_game.exe", "extension": ".exe", "size_bytes": 100}
    result = lookup(similar_file)

    # keyword overlap — confidence should be between 0.5 and 0.75
    assert result is not None
    assert result["confidence"] >= 0.5
    assert result["confidence"] <= 0.75
    assert result["category"] == "App"


def test_correction_updates_existing_pattern():
    """
    Correcting the same file twice should update the category,
    not create a duplicate entry.
    """
    save_correction(LNK_FILE, "App")
    save_correction(LNK_FILE, "Shortcuts")  # correct it again

    memory = _load()

    assert len(memory["patterns"]) == 1                          # no duplicate
    assert memory["patterns"][0]["correct_category"] == "Shortcuts"  # updated


def test_correction_count_increments_on_update():
    """Each re-correction of the same file should increment correction_count."""
    save_correction(LNK_FILE, "App")
    save_correction(LNK_FILE, "Shortcuts")

    memory = _load()
    assert memory["patterns"][0]["correction_count"] == 2


def test_custom_category_created_and_persists():
    """A new custom category should appear in get_all_categories() after creation."""
    add_custom_category("Uni")

    all_cats = get_all_categories()
    assert "Uni" in all_cats


def test_default_categories_always_present():
    """Default categories should always be in get_all_categories()."""
    all_cats = get_all_categories()

    for cat in DEFAULT_CATEGORIES:
        assert cat in all_cats


def test_duplicate_category_not_added():
    """Adding the same custom category twice should only store it once."""
    add_custom_category("Uni")
    add_custom_category("Uni")

    memory = _load()
    assert memory["custom_categories"].count("Uni") == 1


def test_save_correction_auto_creates_new_category():
    """
    If you save a correction with a category that doesn't exist yet,
    it should be automatically created — no manual add_custom_category needed.
    """
    save_correction(LNK_FILE, "NewCategory")

    all_cats = get_all_categories()
    assert "Newcategory" in all_cats or "NewCategory" in all_cats  # handles capitalise()

    result = lookup(LNK_FILE)
    assert result["category"] in ("Newcategory", "NewCategory")


def test_clear_memory_wipes_everything():
    """clear_memory() should remove all patterns and custom categories."""
    save_correction(LNK_FILE, "App")
    add_custom_category("Uni")
    clear_memory()

    memory = _load()
    assert memory["patterns"] == []
    assert memory.get("custom_categories", []) == []


def test_total_corrections_increments():
    """stats.total_corrections should go up with each new correction."""
    save_correction(LNK_FILE, "App")
    save_correction(PY_FILE, "Code")

    memory = _load()
    assert memory["stats"]["total_corrections"] == 2


def test_total_lookups_increments():
    """stats.total_lookups should increment on every lookup call."""
    lookup(LNK_FILE)
    lookup(LNK_FILE)
    lookup(LNK_FILE)

    memory = _load()
    assert memory["stats"]["total_lookups"] == 3


def test_corrupted_json_handled_gracefully(tmp_path, monkeypatch):
    """
    If memory.json is corrupted (invalid JSON), _load() should
    return an empty structure without crashing.
    """
    fake_memory = tmp_path / "bad_memory.json"
    fake_memory.write_text("{ this is not valid json !!!}")
    monkeypatch.setattr("src.memory.MEMORY_FILE", fake_memory)

    memory = _load()

    assert memory["patterns"] == []
    assert memory["stats"]["total_corrections"] == 0


def test_lookup_result_has_correct_shape():
    """Result dict from lookup should have all required keys."""
    save_correction(LNK_FILE, "App")
    result = lookup(LNK_FILE)

    assert "name" in result
    assert "category" in result
    assert "confidence" in result
    assert "reasoning" in result
    assert "method" in result
    assert result["method"] == "memory"


def test_multiple_patterns_returns_best_match():
    """
    With multiple patterns saved, lookup should return the highest
    confidence match — exact filename beats extension match.
    """
    # Save a pattern for a different .lnk file
    other_lnk = {"name": "other_app.lnk", "extension": ".lnk", "size_bytes": 100}
    save_correction(other_lnk, "Shortcuts")

    # Save exact match for our file
    save_correction(LNK_FILE, "App")

    result = lookup(LNK_FILE)

    # Exact filename match should win
    assert result["category"] == "App"
    assert result["confidence"] == 0.98