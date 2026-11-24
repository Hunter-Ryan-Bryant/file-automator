# File Automator

A Python command-line tool that cleans up a cluttered folder (your Downloads folder by default) by sorting each file into a category subfolder based on its extension. It never overwrites a file, keeps going if a single file can't be moved, and writes an audit log of everything it did.

---

## Key Features

* **Extension mapping:** Sorts files into `Images/`, `Documents/`, `Videos/`, `Archives/` and `Code/`. Anything unrecognized goes to `Others/`. Extension matching is case-insensitive (`.JPG` and `.jpg` both count as images).
* **Collision resolution:** If a file with the same name already exists in the destination, the incoming file is renamed `name_1.ext`, `name_2.ext`, and so on. Existing files are never overwritten.
* **Error handling:** A file that can't be moved (locked, permission denied) is logged and skipped, and the run continues with the rest.
* **Audit logging:** Every move, rename, skip and failure is printed to the console and appended to `file_automator.log` in the directory you run the tool from, followed by a summary count.
* **Safe defaults:** Subfolders and hidden files (names starting with `.`) are left alone.
* **CLI:** Pass `--path` to organize any folder.

---

## Tech Stack

* **Language:** Python 3.10+ (standard library only, no dependencies)
* **Modules:** `pathlib`, `shutil`, `logging`, `argparse`
* **Testing:** pytest

---

## Getting Started

### Prerequisites
* Python 3.10 or higher.

### Installation

```bash
git clone https://github.com/rm9v27j9jv-collab/file-automator.git
cd file-automator
```

### Usage

Organize your Downloads folder:

```bash
python main.py
```

Organize a different folder:

```bash
python main.py --path "C:\Users\you\Desktop\messy-folder"
```

### Running the tests

```bash
pip install pytest
python -m pytest
```

The tests run against temporary folders, so they never touch your real files.

---

## Customizing categories

Edit the `DIRECTORIES` dictionary at the top of `main.py` to add categories or extensions:

```python
DIRECTORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Music": {".mp3", ".wav", ".flac"},
    ...
}
```
