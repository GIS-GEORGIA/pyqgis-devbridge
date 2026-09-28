"""CLI wiring for `devbridge link-plugin` and `devbridge uninstall` - the
actual behaviour is covered by test_link_plugin.py / test_uninstall.py, this
just checks argparse wires the right arguments through."""
from __future__ import annotations

from pathlib import Path

from devbridge import cli


def test_cmd_link_plugin_passes_parsed_args_through(tmp_path, monkeypatch):
    seen = {}

    def fake_link(path, name=None, profile=None, copy=False, force=False, log=print):
        seen.update(path=path, name=name, profile=profile, copy=copy, force=force)
        return 0

    monkeypatch.setattr(cli.link_plugin, "link_into_profiles", fake_link)
    code = cli.main(["--lang", "en", "link-plugin", str(tmp_path / "my_plugin"),
                     "--name", "renamed", "--profile", "work", "--copy", "--force"])
    assert code == 0
    assert seen == {"path": Path(tmp_path / "my_plugin"), "name": "renamed",
                    "profile": "work", "copy": True, "force": True}


def test_cmd_link_plugin_defaults(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli.link_plugin, "link_into_profiles",
                        lambda path, name=None, profile=None, copy=False, force=False, log=print:
                        seen.update(name=name, profile=profile, copy=copy, force=force) or 0)
    assert cli.main(["link-plugin", str(tmp_path)]) == 0
    assert seen == {"name": None, "profile": None, "copy": False, "force": False}


def test_cmd_link_plugin_propagates_nonzero_status(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.link_plugin, "link_into_profiles", lambda *a, **k: 1)
    assert cli.main(["link-plugin", str(tmp_path)]) == 1


def test_cmd_uninstall_removes_devbridge_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.uninstall, "uninstall_plugin",
                        lambda profile=None, name=None: calls.append(("plugin", profile, name)) or 0)
    monkeypatch.setattr(cli.uninstall, "uninstall_project",
                        lambda path: calls.append(("project", path)) or 0)
    assert cli.main(["--lang", "en", "uninstall"]) == 0
    assert calls == [("plugin", None, "DevBridge")]


def test_cmd_uninstall_with_project_dir_cleans_both(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli.uninstall, "uninstall_plugin",
                        lambda profile=None, name=None: calls.append(("plugin", name)) or 0)
    monkeypatch.setattr(cli.uninstall, "uninstall_project",
                        lambda path: calls.append(("project", path)) or 0)
    assert cli.main(["uninstall", "--project-dir", str(tmp_path)]) == 0
    assert calls == [("plugin", "DevBridge"), ("project", Path(tmp_path))]


def test_cmd_uninstall_keep_plugin_only_cleans_project(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli.uninstall, "uninstall_plugin",
                        lambda profile=None, name=None: calls.append("plugin") or 0)
    monkeypatch.setattr(cli.uninstall, "uninstall_project",
                        lambda path: calls.append("project") or 0)
    assert cli.main(["uninstall", "--project-dir", str(tmp_path), "--keep-plugin"]) == 0
    assert calls == ["project"]


def test_cmd_uninstall_can_target_a_different_name(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli.uninstall, "uninstall_plugin",
                        lambda profile=None, name=None: seen.update(profile=profile, name=name) or 0)
    assert cli.main(["uninstall", "--name", "my_plugin", "--profile", "work"]) == 0
    assert seen == {"profile": "work", "name": "my_plugin"}


def test_cmd_uninstall_propagates_a_nonzero_status(monkeypatch):
    monkeypatch.setattr(cli.uninstall, "uninstall_plugin", lambda **kw: 1)
    assert cli.main(["uninstall"]) == 1
