from pathlib import Path

from main import HISTORY_FILENAME, get_category, organize_directory, undo_last_run, unique_destination


def make_files(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_text(f"contents of {name}")


def test_get_category_is_case_insensitive():
    assert get_category(Path("photo.JPG")) == "Images"
    assert get_category(Path("notes.txt")) == "Documents"
    assert get_category(Path("mystery.xyz")) == "Others"
    assert get_category(Path("no_extension")) == "Others"
    assert get_category(Path("song.MP3")) == "Audio"
    assert get_category(Path("setup.exe")) == "Installers"


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


def test_in_progress_downloads_are_left_alone(tmp_path):
    make_files(tmp_path, "movie.mkv.crdownload", "game.zip.part", "installer.tmp")

    summary = organize_directory(tmp_path)

    assert summary == {"moved": 0, "skipped": 3, "failed": 0}
    assert (tmp_path / "movie.mkv.crdownload").exists()
    assert (tmp_path / "game.zip.part").exists()
    assert (tmp_path / "installer.tmp").exists()


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

    assert cli.main() == 0

    assert (target / "Images" / "photo.png").exists()


def test_cli_exit_code_is_1_for_missing_folder_or_failed_move(tmp_path, monkeypatch):
    import sys
    import main as cli

    log = str(tmp_path / "run.log")
    monkeypatch.setattr(sys, "argv", ["main.py", "--path", str(tmp_path / "missing"), "--log-file", log])
    assert cli.main() == 1

    target = tmp_path / "clutter"
    target.mkdir()
    (target / "locked.txt").write_text("x")

    def refuse(*args, **kwargs):
        raise PermissionError("file is locked")

    monkeypatch.setattr("main.shutil.move", refuse)
    monkeypatch.setattr(sys, "argv", ["main.py", "--path", str(target), "--log-file", log])
    assert cli.main() == 1


# ---------- undo ----------

def test_undo_restores_files_and_removes_empty_folders(tmp_path):
    make_files(tmp_path, "photo.png", "resume.pdf")
    organize_directory(tmp_path)

    summary = undo_last_run(tmp_path)

    assert summary == {"restored": 2, "skipped": 0, "failed": 0}
    assert (tmp_path / "photo.png").read_text() == "contents of photo.png"
    assert (tmp_path / "resume.pdf").exists()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / "Documents").exists()
    assert not (tmp_path / HISTORY_FILENAME).exists()


def test_undo_restores_renamed_collision_to_original_name(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    make_files(docs, "report.pdf")
    make_files(tmp_path, "report.pdf")
    organize_directory(tmp_path)  # new file becomes Documents/report_1.pdf

    undo_last_run(tmp_path)

    assert (tmp_path / "report.pdf").exists()
    assert not (docs / "report_1.pdf").exists()
    assert (docs / "report.pdf").exists()  # the pre-existing file is untouched


def test_undo_steps_back_one_run_at_a_time(tmp_path):
    make_files(tmp_path, "first.png")
    organize_directory(tmp_path)
    make_files(tmp_path, "second.png")
    organize_directory(tmp_path)

    undo_last_run(tmp_path)
    assert (tmp_path / "second.png").exists()
    assert (tmp_path / "Images" / "first.png").exists()

    undo_last_run(tmp_path)
    assert (tmp_path / "first.png").exists()
    assert not (tmp_path / "Images").exists()


def test_undo_with_nothing_to_undo(tmp_path):
    assert undo_last_run(tmp_path) == {"restored": 0, "skipped": 0, "failed": 0}


def test_undo_never_overwrites_and_keeps_entry_for_retry(tmp_path):
    make_files(tmp_path, "photo.png")
    organize_directory(tmp_path)
    (tmp_path / "photo.png").write_text("a new file with the same name")

    summary = undo_last_run(tmp_path)

    assert summary == {"restored": 0, "skipped": 1, "failed": 0}
    assert (tmp_path / "photo.png").read_text() == "a new file with the same name"
    assert (tmp_path / "Images" / "photo.png").read_text() == "contents of photo.png"
    assert (tmp_path / HISTORY_FILENAME).exists()


def test_undo_skips_files_moved_away_since(tmp_path):
    make_files(tmp_path, "photo.png", "notes.txt")
    organize_directory(tmp_path)
    (tmp_path / "Images" / "photo.png").unlink()

    summary = undo_last_run(tmp_path)

    assert summary == {"restored": 1, "skipped": 1, "failed": 0}
    assert (tmp_path / "notes.txt").exists()
    assert not (tmp_path / HISTORY_FILENAME).exists()


def test_undo_dry_run_changes_nothing(tmp_path):
    make_files(tmp_path, "photo.png")
    organize_directory(tmp_path)

    summary = undo_last_run(tmp_path, dry_run=True)

    assert summary["restored"] == 1
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / HISTORY_FILENAME).exists()


def test_dry_run_does_not_record_history(tmp_path):
    make_files(tmp_path, "photo.png")
    organize_directory(tmp_path, dry_run=True)
    assert not (tmp_path / HISTORY_FILENAME).exists()


def test_cli_undo(tmp_path, monkeypatch):
    import sys
    import main as cli

    make_files(tmp_path, "photo.png")
    log = str(tmp_path.parent / f"{tmp_path.name}.log")
    monkeypatch.setattr(sys, "argv", ["main.py", "--path", str(tmp_path), "--log-file", log])
    assert cli.main() == 0
    assert (tmp_path / "Images" / "photo.png").exists()

    monkeypatch.setattr(sys, "argv", ["main.py", "--path", str(tmp_path), "--log-file", log, "--undo"])
    assert cli.main() == 0
    assert (tmp_path / "photo.png").exists()


# ---------- recursive ----------

def test_non_recursive_leaves_subfolders_alone(tmp_path):
    (tmp_path / "trip").mkdir()
    make_files(tmp_path / "trip", "photo.png")

    organize_directory(tmp_path)

    assert (tmp_path / "trip" / "photo.png").exists()


def test_recursive_gathers_into_top_level_and_removes_emptied_folders(tmp_path):
    (tmp_path / "trip" / "day1").mkdir(parents=True)
    make_files(tmp_path / "trip", "notes.txt")
    make_files(tmp_path / "trip" / "day1", "photo.png")
    make_files(tmp_path, "song.mp3")

    summary = organize_directory(tmp_path, recursive=True)

    assert summary == {"moved": 3, "skipped": 0, "failed": 0}
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / "Documents" / "notes.txt").exists()
    assert (tmp_path / "Audio" / "song.mp3").exists()
    assert not (tmp_path / "trip").exists()


def test_recursive_keeps_folders_that_still_have_content_or_were_already_empty(tmp_path):
    (tmp_path / "project" / ".git").mkdir(parents=True)
    make_files(tmp_path / "project", "main.py")
    (tmp_path / "already-empty").mkdir()

    organize_directory(tmp_path, recursive=True)

    assert (tmp_path / "Code" / "main.py").exists()
    assert (tmp_path / "project" / ".git").is_dir()  # hidden folder is left alone
    assert (tmp_path / "already-empty").is_dir()


def test_recursive_does_not_reorganize_existing_category_folders(tmp_path):
    (tmp_path / "Images").mkdir()
    make_files(tmp_path / "Images", "old.txt")  # misfiled by the user, but already "sorted"

    summary = organize_directory(tmp_path, recursive=True)

    assert summary["moved"] == 0
    assert (tmp_path / "Images" / "old.txt").exists()


def test_recursive_name_collisions_across_folders(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    make_files(tmp_path / "a", "photo.png")
    make_files(tmp_path / "b", "photo.png")

    organize_directory(tmp_path, recursive=True)

    assert sorted(p.name for p in (tmp_path / "Images").iterdir()) == ["photo.png", "photo_1.png"]


def test_recursive_dry_run_changes_nothing(tmp_path):
    (tmp_path / "trip").mkdir()
    make_files(tmp_path / "trip", "photo.png")

    summary = organize_directory(tmp_path, recursive=True, dry_run=True)

    assert summary["moved"] == 1
    assert (tmp_path / "trip" / "photo.png").exists()
    assert not (tmp_path / "Images").exists()


def test_undo_after_recursive_recreates_subfolders(tmp_path):
    (tmp_path / "trip" / "day1").mkdir(parents=True)
    make_files(tmp_path / "trip" / "day1", "photo.png")
    make_files(tmp_path / "trip", "notes.txt")
    organize_directory(tmp_path, recursive=True)
    assert not (tmp_path / "trip").exists()

    summary = undo_last_run(tmp_path)

    assert summary == {"restored": 2, "skipped": 0, "failed": 0}
    assert (tmp_path / "trip" / "day1" / "photo.png").read_text() == "contents of photo.png"
    assert (tmp_path / "trip" / "notes.txt").exists()
    assert not (tmp_path / "Images").exists()


def test_cli_recursive_flag(tmp_path, monkeypatch):
    import sys
    import main as cli

    (tmp_path / "trip").mkdir()
    make_files(tmp_path / "trip", "photo.png")
    log = str(tmp_path.parent / f"{tmp_path.name}.log")
    monkeypatch.setattr(sys, "argv", ["main.py", "--path", str(tmp_path), "--log-file", log, "--recursive"])

    assert cli.main() == 0
    assert (tmp_path / "Images" / "photo.png").exists()
