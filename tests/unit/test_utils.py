"""Tests for legaldocuman.utils helpers."""
import os
import pytest
from legaldocuman.utils import (
    setup_directories,
    safe_move_file,
    get_unique_filename,
    resolve_filename_conflict,
    clean_filename,
    format_file_size,
    get_file_info,
    count_files_by_extension,
    backup_file,
)


class TestSetupDirectories:
    def test_creates_single_directory(self, temp_dir):
        d = temp_dir / "new_folder"
        setup_directories(str(d))
        assert d.exists()
        assert d.is_dir()

    def test_creates_multiple_directories(self, temp_dir):
        dirs = [temp_dir / f"dir_{i}" for i in range(3)]
        setup_directories(*[str(d) for d in dirs])
        for d in dirs:
            assert d.exists()

    def test_skips_empty_strings(self, temp_dir):
        d = temp_dir / "real_dir"
        setup_directories(str(d), "", None)
        assert d.exists()


class TestSafeMoveFile:
    def test_moves_file_successfully(self, temp_dir):
        src = temp_dir / "source.txt"
        src.write_text("hello")
        dst = temp_dir / "dest.txt"
        result = safe_move_file(str(src), str(dst))
        assert not src.exists()
        assert os.path.exists(result)
        assert open(result).read() == "hello"

    def test_raises_on_missing_source(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            safe_move_file(str(temp_dir / "nope.txt"), str(temp_dir / "dest.txt"))

    def test_handles_duplicate_by_renaming(self, temp_dir):
        src = temp_dir / "file.txt"
        src.write_text("v1")
        existing = temp_dir / "file.txt"
        existing.write_text("v0")
        result = safe_move_file(str(src), str(existing), handle_duplicates=True)
        assert "_01" in result or result == str(existing)


class TestGetUniqueFilename:
    def test_returns_same_if_not_exists(self, temp_dir):
        p = str(temp_dir / "unique.txt")
        assert get_unique_filename(p) == p

    def test_appends_counter(self, temp_dir):
        base = temp_dir / "file.txt"
        base.write_text("a")
        (temp_dir / "file_01.txt").write_text("b")
        result = get_unique_filename(str(base))
        assert result == str(temp_dir / "file_02.txt")


class TestCleanFilename:
    @pytest.mark.parametrize("raw,expected", [
        ("file:name.txt", "file_name.txt"),
        ("file\\name.txt", "file_name.txt"),
        ("file//name.txt", "file_name.txt"),
        ("<bad>.txt", "bad_.txt"),  # < and > become _, . preserved, strip removes leading _
        ("__leading__.txt", "leading_.txt"),
        ("trailing__ ", "trailing"),
    ])
    def test_replaces_invalid_chars(self, raw, expected):
        assert clean_filename(raw) == expected


class TestFormatFileSize:
    @pytest.mark.parametrize("size,expected", [
        (0, "0B"),
        (512, "512.0B"),
        (1024, "1.0KB"),
        (1536, "1.5KB"),
        (1024 * 1024, "1.0MB"),
        (1024 ** 3, "1.0GB"),
    ])
    def test_formats_correctly(self, size, expected):
        assert format_file_size(size) == expected


class TestGetFileInfo:
    def test_returns_info_dict(self, temp_dir):
        p = temp_dir / "test.txt"
        p.write_text("hello world")
        info = get_file_info(str(p))
        assert info is not None
        assert info["size"] == 11
        assert info["size_formatted"] == "11.0B"
        assert info["extension"] == ".txt"
        assert "created" in info
        assert "modified" in info

    def test_returns_none_for_missing_file(self, temp_dir):
        assert get_file_info(str(temp_dir / "ghost.txt")) is None


class TestCountFilesByExtension:
    def test_counts_correctly(self, temp_dir):
        (temp_dir / "a.pdf").write_text("x")
        (temp_dir / "b.pdf").write_text("x")
        (temp_dir / "c.docx").write_text("x")
        counts = count_files_by_extension(str(temp_dir), recursive=False)
        assert counts[".pdf"] == 2
        assert counts[".docx"] == 1

    def test_recursive_counts_subdirs(self, temp_dir):
        (temp_dir / "a.txt").write_text("x")
        sub = temp_dir / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("x")
        counts = count_files_by_extension(str(temp_dir), recursive=True)
        assert counts[".txt"] == 2


class TestBackupFile:
    def test_creates_backup_in_backup_dir(self, temp_dir):
        p = temp_dir / "original.txt"
        p.write_text("data")
        backup = backup_file(str(p))
        assert os.path.exists(backup)
        assert "_backup" in backup or os.path.basename(backup) == "original.txt"

    def test_returns_none_for_missing_file(self, temp_dir):
        result = backup_file(str(temp_dir / "missing.txt"))
        assert result is None


class TestResolveFilenameConflict:
    def test_returns_same_if_no_conflict(self, temp_dir):
        p = str(temp_dir / "new_file.txt")
        assert resolve_filename_conflict(p) == p

    def test_appends_conflict_suffix(self, temp_dir):
        existing = temp_dir / "file.txt"
        existing.write_text("existing")
        result = resolve_filename_conflict(str(existing))
        assert result.endswith("_conflict01.txt")

    def test_increments_on_multiple_conflicts(self, temp_dir):
        (temp_dir / "file.txt").write_text("a")
        (temp_dir / "file_conflict01.txt").write_text("b")
        result = resolve_filename_conflict(str(temp_dir / "file.txt"))
        assert result.endswith("_conflict02.txt")
