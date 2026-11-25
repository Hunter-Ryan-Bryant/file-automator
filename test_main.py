from pathlib import Path

from main import get_category, organize_directory, unique_destination


def make_files(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_text(f"contents of {name}")


def test_get_category_is_case_insensitive():
    assert get_category(Path("photo.JPG")) == "Images"
    assert get_category(Path("notes.txt")) == "Documents"
    assert get_category(Path("mystery.xyz")) == "Others"
    assert get_category(Path("no_extension")) == "Others"


def test_files_are_sorted_into_category_folders(tmp_path):
    make_files(tmp_path, "photo.png", "resume.pdf", "script.py", "clip.mp4", "backup.zip", "weird.abc")

    summary = organize_directory(tmp_path)

    assert summary == {"moved": 6, "skipped": 0, "failed": 0}
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / "Documents" / "resume.pdf").exists()
    assert (tmp_path / "Code" / "script.py").exists()
    assert (tmp_path / "Videos" / "clip.mp4").exists()
    assert (tmp_path / "Archives" / "backup.zip").exists()
    assert (tmp_path / "Others" / "weird.abc").exists()


def test_name_collisions_get_numbered_suffixes(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    make_files(docs, "report.pdf", "report_1.pdf")
    make_files(tmp_path, "report.pdf")

    organize_directory(tmp_path)

    # Nothing is overwritten: the new file becomes report_2.pdf.
    assert (docs / "report_2.pdf").read_text() == "contents of report.pdf"
    assert len(list(docs.iterdir())) == 3


def test_unique_destination_returns_original_name_when_free(tmp_path):
    assert unique_destination(tmp_path, "a.txt") == tmp_path / "a.txt"


def test_dry_run_moves_nothing(tmp_path):
    make_files(tmp_path, "photo.png", "notes.txt")

    summary = organize_directory(tmp_path, dry_run=True)

    assert summary["moved"] == 2
    assert (tmp_path / "photo.png").exists()
    assert (tmp_path / "notes.txt").exists()
    assert not (tmp_path / "Images").exists()


def test_hidden_files_folders_and_skip_list_are_left_alone(tmp_path):
    make_files(tmp_path, ".hidden.txt", "audit.log")
    (tmp_path / "SomeFolder").mkdir()

    summary = organize_directory(tmp_path, skip=frozenset({(tmp_path / "audit.log").resolve()}))

    assert summary == {"moved": 0, "skipped": 3, "failed": 0}
    assert (tmp_path / ".hidden.txt").exists()
    assert (tmp_path / "audit.log").exists()


def test_missing_directory_is_handled(tmp_path):
    summary = organize_directory(tmp_path / "does-not-exist")
    assert summary == {"moved": 0, "skipped": 0, "failed": 0}


def test_failed_move_is_counted_not_raised(tmp_path, monkeypatch):
    make_files(tmp_path, "locked.txt")

    def refuse(*args, **kwargs):
        raise PermissionError("file is locked")

    monkeypatch.setattr("main.shutil.move", refuse)
    summary = organize_directory(tmp_path)

    assert summary["failed"] == 1
    assert (tmp_path / "locked.txt").exists()


def test_cli_expands_tilde_in_path(tmp_path, monkeypatch):
    """--path "~/folder" works even when the shell doesn't expand the ~ (e.g. when quoted)."""
    import sys
    import main as cli

    home = tmp_path / "home"
    target = home / "clutter"
    target.mkdir(parents=True)
    (target / "photo.png").write_text("img")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows
    monkeypatch.setattr(sys, "argv", ["main.py", "--path", "~/clutter", "--log-file", str(tmp_path / "run.log")])

    cli.main()

    assert (target / "Images" / "photo.png").exists()
