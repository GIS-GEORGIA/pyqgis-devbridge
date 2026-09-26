"""install-plugin helpers: linking, idempotency and ini editing (no real QGIS)."""
from __future__ import annotations

from pathlib import Path

import pytest

from devbridge import bridge_plugin as bp


@pytest.fixture
def source(tmp_path: Path) -> Path:
    src = tmp_path / "repo" / "qgis_plugin"
    src.mkdir(parents=True)
    (src / "metadata.txt").write_text("[general]\nname=DevBridge\n")
    (src / "__init__.py").write_text("")
    return src


def test_install_links_then_reports_already(source: Path, tmp_path: Path):
    plugins = tmp_path / "profile" / "python" / "plugins"
    assert bp.install(source, plugins) in ("linked", "copied")  # copy if links unavailable
    assert (plugins / "DevBridge" / "metadata.txt").exists()
    if bp.install(source, plugins, force=False) == "already":
        return
    # copy fallback produced a real dir: re-run must not silently clobber it
    assert bp.install(source, plugins) == "exists"


def test_existing_foreign_folder_needs_force(source: Path, tmp_path: Path):
    plugins = tmp_path / "plugins"
    (plugins / "DevBridge").mkdir(parents=True)
    (plugins / "DevBridge" / "old.txt").write_text("x")
    assert bp.install(source, plugins) == "exists"
    assert (plugins / "DevBridge" / "old.txt").exists()

    assert bp.install(source, plugins, force=True) in ("linked", "copied")
    assert not (plugins / "DevBridge" / "old.txt").exists()
    assert (source / "metadata.txt").exists()  # source untouched by the replacement


def test_copy_mode_makes_independent_copy(source: Path, tmp_path: Path):
    plugins = tmp_path / "plugins"
    assert bp.install(source, plugins, copy=True) == "copied"
    (source / "metadata.txt").unlink()
    assert (plugins / "DevBridge" / "metadata.txt").exists()


def test_enable_appends_section_when_missing(tmp_path: Path):
    ini = tmp_path / "QGIS3.ini"
    ini.write_text("[General]\nx=1\n", encoding="utf-8")
    bp.set_plugin_enabled(ini)
    assert ini.read_text() == "[General]\nx=1\n\n[PythonPlugins]\nDevBridge=true\n"


def test_enable_updates_existing_entry_and_keeps_others(tmp_path: Path):
    ini = tmp_path / "QGIS3.ini"
    ini.write_text("[PythonPlugins]\nfoo=true\nDevBridge=false\n\n[Other]\nDevBridge=keep\n",
                   encoding="utf-8")
    bp.set_plugin_enabled(ini)
    assert ini.read_text() == (
        "[PythonPlugins]\nfoo=true\nDevBridge=true\n\n[Other]\nDevBridge=keep\n"
    )


def test_enable_inserts_into_existing_section_and_preserves_crlf(tmp_path: Path):
    ini = tmp_path / "QGIS3.ini"
    ini.write_bytes(b"[PythonPlugins]\r\nfoo=true\r\n[Other]\r\na=b\r\n")
    bp.set_plugin_enabled(ini)
    assert ini.read_bytes() == b"[PythonPlugins]\r\nDevBridge=true\r\nfoo=true\r\n[Other]\r\na=b\r\n"


def test_profile_dirs_only_existing_default(tmp_path: Path, monkeypatch):
    q3, q4 = tmp_path / "QGIS3" / "profiles", tmp_path / "QGIS4" / "profiles"
    (q3 / "default").mkdir(parents=True)
    (q3 / "other").mkdir()
    monkeypatch.setattr(bp.profiles, "profile_roots", lambda: [q3, q4])
    assert bp.profile_dirs() == [q3 / "default"]
    assert bp.profile_dirs("other") == [q3 / "other"]
