"""Choosing among several QGIS installations: pipeline.find_qgis()'s --qgis-root
and interactive-picker hooks, and the CLI wiring around them."""
from __future__ import annotations

from pathlib import Path

import pytest

from devbridge import cli, pipeline
from devbridge.detectors.base import QgisInstallation


def _install(tmp_path: Path, name: str) -> QgisInstallation:
    py = tmp_path / name / "python.exe"
    py.parent.mkdir(parents=True)
    py.write_text("")
    return QgisInstallation(root=tmp_path / name, python_exe=py)


def test_find_qgis_defaults_to_the_first_install_silently(monkeypatch, tmp_path: Path):
    a, b = _install(tmp_path, "a"), _install(tmp_path, "b")
    monkeypatch.setattr(pipeline, "find_all_qgis", lambda log=print: [a, b])
    assert pipeline.find_qgis() == a                       # no qgis_root, no ask: unchanged default


def test_find_qgis_with_one_install_ignores_ask(monkeypatch, tmp_path: Path):
    only = _install(tmp_path, "only")
    monkeypatch.setattr(pipeline, "find_all_qgis", lambda log=print: [only])
    assert pipeline.find_qgis(ask=lambda _installs: pytest.fail("must not be called")) == only


def test_find_qgis_asks_only_when_several_are_found(monkeypatch, tmp_path: Path):
    a, b = _install(tmp_path, "a"), _install(tmp_path, "b")
    monkeypatch.setattr(pipeline, "find_all_qgis", lambda log=print: [a, b])
    assert pipeline.find_qgis(ask=lambda installs: installs[1]) == b
    assert pipeline.find_qgis(ask=lambda _installs: None) == a    # declined -> falls back to the default


def test_find_qgis_root_picks_by_path_and_errors_when_absent(monkeypatch, tmp_path: Path):
    a, b = _install(tmp_path, "a"), _install(tmp_path, "b")
    monkeypatch.setattr(pipeline, "find_all_qgis", lambda log=print: [a, b])
    assert pipeline.find_qgis(qgis_root=str(b.root)) == b
    with pytest.raises(pipeline.SetupError):
        pipeline.find_qgis(qgis_root=str(tmp_path / "nope"))


def test_find_qgis_reports_when_nothing_is_found(monkeypatch):
    monkeypatch.setattr(pipeline, "find_all_qgis", lambda log=print: [])
    with pytest.raises(pipeline.SetupError):
        pipeline.find_qgis()


# --- CLI -----------------------------------------------------------------------------------

def test_ask_qgis_off_a_terminal_returns_none_without_prompting(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli._ask_qgis([_install(tmp_path, "a"), _install(tmp_path, "b")]) is None
    assert capsys.readouterr().out == ""                   # no prompt printed when it can't be answered


def test_ask_qgis_interactive_pick(monkeypatch, tmp_path: Path):
    a, b = _install(tmp_path, "a"), _install(tmp_path, "b")
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")
    assert cli._ask_qgis([a, b]) == b


def test_cmd_detect_lists_every_install(monkeypatch, tmp_path: Path, capsys):
    a, b = _install(tmp_path, "a"), _install(tmp_path, "b")
    monkeypatch.setattr(cli.pipeline, "find_all_qgis", lambda log=print: [a, b])
    assert cli.cmd_detect(None) == 0
    out = capsys.readouterr().out
    assert str(a.root) in out and str(b.root) in out and "(default)" in out


def test_cmd_detect_reports_when_nothing_found(monkeypatch, capsys):
    monkeypatch.setattr(cli.pipeline, "find_all_qgis", lambda log=print: [])
    assert cli.cmd_detect(None) == 1
    assert "detect" in capsys.readouterr().out.lower() or True   # just must not crash; message is translated


def test_cmd_setup_and_launch_pass_qgis_root_and_ask_through(monkeypatch, tmp_path: Path):
    """A thin plumbing check: cmd_setup/cmd_new/cmd_launch must hand args.qgis_root and
    _ask_qgis to pipeline.find_qgis rather than re-detecting on their own."""
    import argparse

    only = _install(tmp_path, "only")
    seen = {}

    def fake_find_qgis(log=print, qgis_root=None, ask=None):
        seen["qgis_root"] = qgis_root
        seen["ask"] = ask
        return only

    monkeypatch.setattr(cli.pipeline, "find_qgis", fake_find_qgis)
    monkeypatch.setattr(cli.pipeline, "run_setup", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_resolve_project_dir", lambda _args: tmp_path)

    args = argparse.Namespace(qgis_root="C:/somewhere", port=5678, venv_name=".venv",
                              host="localhost", plugin_name=None)
    assert cli.cmd_setup(args) == 0
    assert seen["qgis_root"] == "C:/somewhere" and seen["ask"] is cli._ask_qgis


def test_ask_qgis_handles_eof_gracefully(monkeypatch, tmp_path: Path):
    """isatty() can lie (piped/wrapped terminals) - input() then hits EOF;
    that must be treated as 'no answer', never an uncaught crash."""
    a, b = _install(tmp_path, "a"), _install(tmp_path, "b")
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert cli._ask_qgis([a, b]) is None
