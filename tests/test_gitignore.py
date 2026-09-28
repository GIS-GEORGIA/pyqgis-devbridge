"""gitignore.ensure_ignored: keep devbridge's generated folders out of git,
only where a git checkout already is one, and never touch other lines."""
from __future__ import annotations

from pathlib import Path

from devbridge import gitignore


def test_does_nothing_when_not_a_git_checkout(tmp_path: Path):
    assert gitignore.ensure_ignored(tmp_path) is None
    assert not (tmp_path / ".gitignore").exists()


def test_creates_gitignore_when_git_dir_present(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    path = gitignore.ensure_ignored(tmp_path)
    assert path == tmp_path / ".gitignore"
    text = path.read_text(encoding="utf-8")
    assert ".venv/" in text and "__pycache__/" in text and ".pycharm-debug/" in text


def test_uses_the_actual_venv_name(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    path = gitignore.ensure_ignored(tmp_path, venv_name="env")
    assert "env/" in path.read_text(encoding="utf-8")
    assert ".venv/" not in path.read_text(encoding="utf-8")


def test_merges_into_an_existing_gitignore_without_touching_other_lines(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.pyc\nbuild/\n", encoding="utf-8")
    path = gitignore.ensure_ignored(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "*.pyc" in text and "build/" in text and ".venv/" in text


def test_is_a_no_op_the_second_time(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    gitignore.ensure_ignored(tmp_path)
    before = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.ensure_ignored(tmp_path) is None      # nothing missing anymore
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == before


def test_recognizes_entries_written_without_a_trailing_slash(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(".venv\n__pycache__\n.pycharm-debug\n", encoding="utf-8")
    assert gitignore.ensure_ignored(tmp_path) is None
