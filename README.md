# File Automator

[![tests](https://github.com/Hunter-Ryan-Bryant/file-automator/actions/workflows/tests.yml/badge.svg)](https://github.com/Hunter-Ryan-Bryant/file-automator/actions/workflows/tests.yml)

A Python command-line tool that tidies a messy folder (your Downloads folder by default) by sorting files into category folders based on their extension.

```
Downloads/                    Downloads/
├── photo.png                 ├── Images/photo.png
├── resume.pdf       ──►      ├── Documents/resume.pdf
├── script.py                 ├── Code/script.py
└── mystery.xyz               └── Others/mystery.xyz
```

## Features

- **Extension mapping:** sorts files into `Images/`, `Documents/`, `Videos/`, `Audio/`, `Archives/`, `Code/`, `Installers/` and `Others/`. Matching ignores case (`.JPG` = `.jpg`).
- **No overwrites:** if a file with the same name already exists, the new one is saved as `name_1.ext`, `name_2.ext`, and so on.
- **Error handling:** locked files or permission errors are logged and counted; the run keeps going instead of crashing.
- **Dry run:** `--dry-run` shows exactly what would move without touching anything.
- **Recursive mode:** `--recursive` also gathers files from sub-folders into the top-level category folders, then removes sub-folders left empty. Existing category folders, hidden folders (like `.git`) and symlinked folders are never searched.
- **Watch mode:** `--watch` keeps running and sorts new files as they arrive, checking every few seconds (`--interval`). A file is only moved once it has stopped changing, so copies still in progress are left alone. Idle checks log nothing.
- **Undo:** `--undo` moves the files from the most recent run back where they were. Run it again to step back further. It never overwrites a file, and it removes category folders that end up empty.
- **Audit log:** every move, skip and failure is written to the console and to `file_automator.log`.
- **Safe by default:** hidden files, sub-folders, the tool's own log file and in-progress downloads (`.crdownload`, `.part`, `.tmp`, ...) are never moved.
- **Script-friendly exit code:** exits with `1` if the folder doesn't exist or any file failed to move, `0` otherwise.

## Tech Stack

- Python 3.10+ (standard library only: `pathlib`, `shutil`, `logging`, `argparse`)
- `pytest` for tests, run automatically by GitHub Actions on every push

## Getting Started

```bash
git clone https://github.com/Hunter-Ryan-Bryant/file-automator.git
cd file-automator
```

No dependencies are needed to run it.

## Usage

```bash
# Preview what would happen to your Downloads folder
python main.py --dry-run

# Organize a specific folder
python main.py --path "C:/Users/me/Desktop/clutter"

# Also pull files out of sub-folders (preview first: this flattens folders)
python main.py --recursive --dry-run
python main.py --recursive

# Keep running and sort new files as they arrive (Ctrl+C to stop)
python main.py --watch
python main.py --watch --interval 10

# Undo the last run (add --dry-run to preview first)
python main.py --undo

# Write the audit log somewhere else
python main.py --path ~/Downloads --log-file ~/organizer.log
```

| Option | Default | Description |
|---|---|---|
| `--path` | `~/Downloads` | Folder to organize |
| `--dry-run` | off | Log planned moves without moving anything |
| `--recursive` | off | Also gather files from sub-folders; empty sub-folders are removed |
| `--watch` | off | Keep running and organize new files as they appear |
| `--interval` | `5` | Seconds between checks in watch mode |
| `--undo` | off | Reverse the most recent run (combine with `--dry-run` to preview) |
| `--log-file` | `file_automator.log` | Where to write the audit log |
| `--config` | none | JSON file with custom categories (see below) |

Each run records its moves in a hidden `.file_automator_history.json` file inside the organized folder. That file is what `--undo` reads, so don't delete it if you might want to undo. In watch mode, each check that moves files counts as its own run, so `--undo` reverses the most recent batch.

To start watching automatically when you log in, add `python main.py --watch` as a Windows Task Scheduler task with an "At log on" trigger, or as an `@reboot` cron job on macOS/Linux.

## Custom Categories

To add your own folders or change where an extension goes, write a JSON file and pass it with `--config`. You don't need to edit the code. Start from [`categories.example.json`](categories.example.json):

```json
{
  "replace_defaults": false,
  "categories": {
    "Ebooks": [".epub", ".mobi"],
    "Photos-RAW": [".cr2", ".nef", ".arw"],
    "Images": [".avif"]
  }
}
```

```bash
python main.py --config categories.example.json --dry-run
```

- **Merged with the defaults:** every extension you list goes to that folder and is taken out of whichever built-in folder had it. The example above adds `Ebooks/` and `Photos-RAW/`, adds `.avif` to `Images/`, and keeps everything else as is.
- **`"replace_defaults": true`:** uses only your categories. Anything not listed goes to `Others/`.
- **Extensions are flexible:** `"EPUB"`, `".epub"` and `"epub"` all mean the same thing.
- **Folder names** must be plain names: no `/`, `\` or `..`, and they can't start with `.`.
- A config file inside the folder being organized is never moved.
- A typo in the file gives a clear error with the line and column, and nothing gets moved.

## Running Tests

```bash
pip install pytest
pytest -v
```

The tests use pytest's `tmp_path` fixture, so they run in throwaway folders and never touch your real files.
