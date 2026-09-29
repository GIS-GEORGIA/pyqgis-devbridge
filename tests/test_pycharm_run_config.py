"""PyCharm's "Python Debug Server" run configuration XML.

Not runnable through a real PyCharm here (see pycharm_run_config.py's
docstring for what this shape is cross-checked against instead), so these
tests are about the generator's own contract: valid XML, the right
type/factoryName, correct escaping, and a stable/sane file name - not
"PyCharm accepts this", which nothing here can prove."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from devbridge import pycharm_config, pycharm_run_config as prc


def test_build_run_config_xml_is_well_formed_and_has_the_right_type():
    xml = prc.build_run_config_xml()
    root = ET.fromstring(xml)          # raises if malformed
    assert root.tag == "component" and root.get("name") == "ProjectRunConfigurationManager"
    config = root.find("configuration")
    assert config.get("type") == "PyRemoteDebugConfigurationType"
    assert config.get("factoryName") == "Python Remote Debug"
    assert config.get("name") == prc.RUN_CONFIG_NAME


def test_port_and_host_are_set():
    root = ET.fromstring(prc.build_run_config_xml(host="192.168.1.5", port=54321))
    options = {o.get("name"): o.get("value") for o in root.find("configuration").findall("option")}
    assert options["PORT"] == "54321" and options["HOST"] == "192.168.1.5"


def test_redirect_and_suspend_options_present_with_documented_defaults():
    root = ET.fromstring(prc.build_run_config_xml())
    options = {o.get("name"): o.get("value") for o in root.find("configuration").findall("option")}
    assert options["REDIRECT_OUTPUT"] == "true"    # matches PyCharm's own default for this config type
    assert options["SUSPEND_AFTER_CONNECT"] == "false"


def test_no_path_mapping_without_a_remote_root():
    root = ET.fromstring(prc.build_run_config_xml())
    assert root.find("configuration/PathMappingSettings") is None


def test_path_mapping_with_a_remote_root():
    root = ET.fromstring(prc.build_run_config_xml(remote_root="/home/user/.local/share/QGIS/.../my_plugin"))
    mapping = root.find("configuration/PathMappingSettings/option/list/mapping")
    assert mapping.get("local-root") == "$PROJECT_DIR$"
    assert mapping.get("remote-root") == "/home/user/.local/share/QGIS/.../my_plugin"


def test_special_characters_in_name_and_host_are_escaped_not_broken():
    xml = prc.build_run_config_xml(name='Debug "Server" & Co', host="localhost")
    root = ET.fromstring(xml)          # would raise on unescaped & or "
    assert root.find("configuration").get("name") == 'Debug "Server" & Co'


def test_config_filename_is_safe_and_stable():
    assert prc._config_filename("PyQGIS Debug Server") == "PyQGIS_Debug_Server.xml"
    assert prc._config_filename("weird/name:here") == "weird_name_here.xml"


def test_write_run_config_creates_the_file_under_idea_runconfigurations(tmp_path: Path):
    path = prc.write_run_config(tmp_path, host="localhost", port=12345)
    assert path == tmp_path / ".idea" / "runConfigurations" / "PyQGIS_Debug_Server.xml"
    assert path.exists()
    ET.fromstring(path.read_text(encoding="utf-8"))    # still well-formed on disk


def test_write_run_config_is_refreshed_on_a_second_call(tmp_path: Path):
    prc.write_run_config(tmp_path, port=1111)
    path = prc.write_run_config(tmp_path, port=2222)
    assert 'value="2222"' in path.read_text(encoding="utf-8")
    assert 'value="1111"' not in path.read_text(encoding="utf-8")


# --- pycharm_config.write_pycharm_run_config: the plugin_name -> path mapping wiring -------------

def test_write_pycharm_run_config_without_plugin_name_has_no_mapping(tmp_path: Path):
    path = pycharm_config.write_pycharm_run_config(tmp_path, host="localhost", port=12345)
    assert "PathMappingSettings" not in path.read_text(encoding="utf-8")


def test_write_pycharm_run_config_maps_the_profile_plugin_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    path = pycharm_config.write_pycharm_run_config(tmp_path, plugin_name="my_plugin")
    text = path.read_text(encoding="utf-8")
    assert "my_plugin" in text and "PathMappingSettings" in text


def test_write_pycharm_run_config_logs_the_written_path(tmp_path: Path):
    msgs = []
    pycharm_config.write_pycharm_run_config(tmp_path, verbose_print=msgs.append)
    assert any("runConfigurations" in m for m in msgs)
