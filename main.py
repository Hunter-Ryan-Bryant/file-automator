from pathlib import Path
import shutil
import logging
import argparse

LOG_FILE = "file_automator.log"

DIRECTORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".csv", ".pptx"},
    "Videos": {".mp4", ".mov", ".mkv", ".avi"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {".py", ".js", ".html", ".css", ".json", ".cpp"},
}
OTHER_FOLDER = "Others"


def setup_logging(log_path: Path) -> None:
    """Log to the console and to an audit log file."""
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")):
        handler.setFormatter(formatter)
        root.addHandler(handler)


def category_for(file_ext: str) -> str:
    for category, extensions in DIRECTORIES.items():
        if file_ext in extensions:
            return category
    return OTHER_FOLDER


def unique_destination(dest_folder: Path, filename: str) -> Path:
    """Return a path in dest_folder that does not exist yet: name.ext, name_1.ext, name_2.ext, ..."""
    candidate = dest_folder / filename
    stem, suffix = candidate.stem, candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = dest_folder / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def organize_directory(target_dir: Path) -> dict:
    """Move each file in target_dir into a category subfolder. Returns counts of moved/skipped/failed files."""
    stats = {"moved": 0, "skipped": 0, "failed": 0}
    if not target_dir.exists() or not target_dir.is_dir():
        logging.error(f"Target directory does not exist or is invalid: {target_dir}")
        return stats

    logging.info(f"Starting organization for: {target_dir}")
    for item in target_dir.iterdir():
        if item.is_dir() or item.name.startswith(".") or item.name == LOG_FILE:
            logging.info(f"Skipped: {item.name}")
            stats["skipped"] += 1
            continue

        category = category_for(item.suffix.lower())
        try:
            dest_folder = target_dir / category
            dest_folder.mkdir(exist_ok=True)
            dest_path = unique_destination(dest_folder, item.name)
            shutil.move(str(item), str(dest_path))
        except (PermissionError, OSError) as exc:
            logging.error(f"Failed to move {item.name}: {exc}")
            stats["failed"] += 1
            continue

        if dest_path.name != item.name:
            logging.info(f"Moved: {item.name} -> {category}/{dest_path.name} (renamed to avoid overwrite)")
        else:
            logging.info(f"Moved: {item.name} -> {category}/")
        stats["moved"] += 1

    logging.info(
        f"Finished: {stats['moved']} moved, {stats['skipped']} skipped, {stats['failed']} failed"
    )
    return stats


def main():
    parser = argparse.ArgumentParser(description="Automate organizing files in a directory")
    parser.add_argument(
        "--path",
        type=str,
        default=str(Path.home() / "Downloads"),
        help="Path to the directory you want to organize (defaults to Downloads)",
    )
    args = parser.parse_args()
    target = Path(args.path).expanduser()
    setup_logging(Path.cwd() / LOG_FILE)
    organize_directory(target)


if __name__ == "__main__":
    main()
