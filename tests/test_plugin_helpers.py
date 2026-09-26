"""Pure-Python parts of the QGIS plugin (no qgis.* needed) and the zip builder."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import make_plugin_zip
from devbridge import config as tool_config
from qgis_plugin import profile_plugins, shared_config, tool_launcher


# --- shared settings: plugin copy must behave exactly like the tool's -------------

def test_shared_config_matches_tool_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEVBRIDGE_CONFIG", str(tmp_path / "c.json"))
    assert shared_config.DEFAULTS == tool_config.DEFAULTS
    assert shared_config.config_path() == tool_config.config_path()

    shared_config.save({"lang": "ka", "port": 6001})
    loaded = tool_config.load()                      # written by the plugin, read by the tool
    assert loaded["lang"] == "ka" and loaded["port"] == 6001 and loaded["host"] == "localhost"

    tool_config.save({**loaded, "pycharm_port": 12399})   # and the other way round
    assert shared_config.load()["pycharm_port"] == 12399


def test_shared_config_ignores_garbage_and_unknown_keys(tmp_path: Path, monkeypatch):
    path = tmp_path / "c.json"
    monkeypatch.setenv("DEVBRIDGE_CONFIG", str(path))
    path.write_text("{not json", encoding="utf-8")
    assert shared_config.load() == shared_config.DEFAULTS
    path.write_text('{"port": 7000, "evil": 1}', encoding="utf-8")
    cfg = shared_config.load()
    assert cfg["port"] == 7000 and "evil" not in cfg


# --- profile plugin listing ------------------------------------------------------

def test_list_plugins_skips_devbridge_hidden_and_non_packages(tmp_path: Path):
    plugins = tmp_path / "python" / "plugins"
    for name in ("Zeta", "alpha", "DevBridge", "_private", ".hidden"):
        (plugins / name).mkdir(parents=True)
        (plugins / name / "__init__.py").write_text("")
    (plugins / "not_a_plugin").mkdir()
    (plugins / "file.txt").write_text("x")

    assert [p.name for p in profile_plugins.list_plugins(tmp_path)] == ["alpha", "Zeta"]
    assert profile_plugins.list_plugins(tmp_path / "missing") == []


# --- tool launcher helpers ---------------------------------------------------------

def test_guess_qgis_root():
    assert tool_launcher.guess_qgis_root("C:/Program Files/QGIS 3.44.5/apps/qgis-ltr") == Path(
        "C:/Program Files/QGIS 3.44.5")
    assert tool_launcher.guess_qgis_root("/usr") is None


def test_scrubbed_env_drops_qgis_python_variables(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PYTHONHOME", "C:/qgis/python")
    monkeypatch.setenv("PYTHONPATH", "C:/qgis/python/plugins")
    env = tool_launcher.scrubbed_env()
    assert "PYTHONHOME" not in env and "PYTHONPATH" not in env
    assert tool_launcher.scrubbed_env(tmp_path)["PYTHONPATH"] == str(tmp_path)


def test_tool_dir_prefers_bundled_copy_then_repo_src(tmp_path: Path, monkeypatch):
    plugin = tmp_path / "DevBridge"
    monkeypatch.setattr(tool_launcher, "_PLUGIN_DIR", plugin)
    assert tool_launcher.tool_dir() is None                       # nothing yet
    with pytest.raises(tool_launcher.ToolMissingError):
        tool_launcher.ensure_importable()

    (tmp_path / "src" / "devbridge").mkdir(parents=True)          # repo layout: <repo>/src next to <repo>/qgis_plugin
    (tmp_path / "src" / "devbridge" / "__init__.py").write_text("")
    assert tool_launcher.tool_dir() == tmp_path / "src"
    assert tool_launcher.folder_to_open() == tmp_path             # repo root, not src/

    (plugin / "tool" / "devbridge").mkdir(parents=True)           # zip layout wins
    (plugin / "tool" / "devbridge" / "__init__.py").write_text("")
    assert tool_launcher.tool_dir() == plugin / "tool"
    assert tool_launcher.folder_to_open() == plugin / "tool"


def test_find_gui_python_reports_no_tk(monkeypatch):
    monkeypatch.setattr(tool_launcher, "_gui_python_cache", None)
    monkeypatch.setattr(tool_launcher, "_candidates", lambda: [["definitely-not-a-python"]])
    with pytest.raises(tool_launcher.NoTkError):
        tool_launcher.find_gui_python()


# --- the zip that goes to plugins.qgis.ge ---------------------------------------------

@pytest.fixture(scope="module")
def built_zip(tmp_path_factory) -> Path:
    return make_plugin_zip.build(tmp_path_factory.mktemp("dist"))


def test_zip_layout_matches_plugin_id_and_bundles_the_tool(built_zip: Path):
    names = zipfile.ZipFile(built_zip).namelist()
    assert built_zip.name == "DevBridge.zip"
    assert all(n.startswith("DevBridge/") for n in names)                 # root folder == zip name == plugin id
    for required in ("DevBridge/metadata.txt", "DevBridge/plugin.py", "DevBridge/icon.png",
                     "DevBridge/ui/control_panel.py", "DevBridge/tool/devbridge/pipeline.py",
                     "DevBridge/tool/devbridge/gui.py", "DevBridge/tool/devbridge/i18n/ka.json",
                     "DevBridge/tool/devbridge_gui.pyw", "DevBridge/tool/README.txt"):
        assert required in names, required
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]


def test_zip_is_reproducible(built_zip: Path, tmp_path: Path):
    again = make_plugin_zip.build(tmp_path)
    assert built_zip.read_bytes() == again.read_bytes()


def test_plugin_never_imports_the_tool_at_module_level():
    """Design rule: qgis_plugin must not depend on src/devbridge being importable;
    it only ever reaches the bundled copy through tool_launcher.ensure_importable()."""
    import re
    for path in Path("qgis_plugin").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        top_level = [ln for ln in text.splitlines() if re.match(r"(from|import) devbridge\b", ln)]
        assert not top_level, f"{path}: {top_level}"
