"""
observer.py — Scans the Desktop and returns file observations.
"""

from pathlib import Path

DESKTOP_PATH = Path.home() / "Desktop"

# Files to always skip
IGNORED_EXTENSIONS = {".DS_Store", ".localized"}
IGNORED_NAMES = {".DS_Store", "desktop.ini", "Thumbs.db"}


def observe_desktop() -> list[dict]:
    """
    Scan the Desktop and return a list of file observation dicts.

    Each dict contains:
        name, path, size_bytes, last_modified, extension
    """
    observations = []

    if not DESKTOP_PATH.exists():
        print(f"Desktop not found at: {DESKTOP_PATH}")
        return observations

    for item in DESKTOP_PATH.iterdir():
        # Skip directories, hidden files, and system files
        if not item.is_file():
            continue
        if item.name.startswith("."):
            continue
        if item.name in IGNORED_NAMES:
            continue
        if item.suffix in IGNORED_EXTENSIONS:
            continue

        stat = item.stat()
        observations.append({
            "name": item.name,
            "path": str(item),
            "size_bytes": stat.st_size,
            "last_modified": stat.st_mtime,
            "extension": item.suffix.lower()
        })

    return observations