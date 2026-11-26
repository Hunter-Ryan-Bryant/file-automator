from datetime import datetime
from pathlib import Path
import argparse
import json
import logging
import shutil
import time

logger = logging.getLogger("file_automator")

# Hidden (starts with ".") so the organizer never moves it.
HISTORY_FILENAME = ".file_automator_history.json"

DIRECTORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".heic", ".bmp"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".csv", ".pptx"},
    "Videos": {".mp4", ".mov", ".mkv", ".avi"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".cpp"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg"},
}
OTHER_CATEGORY = "Others"

# Downloads that are still in progress. Moving these can break the download.
PARTIAL_DOWNLOAD_EXTS = {".crdownload", ".part", ".partial", ".download", ".tmp"}


def should_skip(item: Path, skip: frozenset) -> bool:
    """Folders, hidden files, in-progress downloads and explicitly skipped paths stay put."""
    return (
        item.is_dir()
        or item.name.startswith(".")
        or item.suffix.lower() in PARTIAL_DOWNLOAD_EXTS
        or item.resolve() in skip
    )


class ConfigError(ValueError):
    """The --config file is missing, isn't valid JSON, or has the wrong shape."""


def _normalize_extension(raw: str, category: str) -> str:
    ext = raw.strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    if ext == ".":
        raise ConfigError(f'Category "{category}" has an empty extension')
    return ext


def _validate_category_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ConfigError("Category names can't be empty")
    if cleaned.startswith("."):
        raise ConfigError(f'Category "{name}" can\'t start with "." (hidden folders are skipped)')
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise ConfigError(f'Category "{name}" must be a plain folder name (no "/", "\\" or "..")')
    return cleaned


def load_categories(config_path: Path) -> dict[str, set[str]]:
    """Read a JSON config and return the categories to use.

    Format:
        {"replace_defaults": false, "categories": {"Ebooks": [".epub", ".mobi"]}}

    By default the config is merged into DIRECTORIES: every extension it lists
    goes to that folder and is taken out of any other folder. With
    "replace_defaults": true, only the config's categories are used.
    Raises ConfigError with a readable message if anything is wrong.
    """
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {config_path}") from None
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"Config file {config_path} isn't valid JSON (line {error.lineno}, column {error.colno}): {error.msg}"
        ) from None
    except OSError as error:
        raise ConfigError(f"Could not read config file {config_path}: {error}") from None

    if not isinstance(data, dict):
        raise ConfigError('Config must be a JSON object like {"categories": {...}}')

    replace = data.get("replace_defaults", False)
    if not isinstance(replace, bool):
        raise ConfigError('"replace_defaults" must be true or false')

    user_categories = data.get("categories", {})
    if not isinstance(user_categories, dict):
        raise ConfigError('"categories" must be an object like {"Ebooks": [".epub"]}')

    categories = {} if replace else {name: set(exts) for name, exts in DIRECTORIES.items()}
    existing_names = {name.lower(): name for name in categories}

    for raw_name, raw_exts in user_categories.items():
        name = _validate_category_name(raw_name)
        name = existing_names.get(name.lower(), name)  # "images" -> "Images"
        if not isinstance(raw_exts, list) or not all(isinstance(e, str) for e in raw_exts):
            raise ConfigError(f'Category "{name}" must be a list of extensions like [".epub", ".mobi"]')

        exts = {_normalize_extension(e, name) for e in raw_exts}
        for other in categories.values():
            other -= exts  # an extension belongs to exactly one folder
        categories.setdefault(name, set()).update(exts)
        existing_names[name.lower()] = name

    return {name: exts for name, exts in categories.items() if exts}


def get_category(file_path: Path, categories: dict | None = None) -> str:
    """Return the folder name a file belongs in, based on its extension."""
    file_ext = file_path.suffix.lower()
    for category, extensions in (DIRECTORIES if categories is None else categories).items():
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


def load_history(target_dir: Path) -> list[dict]:
    """Return the list of recorded runs for target_dir, oldest first."""
    history_file = target_dir / HISTORY_FILENAME
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError, AttributeError) as error:
        logger.warning(f"Could not read undo history {history_file.name}: {error}")
        return []


def save_history(target_dir: Path, runs: list[dict]) -> None:
    """Write the run history, or delete the file when there's nothing left to undo."""
    history_file = target_dir / HISTORY_FILENAME
    try:
        if runs:
            history_file.write_text(json.dumps({"runs": runs}, indent=2), encoding="utf-8")
        elif history_file.exists():
            history_file.unlink()
    except OSError as error:
        logger.warning(f"Could not update undo history {history_file.name}: {error}")


def is_settled(item: Path, min_age: float) -> bool:
    """True if the file hasn't been modified in the last min_age seconds."""
    if min_age <= 0:
        return True
    try:
        return time.time() - item.stat().st_mtime >= min_age
    except OSError:
        return False


def collect_files(
    target_dir: Path,
    recursive: bool,
    skip: frozenset,
    summary: dict,
    min_age: float = 0,
    categories: dict | None = None,
) -> list[Path]:
    """List the files to organize, counting anything left alone in summary["skipped"].

    With recursive=True, sub-folders are searched too, except hidden folders,
    symlinked folders and the top-level category folders (already sorted).
    Files modified less than min_age seconds ago are left for a later run
    (they may still be being written) and are not counted as skipped.
    """
    active = DIRECTORIES if categories is None else categories
    category_names = {name.lower() for name in active} | {OTHER_CATEGORY.lower()}
    files = []

    def visit(folder: Path, is_top: bool) -> None:
        try:
            items = sorted(folder.iterdir())
        except OSError as error:
            logger.warning(f"Could not read folder {folder}: {error}")
            summary["skipped"] += 1
            return
        for item in items:
            descend = (
                recursive
                and item.is_dir()
                and not item.is_symlink()
                and not item.name.startswith(".")
                and not (is_top and item.name.lower() in category_names)
            )
            if descend:
                visit(item, is_top=False)
            elif should_skip(item, skip):
                summary["skipped"] += 1
            elif is_settled(item, min_age):
                files.append(item)

    visit(target_dir, is_top=True)
    return files


def remove_emptied_folders(target_dir: Path, moved_files: list[Path]) -> None:
    """Delete sub-folders that are empty now because we moved files out of them."""
    folders = set()
    for file in moved_files:
        parent = file.parent
        while parent != target_dir and target_dir in parent.parents:
            folders.add(parent)
            parent = parent.parent
    # Deepest first, so a parent can be removed once its children are gone.
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        try:
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
                logger.info(f"Removed empty folder: {folder.relative_to(target_dir).as_posix()}/")
        except OSError:
            pass


def organize_directory(
    target_dir: Path,
    dry_run: bool = False,
    skip: frozenset = frozenset(),
    recursive: bool = False,
    min_age: float = 0,
    quiet: bool = False,
    categories: dict | None = None,
) -> dict:
    """Sort the files inside target_dir into category folders.

    categories maps folder names to extensions (see load_categories);
    None means the built-in DIRECTORIES.

    With recursive=True, files in sub-folders are gathered into the top-level
    category folders too, and sub-folders left empty are removed.
    min_age leaves recently modified files for later; quiet=True logs only
    when something actually moved or failed (used by watch mode).
    Returns a summary: {"moved": int, "skipped": int, "failed": int}.
    With dry_run=True nothing is moved; planned moves are only logged.
    Real moves are recorded in HISTORY_FILENAME so they can be undone.
    """
    summary = {"moved": 0, "skipped": 0, "failed": 0}
    moves = []  # [{"src": "trip/photo.png", "dest": "Images/photo.png"}, ...], relative to target_dir
    moved_files = []

    if not target_dir.exists() or not target_dir.is_dir():
        logger.error(f"Target directory does not exist or is invalid: {target_dir}")
        return summary

    if not quiet:
        mode = " (recursive)" if recursive else ""
        logger.info(f"Starting organization for: {target_dir}{mode}" + (" (dry run)" if dry_run else ""))

    try:
        # Collect everything first so files we create or move don't affect the loop.
        for item in collect_files(target_dir, recursive, skip, summary, min_age=min_age, categories=categories):
            category = get_category(item, categories)
            dest_folder = target_dir / category
            rel = item.relative_to(target_dir).as_posix()

            try:
                dest_path = unique_destination(dest_folder, item.name)
                if dry_run:
                    logger.info(f"[dry run] Would move: {rel} -> {category}/{dest_path.name}")
                else:
                    dest_folder.mkdir(exist_ok=True)
                    shutil.move(str(item), str(dest_path))
                    logger.info(f"Moved: {rel} -> {category}/{dest_path.name}")
                    moves.append({"src": rel, "dest": f"{category}/{dest_path.name}"})
                    moved_files.append(item)
                summary["moved"] += 1
            except (PermissionError, OSError) as error:
                logger.warning(f"Could not move {rel}: {error}")
                summary["failed"] += 1
    finally:
        # Runs even on Ctrl+C, so every completed move can still be undone.
        if moved_files:
            remove_emptied_folders(target_dir, moved_files)
        if moves:
            runs = load_history(target_dir)
            runs.append({"timestamp": datetime.now().isoformat(timespec="seconds"), "moves": moves})
            save_history(target_dir, runs)

    if not quiet or summary["moved"] or summary["failed"]:
        logger.info(
            f"Done. Moved: {summary['moved']}, skipped: {summary['skipped']}, failed: {summary['failed']}"
        )
    return summary


def watch_directory(
    target_dir: Path,
    interval: float = 5,
    skip: frozenset = frozenset(),
    recursive: bool = False,
    sleep=None,
    max_cycles: int | None = None,
    categories: dict | None = None,
) -> dict:
    """Organize target_dir now, then again every `interval` seconds until Ctrl+C.

    A file is only moved once it hasn't changed for `interval` seconds, so
    files that are still being copied or written are left for a later pass.
    Returns totals: {"moved": int, "failed": int, "stopped_early": bool}.
    stopped_early is True if the folder disappeared while watching.
    `sleep` and `max_cycles` exist so tests can run the loop without waiting.
    """
    sleep = sleep or time.sleep
    totals = {"moved": 0, "failed": 0, "stopped_early": False}
    logger.info(
        f"Watching {target_dir} every {interval:g}s"
        + (" (recursive)" if recursive else "")
        + ". Press Ctrl+C to stop."
    )

    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            if not target_dir.is_dir():
                logger.error(f"Stopped watching: folder is gone or invalid: {target_dir}")
                totals["stopped_early"] = True
                break
            summary = organize_directory(
                target_dir,
                skip=skip,
                recursive=recursive,
                min_age=interval,
                quiet=True,
                categories=categories,
            )
            totals["moved"] += summary["moved"]
            totals["failed"] += summary["failed"]
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                sleep(interval)
    except KeyboardInterrupt:
        pass

    logger.info(f"Stopped watching. Moved: {totals['moved']}, failed: {totals['failed']}")
    return totals


def undo_last_run(target_dir: Path, dry_run: bool = False) -> dict:
    """Move the files from the most recent run back to where they were.

    Returns a summary: {"restored": int, "skipped": int, "failed": int}.
    Files are never overwritten: if the original name is taken again, the file
    stays put and the move is kept in the history so it can be retried.
    """
    summary = {"restored": 0, "skipped": 0, "failed": 0}

    if not target_dir.is_dir():
        logger.error(f"Target directory does not exist or is invalid: {target_dir}")
        return summary

    runs = load_history(target_dir)
    if not runs:
        logger.info(f"Nothing to undo in: {target_dir}")
        return summary

    last_run = runs[-1]
    logger.info(
        f"Undoing run from {last_run.get('timestamp', 'unknown time')} in: {target_dir}"
        + (" (dry run)" if dry_run else "")
    )

    remaining = []  # moves we couldn't undo, kept so the user can retry
    for move in reversed(last_run["moves"]):
        current = target_dir / move["dest"]
        original = target_dir / move["src"]

        if not current.exists():
            logger.warning(f"Skipped {move['dest']}: file is no longer there")
            summary["skipped"] += 1
            continue
        if original.exists():
            logger.warning(f"Skipped {move['dest']}: {move['src']} already exists")
            summary["skipped"] += 1
            remaining.append(move)
            continue

        if dry_run:
            logger.info(f"[dry run] Would restore: {move['dest']} -> {move['src']}")
            summary["restored"] += 1
            continue

        try:
            # Recreate the sub-folder if a recursive run removed it.
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current), str(original))
            logger.info(f"Restored: {move['dest']} -> {move['src']}")
            summary["restored"] += 1
        except (PermissionError, OSError) as error:
            logger.warning(f"Could not restore {move['dest']}: {error}")
            summary["failed"] += 1
            remaining.append(move)

    if not dry_run:
        # Remove category folders this run created that are now empty.
        for folder in {(target_dir / m["dest"]).parent for m in last_run["moves"]}:
            try:
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
            except OSError:
                pass

        if remaining:
            last_run["moves"] = list(reversed(remaining))
        else:
            runs.pop()
        save_history(target_dir, runs)

    logger.info(
        f"Undo done. Restored: {summary['restored']}, skipped: {summary['skipped']}, failed: {summary['failed']}"
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


def main() -> int:
    """Run the CLI. Returns 1 if the folder is invalid or any move failed, else 0."""
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
        "--recursive",
        action="store_true",
        help="Also gather files from sub-folders into the top-level category folders",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Move files from the most recent run back to where they were",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep running and organize new files as they appear (Ctrl+C to stop)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5,
        help="Seconds between checks in --watch mode (default: 5)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="file_automator.log",
        help="Where to write the audit log (default: file_automator.log in the current folder)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="JSON file with custom categories (see categories.example.json)",
    )
    args = parser.parse_args()

    if args.watch and args.undo:
        parser.error("--watch can't be combined with --undo")
    if args.watch and args.dry_run:
        parser.error("--watch can't be combined with --dry-run")
    if args.interval <= 0:
        parser.error("--interval must be greater than 0")

    log_file = Path(args.log_file)
    setup_logging(log_file)
    target_dir = Path(args.path).expanduser()
    skip = {log_file.resolve()}  # never sort our own log file

    categories = None
    if args.config and not args.undo:  # undo reads the history, not categories
        config_path = Path(args.config).expanduser()
        try:
            categories = load_categories(config_path)
        except ConfigError as error:
            logger.error(error)
            return 1
        logger.info(f"Using categories from {config_path}")
        skip.add(config_path.resolve())  # don't sort the config file itself
    skip = frozenset(skip)

    if args.watch:
        if not target_dir.is_dir():
            logger.error(f"Target directory does not exist or is invalid: {target_dir}")
            return 1
        totals = watch_directory(
            target_dir,
            interval=args.interval,
            skip=skip,
            recursive=args.recursive,
            categories=categories,
        )
        return 1 if totals["failed"] or totals["stopped_early"] else 0

    if args.undo:
        summary = undo_last_run(target_dir, dry_run=args.dry_run)
    else:
        summary = organize_directory(
            target_dir,
            dry_run=args.dry_run,
            skip=skip,
            recursive=args.recursive,
            categories=categories,
        )

    if not target_dir.is_dir() or summary["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
