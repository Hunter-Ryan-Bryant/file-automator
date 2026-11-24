from main import organize_directory, unique_destination


def test_sorts_files_by_extension(tmp_path):
    (tmp_path / "photo.JPG").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "mystery.xyz").write_text("x")

    stats = organize_directory(tmp_path)

    assert (tmp_path / "Images" / "photo.JPG").exists()
    assert (tmp_path / "Documents" / "notes.txt").exists()
    assert (tmp_path / "Others" / "mystery.xyz").exists()
    assert stats["moved"] == 3


def test_repeated_collisions_never_overwrite(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "report.pdf").write_text("original")
    (docs / "report_1.pdf").write_text("first copy")
    (tmp_path / "report.pdf").write_text("new")

    organize_directory(tmp_path)

    assert (docs / "report.pdf").read_text() == "original"
    assert (docs / "report_1.pdf").read_text() == "first copy"
    assert (docs / "report_2.pdf").read_text() == "new"


def test_skips_folders_and_hidden_files(tmp_path):
    (tmp_path / "subfolder").mkdir()
    (tmp_path / ".hidden").write_text("x")

    stats = organize_directory(tmp_path)

    assert (tmp_path / "subfolder").is_dir()
    assert (tmp_path / ".hidden").exists()
    assert stats == {"moved": 0, "skipped": 2, "failed": 0}


def test_missing_directory_is_handled(tmp_path):
    stats = organize_directory(tmp_path / "does-not-exist")
    assert stats == {"moved": 0, "skipped": 0, "failed": 0}


def test_unique_destination_numbers_names(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert unique_destination(tmp_path, "a.txt").name == "a_1.txt"
    assert unique_destination(tmp_path, "b.txt").name == "b.txt"
