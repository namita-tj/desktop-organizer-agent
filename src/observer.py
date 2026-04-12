"""
observer.py — Scans the Desktop and returns file observations.
"""

from pathlib import Path

# Files to always skip
IGNORED_EXTENSIONS = {".DS_Store", ".localized"}
IGNORED_NAMES = {".DS_Store", "desktop.ini", "Thumbs.db"}


DESKTOP_PATH = Path.home() / "Desktop"

def observe_desktop(path=None):
    scan_path = path or DESKTOP_PATH
    observations = []
    if not scan_path.exists():
        print(f"{scan_path} does not exist!")
        return observations

    for item in scan_path.iterdir():
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