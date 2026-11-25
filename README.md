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

- **Extension mapping:** sorts files into `Images/`, `Documents/`, `Videos/`, `Archives/`, `Code/` and `Others/`. Matching ignores case (`.JPG` = `.jpg`).
- **No overwrites:** if a file with the same name already exists, the new one is saved as `name_1.ext`, `name_2.ext`, and so on.
- **Error handling:** locked files or permission errors are logged and counted; the run keeps going instead of crashing.
- **Dry run:** `--dry-run` shows exactly what would move without touching anything.
- **Audit log:** every move, skip and failure is written to the console and to `file_automator.log`.
- **Safe by default:** hidden files, sub-folders and the tool's own log file are never moved.

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

# Write the audit log somewhere else
python main.py --path ~/Downloads --log-file ~/organizer.log
```

| Option | Default | Description |
|---|---|---|
| `--path` | `~/Downloads` | Folder to organize |
| `--dry-run` | off | Log planned moves without moving anything |
| `--log-file` | `file_automator.log` | Where to write the audit log |

To add or change categories, edit the `DIRECTORIES` dictionary at the top of `main.py`.

## Running Tests

```bash
pip install pytest
pytest -v
```

The tests use pytest's `tmp_path` fixture, so they run in throwaway folders and never touch your real files.
