"""Starting a NEW standalone script: the scaffold, and the CLI path to it
(mirrors test_new_plugin.py's structure for `devbridge new`)."""
from __future__ import annotations

import py_compile
from pathlib import Path

import pytest

from devbridge import cli, scaffold


# --- scaffold -----------------------------------------------------------------------------------

def test_create_script_writes_a_runnable_file(tmp_path: Path):
    path = scaffold.create_script(tmp_path, "my_script")
    assert path == tmp_path / "my_script.py"
    text = path.read_text(encoding="utf-8")
    assert "QgsApplication([], False)" in text and "initQgis()" in text and "exitQgis()" in text
    py_compile.compile(str(path), doraise=True)


def test_create_script_adds_py_extension_only_when_missing(tmp_path: Path):
    assert scaffold.create_script(tmp_path, "already.py").name == "already.py"
    assert scaffold.create_script(tmp_path, "bare").name == "bare.py"


def test_create_script_creates_the_parent_folder(tmp_path: Path):
    target = tmp_path / "nested" / "deeper"
    path = scaffold.create_script(target, "s")
    assert path.exists() and path.parent == target


def test_create_script_refuses_to_overwrite(tmp_path: Path):
    scaffold.create_script(tmp_path, "s")
    with pytest.raises(scaffold.ScaffoldError) as info:
        scaffold.create_script(tmp_path, "s")
    assert str(info.value) == "script_exists"


@pytest.mark.parametrize("name", ["", "has space", "has/slash", "x" * 81, ".hidden"])
def test_create_script_rejects_bad_names(tmp_path: Path, name: str):
    with pytest.raises(scaffold.ScaffoldError) as info:
        scaffold.create_script(tmp_path, name)
    assert str(info.value) == "script_name_invalid"


@pytest.mark.parametrize("name", ["s", "my_script", "my-script", "Script2", "a" * 80])
def test_create_script_accepts_reasonable_names(name: str):
    scaffold.validate_script_name(name)


def test_create_script_title_comes_from_the_name(tmp_path: Path):
    path = scaffold.create_script(tmp_path, "process_layers")
    assert "Process Layers" in path.read_text(encoding="utf-8")
    explicit = scaffold.create_script(tmp_path, "other", title='Custom "Title"')
    assert "Custom 'Title'" in explicit.read_text(encoding="utf-8")


# --- CLI ------------------------------------------------------------------------------------------------

def _no_prompt(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)


def test_cli_new_script_creates_and_prepares(tmp_path: Path, monkeypatch, capsys):
    _no_prompt(monkeypatch)
    prepared: list[Path] = []
    monkeypatch.setattr(cli.pipeline, "find_qgis", lambda **kw: object())
    monkeypatch.setattr(cli.pipeline, "run_setup", lambda path, port=5678, **kw: prepared.append(path))
    code = cli.main(["--lang", "en", "new-script", "my_script", "--dir", str(tmp_path)])
    assert code == 0 and (tmp_path / "my_script.py").exists()
    assert prepared == [tmp_path.resolve()]             # setup runs on the containing folder
    assert "New script created" in capsys.readouterr().out


def test_cli_new_script_no_setup_and_bad_name(tmp_path: Path, monkeypatch, capsys):
    _no_prompt(monkeypatch)
    monkeypatch.setattr(cli.pipeline, "run_setup", lambda *a, **k: pytest.fail("must not prepare"))
    assert cli.main(["new-script", "fine_name", "--dir", str(tmp_path), "--no-setup"]) == 0
    assert cli.main(["new-script", "has space", "--dir", str(tmp_path)]) == 1
    assert "not a valid script name" in capsys.readouterr().out


def test_cli_new_script_without_name_off_terminal_explains(monkeypatch, capsys):
    _no_prompt(monkeypatch)
    assert cli.main(["new-script"]) == 1
    assert "devbridge new-script my_script" in capsys.readouterr().out


def test_cli_new_script_prompts_on_a_terminal(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "typed_name")
    path = cli._new_script(None, str(tmp_path))
    assert path == (tmp_path / "typed_name.py").resolve()


def test_cli_new_script_prompt_handles_eof_gracefully(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert cli._new_script(None, None) is None


def test_cli_new_script_defaults_to_current_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = cli._new_script("here", None)
    assert path == (tmp_path / "here.py").resolve()
