"""
logger.py — Centralised logging for the Desktop Organiser Agent.

Writes to both console (INFO+) and a rotating log file (DEBUG+).
Import get_logger() in any module that needs logging.

Log files are written to logs/ in the project root.
"""

import logging
import logging.handlers
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOGS_DIR / "agent.log"


def _setup() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger("desktop_organiser")

    if logger.handlers:
        return logger  # already configured — don't add duplicate handlers

    logger.setLevel(logging.DEBUG)

    # ── Console handler — INFO and above, clean format ────────────────────────
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    # ── File handler — DEBUG and above, full format, 1MB rotating, 3 backups ─
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def get_logger(name: str = "") -> logging.Logger:
    """
    Return a child logger under 'desktop_organiser'.
    Call once at module level:  log = get_logger(__name__)
    """
    _setup()
    if name:
        return logging.getLogger(f"desktop_organiser.{name}")
    return logging.getLogger("desktop_organiser")