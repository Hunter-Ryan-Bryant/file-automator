from pathlib import Path
import shutil
import logging
import argparse

logger = logging.getLogger("file_automator")

DIRECTORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".csv", ".pptx"},
    "Videos": {".mp4", ".mov", ".mkv", ".avi"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {".py", ".js", ".html", ".css", ".json", ".cpp"},
}
OTHER_CATEGORY = "Others"


def get_category(file_path: Path) -> str:
    """Return the folder name a file belongs in, based on its extension."""
    file_ext = file_path.suffix.lower()
    for category, extensions in DIRECTORIES.items():
        if file_ext in extensions:
            return category
    return OTHER_CATEGORY


def unique_destination(dest_folder: Path, file_name: str) -> Path:
    """Return a path in dest_folder that doesn't exist yet.

    report.pdf -> report.pdf, then report_1.pdf, report_2.pdf, ...
    """
    candidate = dest_folder / file_name
    stem, suffix = Path(file_name).stem, Path(file_name).suffix
    counter = 1
    while candidate.exists():
        candidate = dest_folder / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def organize_directory(target_dir: Path, dry_run: bool = False, skip: frozenset = frozenset()) -> dict:
    """Sort the files directly inside target_dir into category folders.

    Returns a summary: {"moved": int, "skipped": int, "failed": int}.
    With dry_run=True nothing is moved; planned moves are only logged.
    """
    summary = {"moved": 0, "skipped": 0, "failed": 0}

    if not target_dir.exists() or not target_dir.is_dir():
        logger.error(f"Target directory does not exist or is invalid: {target_dir}")
        return summary

    logger.info(f"Starting organization for: {target_dir}" + (" (dry run)" if dry_run else ""))

    # Snapshot the listing first so files we create or move don't affect the loop.
    for item in sorted(target_dir.iterdir()):
        if item.is_dir() or item.name.startswith(".") or item.resolve() in skip:
            summary["skipped"] += 1
            continue

        category = get_category(item)
        dest_folder = target_dir / category

        try:
            dest_path = unique_destination(dest_folder, item.name)
            if dry_run:
                logger.info(f"[dry run] Would move: {item.name} -> {category}/{dest_path.name}")
            else:
                dest_folder.mkdir(exist_ok=True)
                shutil.move(str(item), str(dest_path))
                logger.info(f"Moved: {item.name} -> {category}/{dest_path.name}")
            summary["moved"] += 1
        except (PermissionError, OSError) as error:
            logger.warning(f"Could not move {item.name}: {error}")
            summary["failed"] += 1

    logger.info(
        f"Done. Moved: {summary['moved']}, skipped: {summary['skipped']}, failed: {summary['failed']}"
    )
    return summary


def setup_logging(log_file: Path | None) -> None:
    """Log to the console and, if given, to an audit log file."""
    handlers = [logging.StreamHandler()]
    if log_file is not None:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Automate organizing files in a directory")
    parser.add_argument(
        "--path",
        type=str,
        default=str(Path.home() / "Downloads"),
        help="Path to the directory you want to organize (defaults to Downloads)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be moved without moving anything",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="file_automator.log",
        help="Where to write the audit log (default: file_automator.log in the current folder)",
    )
    args = parser.parse_args()

    log_file = Path(args.log_file)
    setup_logging(log_file)
    # Never sort our own log file if it lives inside the target folder.
    organize_directory(Path(args.path), dry_run=args.dry_run, skip=frozenset({log_file.resolve()}))


if __name__ == "__main__":
    main()
