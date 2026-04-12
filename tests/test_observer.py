"""
test_observer.py — Tests for observer.py
"""

from pathlib import Path
from src.observer import observe_desktop


def make_fake_desktop(tmp_path) -> Path:
    """Create a temporary fake Desktop folder for each test."""
    fake_desktop = tmp_path / "Desktop"
    fake_desktop.mkdir()
    return fake_desktop


def test_finds_normal_file(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    (desktop / "resume.pdf").write_text("fake content")

    results = observe_desktop(path=desktop)
    names = [f["name"] for f in results]

    assert "resume.pdf" in names


def test_skips_hidden_files(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    (desktop / ".DS_Store").touch()
    (desktop / ".hidden_config").touch()
    (desktop / "visible.txt").write_text("visible")

    results = observe_desktop(path=desktop)
    names = [f["name"] for f in results]

    assert ".DS_Store" not in names
    assert ".hidden_config" not in names
    assert "visible.txt" in names


def test_skips_system_files(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    (desktop / "desktop.ini").touch()
    (desktop / "Thumbs.db").touch()
    (desktop / "my_notes.txt").write_text("notes")

    results = observe_desktop(path=desktop)
    names = [f["name"] for f in results]

    assert "desktop.ini" not in names
    assert "Thumbs.db" not in names
    assert "my_notes.txt" in names


def test_skips_directories(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    (desktop / "my_folder").mkdir()
    (desktop / "my_file.txt").write_text("x")

    results = observe_desktop(path=desktop)
    names = [f["name"] for f in results]

    assert "my_folder" not in names
    assert "my_file.txt" in names


def test_returns_correct_metadata(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    test_file = desktop / "report.pdf"
    test_file.write_text("hello world")  # 11 bytes

    results = observe_desktop(path=desktop)

    assert len(results) == 1
    f = results[0]
    assert f["name"] == "report.pdf"
    assert f["extension"] == ".pdf"
    assert f["path"] == str(test_file)
    assert f["size_bytes"] == 11
    assert "last_modified" in f


def test_extension_is_lowercase(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    (desktop / "Photo.JPG").touch()

    results = observe_desktop(path=desktop)

    assert results[0]["extension"] == ".jpg"


def test_empty_desktop_returns_empty_list(tmp_path):
    desktop = make_fake_desktop(tmp_path)

    results = observe_desktop(path=desktop)

    assert results == []


def test_nonexistent_desktop_returns_empty_list(tmp_path):
    fake_path = tmp_path / "DoesNotExist"

    results = observe_desktop(path=fake_path)

    assert results == []


def test_multiple_files_all_returned(tmp_path):
    desktop = make_fake_desktop(tmp_path)
    files = ["notes.txt", "photo.png", "script.py", "data.zip"]
    for name in files:
        (desktop / name).write_text("x")

    results = observe_desktop(path=desktop)
    names = [f["name"] for f in results]

    for name in files:
        assert name in names
    assert len(results) == len(files)


def test_mixed_desktop_only_returns_valid_files(tmp_path):
    desktop = make_fake_desktop(tmp_path)

    (desktop / "essay.docx").write_text("x")
    (desktop / "app.py").write_text("x")
    (desktop / ".DS_Store").touch()
    (desktop / "desktop.ini").touch()
    (desktop / "some_folder").mkdir()

    results = observe_desktop(path=desktop)
    names = [f["name"] for f in results]

    assert "essay.docx" in names
    assert "app.py" in names
    assert len(results) == 2