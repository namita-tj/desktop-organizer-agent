"""
test_actor.py — Tests for actor.py

Pass criteria:
    1.  Dry run does not move files
    2.  Dry run returns action="dry_run"
    3.  Move creates correct folder structure
    4.  Move removes file from source
    5.  Move returns action="moved"
    6.  Collision handling appends timestamp, does not overwrite
    7.  Files already inside Organised/ are skipped
    8.  Result dict always has all required keys
    9.  PermissionError is caught and returned as action="error"
    10. Destination dir is created if it doesn't exist
"""

import pytest
from unittest.mock import patch
from src.actor import act, summarise_actions


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def desktop(tmp_path, monkeypatch):
    organised = tmp_path / "Organised"
    monkeypatch.setattr("src.actor.ORGANISED_ROOT", organised)
    monkeypatch.setattr("src.actor.MOVES_LOG", tmp_path / "moves.log")  # ← add this
    return tmp_path, organised


@pytest.fixture
def pdf_file(desktop):
    """A sample PDF file sitting on the fake Desktop."""
    tmp_path, _ = desktop
    source = tmp_path / "resume.pdf"
    source.write_text("fake pdf content")
    return {
        "name": "resume.pdf",
        "path": str(source),
        "extension": ".pdf",
        "size_bytes": 100
    }


# ── Dry run tests ──────────────────────────────────────────────────────────────

class TestDryRun:

    def test_dry_run_does_not_move_file(self, desktop, pdf_file):
        source = pdf_file["path"]
        act(pdf_file, "Documents", dry_run=True)
        assert __import__("pathlib").Path(source).exists()

    def test_dry_run_returns_correct_action(self, desktop, pdf_file):
        result = act(pdf_file, "Documents", dry_run=True)
        assert result["action"] == "dry_run"

    def test_dry_run_result_has_all_keys(self, desktop, pdf_file):
        result = act(pdf_file, "Documents", dry_run=True)
        assert "name" in result
        assert "action" in result
        assert "source" in result
        assert "destination" in result
        assert "message" in result

    def test_dry_run_destination_path_is_correct(self, desktop, pdf_file):
        _, organised = desktop
        result = act(pdf_file, "Documents", dry_run=True)
        assert "Documents" in result["destination"]
        assert "resume.pdf" in result["destination"]


# ── Move tests ─────────────────────────────────────────────────────────────────

class TestMove:

    def test_move_removes_file_from_source(self, desktop, pdf_file):
        source_path = __import__("pathlib").Path(pdf_file["path"])
        act(pdf_file, "Documents", dry_run=False)
        assert not source_path.exists()

    def test_move_creates_file_at_destination(self, desktop, pdf_file):
        _, organised = desktop
        act(pdf_file, "Documents", dry_run=False)
        assert (organised / "Documents" / "resume.pdf").exists()

    def test_move_creates_category_folder(self, desktop, pdf_file):
        _, organised = desktop
        act(pdf_file, "Documents", dry_run=False)
        assert (organised / "Documents").is_dir()

    def test_move_returns_action_moved(self, desktop, pdf_file):
        result = act(pdf_file, "Documents", dry_run=False)
        assert result["action"] == "moved"

    def test_move_result_has_all_keys(self, desktop, pdf_file):
        result = act(pdf_file, "Documents", dry_run=False)
        assert "name" in result
        assert "action" in result
        assert "source" in result
        assert "destination" in result
        assert "message" in result


# ── Collision handling ─────────────────────────────────────────────────────────

class TestCollisionHandling:

    def test_collision_does_not_overwrite_existing_file(self, desktop, pdf_file):
        _, organised = desktop
        dest_dir = organised / "Documents"
        dest_dir.mkdir(parents=True)
        existing = dest_dir / "resume.pdf"
        existing.write_text("original content")

        act(pdf_file, "Documents", dry_run=False)

        assert existing.read_text() == "original content"

    def test_collision_creates_timestamped_file(self, desktop, pdf_file):
        _, organised = desktop
        dest_dir = organised / "Documents"
        dest_dir.mkdir(parents=True)
        (dest_dir / "resume.pdf").write_text("original")

        result = act(pdf_file, "Documents", dry_run=False)

        # Destination should have a timestamp suffix
        assert result["destination"] != str(organised / "Documents" / "resume.pdf")
        assert "resume_" in result["destination"]
        assert result["action"] == "moved"

    def test_collision_both_files_exist_after_move(self, desktop, pdf_file):
        _, organised = desktop
        dest_dir = organised / "Documents"
        dest_dir.mkdir(parents=True)
        (dest_dir / "resume.pdf").write_text("original")

        act(pdf_file, "Documents", dry_run=False)

        files = list(dest_dir.iterdir())
        assert len(files) == 2


# ── Already organised ──────────────────────────────────────────────────────────

class TestAlreadyOrganised:

    def test_file_inside_organised_is_skipped(self, desktop, monkeypatch):
        tmp_path, organised = desktop
        # File is already inside Organised/
        already_there = organised / "Documents" / "resume.pdf"
        already_there.parent.mkdir(parents=True)
        already_there.write_text("content")

        file_obs = {
            "name": "resume.pdf",
            "path": str(already_there),
            "extension": ".pdf",
            "size_bytes": 100
        }

        result = act(file_obs, "Documents", dry_run=False)
        assert result["action"] == "skipped"
        assert already_there.exists()  # not moved


# ── Error handling ─────────────────────────────────────────────────────────────

class TestErrorHandling:

    def test_permission_error_returns_error_action(self, desktop, pdf_file):
        with patch("shutil.move", side_effect=PermissionError("denied")):
            result = act(pdf_file, "Documents", dry_run=False)

        assert result["action"] == "error"
        assert "Permission" in result["message"]

    def test_unexpected_error_returns_error_action(self, desktop, pdf_file):
        with patch("shutil.move", side_effect=OSError("disk full")):
            result = act(pdf_file, "Documents", dry_run=False)

        assert result["action"] == "error"

    def test_error_does_not_raise_exception(self, desktop, pdf_file):
        with patch("shutil.move", side_effect=Exception("something broke")):
            # Should not raise — errors are caught and returned
            result = act(pdf_file, "Documents", dry_run=False)
        assert result["action"] == "error"


# ── summarise_actions ──────────────────────────────────────────────────────────

class TestSummariseActions:

    def test_summarise_does_not_crash_on_empty_log(self):
        summarise_actions([])  # should not raise

    def test_summarise_counts_correctly(self, capsys):
        log = [
            {"action": "moved"},
            {"action": "moved"},
            {"action": "dry_run"},
            {"action": "skipped"},
        ]
        summarise_actions(log)
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "moved" in output
        assert "2" in output