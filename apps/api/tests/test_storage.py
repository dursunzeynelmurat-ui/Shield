"""Tests for storage path traversal protection."""
import pytest
from pathlib import Path
import tempfile

from app.uploads.storage import LocalStorage


def _storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(str(tmp_path))


def test_get_local_path_valid(tmp_path):
    s = _storage(tmp_path)
    (tmp_path / "abc123.jpg").write_bytes(b"x")
    path = s.get_local_path("local://abc123.jpg")
    assert path.name == "abc123.jpg"
    assert str(path).startswith(str(tmp_path))


def test_path_traversal_dots_rejected(tmp_path):
    s = _storage(tmp_path)
    with pytest.raises(ValueError):
        s.get_local_path("local://../etc/passwd")


def test_path_traversal_slash_rejected(tmp_path):
    s = _storage(tmp_path)
    with pytest.raises(ValueError):
        s.get_local_path("local://subdir/malicious")


def test_path_traversal_backslash_rejected(tmp_path):
    s = _storage(tmp_path)
    with pytest.raises(ValueError):
        s.get_local_path("local://subdir\\malicious")


def test_leading_dot_rejected(tmp_path):
    s = _storage(tmp_path)
    with pytest.raises(ValueError):
        s.get_local_path("local://.hidden")
