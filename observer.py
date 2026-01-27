from pathlib import Path

DESKTOP_PATH = Path.home() / "Desktop"

def observe_desktop():
    observations = []

    if not DESKTOP_PATH.exists():
        print(f"{DESKTOP_PATH} does not exist!")
        return observations

    for item in DESKTOP_PATH.iterdir():
        if item.is_file():
            stat = item.stat()
            observations.append({
                "name": item.name,
                "path": str(item),
                "size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "extension": item.suffix.lower()
            })

    return observations
from pathlib import Path
import logging
import time

# Logging setup
logging.basicConfig(
    filename="agent.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def observe_desktop(path=None):
    # Use Windows Desktop path by default if none provided
    if path is None:
        desktop = Path("C:/Users/namit/Desktop")  # <- your real Desktop
    else:
        desktop = Path(path)

    if not desktop.exists():
        print(f"{desktop} does not exist!")
        return []

    observations = []

    for item in desktop.iterdir():
        stats = item.stat()
        obs = {
            "name": item.name,
            "extension": item.suffix,
            "path": str(item),
            "is_file": item.is_file(),
            "size_bytes": stats.st_size,
            "last_modified": time.ctime(stats.st_mtime),
        }
        observations.append(obs)
        logging.info(f"Observed: {obs}")

    return observations

# Test run
if __name__ == "__main__":
    obs = observe_desktop()
    print(f"Observed {len(obs)} items")
    for o in obs:
        print(o)
