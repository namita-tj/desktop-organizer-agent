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
