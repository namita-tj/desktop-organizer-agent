"""
observer.py — Scans a directory and returns file observations.

Defaults to ~/Desktop but accepts any path via observe_desktop(path=...)
or the DESKTOP_PATH module-level variable.
"""

from pathlib import Path
from src.logger import get_logger

log = get_logger(__name__)

# Files to always skip
IGNORED_EXTENSIONS = {".DS_Store", ".localized"}
IGNORED_NAMES      = {".DS_Store", "desktop.ini", "Thumbs.db"}

DESKTOP_PATH = Path.home() / "Desktop"


def observe_desktop(path=None) -> list:
    scan_path = Path(path) if path else DESKTOP_PATH

    if not scan_path.exists():
        log.warning("Scan path does not exist: %s", scan_path)
        return []

    log.info("Scanning: %s", scan_path)
    observations = []

    for item in scan_path.iterdir():
        if not item.is_file():
            log.debug("Skipping non-file: %s", item.name)
            continue
        if item.name.startswith("."):
            log.debug("Skipping hidden file: %s", item.name)
            continue
        if item.name in IGNORED_NAMES:
            log.debug("Skipping ignored name: %s", item.name)
            continue
        if item.suffix in IGNORED_EXTENSIONS:
            log.debug("Skipping ignored extension: %s", item.name)
            continue

        stat = item.stat()
        observations.append({
            "name":          item.name,
            "path":          str(item),
            "size_bytes":    stat.st_size,
            "last_modified": stat.st_mtime,
            "extension":     item.suffix.lower()
        })
        log.debug("Found: %s (%d bytes)", item.name, stat.st_size)

    log.info("Found %d file(s)", len(observations))
    return observations