"""devbridge link-plugin: generalizes bridge_plugin's install/enable
(written for DevBridge itself) to any plugin folder and any name."""
from __future__ import annotations

from pathlib import Path

import pytest

from devbridge import link_plugin


@pytest.fixture
def source(tmp_path: Path) -> Path:
    src = tmp_path / "repo" / "my_plugin"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    return src


def test_validate_source_rejects_missing_folder_and_non_plugin(tmp_path: Path):
    assert link_plugin.validate_source(tmp_path / "nope") == "link_source_missing"
    empty = tmp_path / "empty"
    empty.mkdir()
    assert link_plugin.validate_source(empty) == "link_source_not_a_plugin"


def test_validate_source_accepts_a_plugin_folder(source: Path):
    assert link_plugin.validate_source(source) is None


def test_link_into_profiles_links_and_enables(source: Path, tmp_path: Path, monkeypatch):
    root = tmp_path / "QGIS3" / "profiles"
    prof = root / "default"
    (prof / "QGIS").mkdir(parents=True)
    (prof / "QGIS" / "QGIS3.ini").write_text("[General]\nx=1\n", encoding="utf-8")
    monkeypatch.setattr(link_plugin.bridge_plugin.profiles, "profile_roots", lambda: [root])
    monkeypatch.setattr(link_plugin.bridge_plugin, "qgis_running", lambda: False)

    logs = []
    assert link_plugin.link_into_profiles(source, log=logs.append) == 0
    target = prof / "python" / "plugins" / "my_plugin"
    assert target.exists()
    assert link_plugin.bridge_plugin.is_plugin_enabled(prof / "QGIS" / "QGIS3.ini", "my_plugin") is True
    assert any("my_plugin" in m for m in logs)


def test_link_into_profiles_uses_a_custom_name(source: Path, tmp_path: Path, monkeypatch):
    root = tmp_path / "QGIS3" / "profiles"
    (root / "default").mkdir(parents=True)
    monkeypatch.setattr(link_plugin.bridge_plugin.profiles, "profile_roots", lambda: [root])
    monkeypatch.setattr(link_plugin.bridge_plugin, "qgis_running", lambda: False)

    link_plugin.link_into_profiles(source, name="renamed", log=lambda _m: None)
    plugins_dir = root / "default" / "python" / "plugins"
    assert (plugins_dir / "renamed").exists()
    assert not (plugins_dir / "my_plugin").exists()


def test_link_into_profiles_needs_force_to_replace(source: Path, tmp_path: Path, monkeypatch):
    root = tmp_path / "QGIS3" / "profiles"
    plugins_dir = root / "default" / "python" / "plugins"
    (plugins_dir / "my_plugin").mkdir(parents=True)
    (plugins_dir / "my_plugin" / "old.txt").write_text("x")
    monkeypatch.setattr(link_plugin.bridge_plugin.profiles, "profile_roots", lambda: [root])
    monkeypatch.setattr(link_plugin.bridge_plugin, "qgis_running", lambda: False)

    assert link_plugin.link_into_profiles(source, log=lambda _m: None) == 1
    assert (plugins_dir / "my_plugin" / "old.txt").exists()
    assert link_plugin.link_into_profiles(source, force=True, log=lambda _m: None) == 0
    assert not (plugins_dir / "my_plugin" / "old.txt").exists()


def test_link_into_profiles_reports_missing_profile(source: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(link_plugin.bridge_plugin.profiles, "profile_roots", lambda: [tmp_path / "nowhere"])
    logs = []
    assert link_plugin.link_into_profiles(source, log=logs.append) == 1
    assert logs


def test_link_into_profiles_rejects_a_bad_source(tmp_path: Path):
    logs = []
    assert link_plugin.link_into_profiles(tmp_path / "missing", log=logs.append) == 1
    assert logs
