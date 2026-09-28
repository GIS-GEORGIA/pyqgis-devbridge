"""Starting a NEW plugin: the scaffold, the CLI paths to it, and choosing between
existing / new in the profile lists."""
from __future__ import annotations

import argparse
import configparser
import py_compile
from pathlib import Path

import pytest

from devbridge import cli, profiles, scaffold
from qgis_plugin import profile_plugins


# --- scaffold -----------------------------------------------------------------------------------

def test_scaffold_writes_a_loadable_plugin(tmp_path: Path):
    path = scaffold.create_plugin(tmp_path, "my_plugin", author="Kapo", email="k@example.org")
    assert path == tmp_path / "my_plugin"
    assert sorted(p.name for p in path.iterdir()) == [".gitignore", "__init__.py", "metadata.txt", "plugin.py"]
    for name in ("__init__.py", "plugin.py"):
        py_compile.compile(str(path / name), doraise=True)
    meta = configparser.RawConfigParser()
    meta.read_string((path / "metadata.txt").read_text(encoding="utf-8"))
    general = meta["general"]
    assert general["name"] == "My Plugin" and general["author"] == "Kapo" and general["email"] == "k@example.org"
    assert general["qgisMinimumVersion"] == "3.40" and general["supportsQt6"] == "True"
    assert "class MyPluginPlugin" in (path / "plugin.py").read_text(encoding="utf-8")
    assert "from .plugin import MyPluginPlugin" in (path / "__init__.py").read_text(encoding="utf-8")


def test_scaffold_code_is_qt5_and_qt6_safe(tmp_path: Path):
    text = (scaffold.create_plugin(tmp_path, "hello_qgis") / "plugin.py").read_text(encoding="utf-8")
    assert "from qgis.PyQt" in text and "PyQt5" not in text and "PyQt6" not in text
    assert "exec_" not in text


@pytest.mark.parametrize("name,key", [("", "name_invalid"), ("My_Plugin", "name_invalid"), ("1abc", "name_invalid"),
                                       ("a", "name_invalid"), ("has space", "name_invalid"),
                                       ("x" * 41, "name_invalid"), ("devbridge", "name_reserved")])
def test_scaffold_rejects_bad_names(tmp_path: Path, name: str, key: str):
    with pytest.raises(scaffold.ScaffoldError) as info:
        scaffold.create_plugin(tmp_path, name)
    assert str(info.value) == key
    assert list(tmp_path.iterdir()) == []


def test_scaffold_refuses_to_overwrite_and_needs_a_parent(tmp_path: Path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "important.py").write_text("x")
    with pytest.raises(scaffold.ScaffoldError) as info:
        scaffold.create_plugin(tmp_path, "taken")
    assert str(info.value) == "exists" and (tmp_path / "taken" / "important.py").exists()
    (tmp_path / "empty_one").mkdir()
    assert scaffold.create_plugin(tmp_path, "empty_one").is_dir()          # an empty folder is fine
    with pytest.raises(scaffold.ScaffoldError) as info:
        scaffold.create_plugin(tmp_path / "missing", "abc")
    assert str(info.value) == "parent_missing"


def test_scaffold_valid_names_are_accepted():
    for name in ("ab", "my_plugin", "geo2_tools", "a" + "b" * 39):
        scaffold.validate_name(name)


# --- profiles: where a new plugin goes --------------------------------------------------------------

def test_default_plugins_dir_prefers_qgis3_then_qgis4(tmp_path: Path, monkeypatch):
    q3, q4 = tmp_path / "QGIS3" / "profiles", tmp_path / "QGIS4" / "profiles"
    monkeypatch.setattr(profiles, "profile_roots", lambda: [q3, q4])
    assert profiles.default_plugins_dir() is None
    (q4 / "default").mkdir(parents=True)
    assert profiles.default_plugins_dir() == q4 / "default" / "python" / "plugins"
    (q3 / "default").mkdir(parents=True)
    assert profiles.default_plugins_dir() == q3 / "default" / "python" / "plugins"
    assert profiles.default_plugins_dir("4") == q4 / "default" / "python" / "plugins"


# --- CLI ------------------------------------------------------------------------------------------------

def _no_prompt(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)


def test_cli_new_creates_and_prepares(tmp_path: Path, monkeypatch, capsys):
    _no_prompt(monkeypatch)
    prepared: list[Path] = []
    monkeypatch.setattr(cli.pipeline, "find_qgis", lambda **kw: object())   # any non-None sentinel
    monkeypatch.setattr(cli.pipeline, "run_setup", lambda path, port=5678, **kw: prepared.append(path))
    code = cli.main(["--lang", "en", "new", "my_plugin", "--dir", str(tmp_path)])
    assert code == 0 and (tmp_path / "my_plugin" / "plugin.py").exists()
    assert prepared == [(tmp_path / "my_plugin").resolve()]
    assert "New plugin created" in capsys.readouterr().out


def test_cli_new_no_setup_and_bad_name(tmp_path: Path, monkeypatch, capsys):
    _no_prompt(monkeypatch)
    monkeypatch.setattr(cli.pipeline, "run_setup", lambda *a, **k: pytest.fail("must not prepare"))
    assert cli.main(["new", "fine_name", "--dir", str(tmp_path), "--no-setup"]) == 0
    assert cli.main(["new", "Bad Name", "--dir", str(tmp_path)]) == 1
    assert "not a valid plugin name" in capsys.readouterr().out
    assert not (tmp_path / "Bad Name").exists()


def test_cli_new_without_name_off_terminal_explains(monkeypatch, capsys):
    _no_prompt(monkeypatch)
    assert cli.main(["new"]) == 1
    assert "devbridge new my_plugin" in capsys.readouterr().out


def _args(**kw) -> argparse.Namespace:
    return argparse.Namespace(project_dir=None, plugin=None, profile=None, **kw)


def test_picker_offers_new_plugin_and_creates_it(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "QGIS3" / "profiles"
    for name in ("one", "two"):
        d = root / "default" / "python" / "plugins" / name
        d.mkdir(parents=True)
        (d / "__init__.py").write_text("")
    monkeypatch.setattr(profiles, "profile_roots", lambda: [root])
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    answers = iter(["n", "brand_new"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    path = cli._resolve_project_dir(_args())
    assert path == (root / "default" / "python" / "plugins" / "brand_new").resolve()
    assert (path / "plugin.py").exists()
    out = capsys.readouterr().out
    assert "N. Start a NEW plugin" in out


def test_no_plugins_on_a_terminal_offers_a_new_one(tmp_path: Path, monkeypatch):
    root = tmp_path / "QGIS3" / "profiles"
    (root / "default").mkdir(parents=True)
    monkeypatch.setattr(profiles, "profile_roots", lambda: [root])
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "first_plugin")
    path = cli._resolve_project_dir(_args())
    assert path is not None and path.name == "first_plugin"


# --- the QGIS panel's list: every profile, running one first, nothing pre-chosen -------------------------

def _plugin(profiles_root: Path, profile: str, name: str) -> None:
    d = profiles_root / profile / "python" / "plugins" / name
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("")


def test_list_all_spans_qgis3_and_qgis4_with_running_profile_first(tmp_path: Path):
    q3, q4 = tmp_path / "QGIS" / "QGIS3" / "profiles", tmp_path / "QGIS" / "QGIS4" / "profiles"
    for n in ("zeta", "alpha"):
        _plugin(q3, "default", n)
    _plugin(q4, "default", "postgis_manager")
    _plugin(q3, "work", "other")
    _plugin(q3, "default", "DevBridge")                       # never listed

    entries = profile_plugins.list_all(q4 / "default")        # running QGIS 4
    assert [e.name for e in entries][:1] == ["postgis_manager"] and entries[0].current
    assert sorted(e.label for e in entries[1:]) == [
        "alpha  (QGIS3/default)", "other  (QGIS3/work)", "zeta  (QGIS3/default)"]
    assert not any(e.current for e in entries[1:])
    assert not any(e.name == "DevBridge" for e in entries)


def test_list_all_falls_back_to_the_running_profile_only(tmp_path: Path):
    weird = tmp_path / "custom" / "profiles"
    _plugin(weird, "default", "solo")
    _plugin(weird, "second", "duo")
    assert sorted(e.name for e in profile_plugins.list_all(weird / "default")) == ["duo", "solo"]
    assert profile_plugins.new_plugin_parent(weird / "default") == weird / "default" / "python" / "plugins"


def test_picker_handles_eof_gracefully(tmp_path: Path, monkeypatch):
    """Same isatty()-lies scenario as the QGIS picker, for the plugin picker
    and the new-plugin name prompt."""
    root = tmp_path / "QGIS3" / "profiles"
    for name in ("one", "two"):
        _plugin(root, "default", name)
    monkeypatch.setattr(profiles, "profile_roots", lambda: [root])
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert cli._resolve_project_dir(_args()) is None


def test_new_name_prompt_handles_eof_gracefully(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert cli._new_plugin(None, None) is None
