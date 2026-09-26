"""Profile plugin discovery + CLI project-dir resolution (no real QGIS)."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from devbridge import cli, profiles


def _plugin(profile_root: Path, profile: str, name: str) -> Path:
    d = profile_root / profile / "python" / "plugins" / name
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("")
    return d


@pytest.fixture
def qgis3_profiles(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "QGIS" / "QGIS3" / "profiles"
    monkeypatch.setattr(profiles, "profile_roots", lambda: [root])
    return root


def _args(**kw) -> argparse.Namespace:
    return argparse.Namespace(project_dir=kw.get("project_dir"),
                              plugin=kw.get("plugin"), profile=kw.get("profile"))


def test_find_plugins_skips_devbridge_hidden_and_non_plugins(qgis3_profiles: Path):
    mine = _plugin(qgis3_profiles, "default", "MyPlugin")
    _plugin(qgis3_profiles, "default", "DevBridge")
    _plugin(qgis3_profiles, "default", "__pycache__")
    (qgis3_profiles / "default" / "python" / "plugins" / "notaplugin").mkdir()

    found = profiles.find_plugins()
    assert [p.path for p in found] == [mine]
    assert found[0].profile == "default" and found[0].qgis_major == "QGIS3"


def test_default_profile_listed_first_and_profile_filter(qgis3_profiles: Path):
    _plugin(qgis3_profiles, "alpha", "A")
    _plugin(qgis3_profiles, "default", "B")
    assert [p.name for p in profiles.find_plugins()] == ["B", "A"]
    assert [p.name for p in profiles.find_plugins("alpha")] == ["A"]


def test_single_plugin_is_picked_automatically(qgis3_profiles: Path):
    mine = _plugin(qgis3_profiles, "default", "Only")
    assert cli._resolve_project_dir(_args()) == mine.resolve()


def test_named_plugin_case_insensitive(qgis3_profiles: Path):
    _plugin(qgis3_profiles, "default", "One")
    two = _plugin(qgis3_profiles, "default", "Two")
    assert cli._resolve_project_dir(_args(plugin="two")) == two.resolve()


def test_several_plugins_without_tty_fails_with_list(qgis3_profiles: Path, monkeypatch, capsys):
    _plugin(qgis3_profiles, "default", "One")
    _plugin(qgis3_profiles, "default", "Two")
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli._resolve_project_dir(_args()) is None
    assert "One" in capsys.readouterr().out


def test_interactive_pick(qgis3_profiles: Path, monkeypatch):
    _plugin(qgis3_profiles, "default", "One")
    two = _plugin(qgis3_profiles, "default", "Two")
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")
    assert cli._resolve_project_dir(_args()) == two.resolve()


def test_explicit_project_dir_wins(qgis3_profiles: Path, tmp_path: Path):
    _plugin(qgis3_profiles, "default", "One")
    assert cli._resolve_project_dir(_args(project_dir=str(tmp_path))) == tmp_path.resolve()


def test_no_plugins_reports_error(qgis3_profiles: Path, capsys):
    assert cli._resolve_project_dir(_args()) is None
    assert "--project-dir" in capsys.readouterr().out
