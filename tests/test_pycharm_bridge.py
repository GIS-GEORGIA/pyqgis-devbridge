from __future__ import annotations

import pytest

from qgis_plugin import pycharm_bridge


def test_detect_installation_reads_build_file(tmp_path, monkeypatch):
    install_dir = tmp_path / "PyCharm 2023.3"
    install_dir.mkdir()
    (install_dir / "build.txt").write_text("PY-233.13135.95")
    (install_dir / "product-info.json").write_text('{"version": "2023.3.2"}')

    monkeypatch.setattr(pycharm_bridge, "_candidate_dirs", lambda: [install_dir])

    found = pycharm_bridge.find_pycharm_installations()
    assert len(found) == 1
    assert found[0].build == "233.13135.95"
    assert "Professional" in found[0].display_name


def test_detect_installation_skips_dirs_without_build_file(tmp_path, monkeypatch):
    install_dir = tmp_path / "not-pycharm"
    install_dir.mkdir()
    monkeypatch.setattr(pycharm_bridge, "_candidate_dirs", lambda: [install_dir])
    assert pycharm_bridge.find_pycharm_installations() == []


def test_detect_sorts_newest_build_first(tmp_path, monkeypatch):
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    (old_dir / "build.txt").write_text("PC-231.1.1")
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    (new_dir / "build.txt").write_text("PY-233.13135.95")

    monkeypatch.setattr(pycharm_bridge, "_candidate_dirs", lambda: [old_dir, new_dir])
    found = pycharm_bridge.find_pycharm_installations()
    assert [i.build for i in found] == ["233.13135.95", "231.1.1"]


def test_resolve_pydevd_version_exact_match(monkeypatch):
    monkeypatch.setattr(pycharm_bridge, "_available_pydevd_versions",
                         lambda: ["233.13135.95", "232.10072.31"])
    assert pycharm_bridge.resolve_pydevd_version("233.13135.95") == "233.13135.95"


def test_resolve_pydevd_version_falls_back_to_nearest_same_major(monkeypatch):
    monkeypatch.setattr(pycharm_bridge, "_available_pydevd_versions",
                         lambda: ["233.13135.95", "233.11799.241", "232.10072.31"])
    assert pycharm_bridge.resolve_pydevd_version("233.20000.1") == "233.13135.95"


def test_resolve_pydevd_version_falls_back_across_majors_if_needed(monkeypatch):
    monkeypatch.setattr(pycharm_bridge, "_available_pydevd_versions",
                         lambda: ["232.10072.31"])
    # no 233.x release published at all -> falls back to the closest overall
    assert pycharm_bridge.resolve_pydevd_version("233.20000.1") == "232.10072.31"


def test_resolve_pydevd_version_no_versions_raises(monkeypatch):
    monkeypatch.setattr(pycharm_bridge, "_available_pydevd_versions", lambda: [])
    with pytest.raises(pycharm_bridge.PyCharmBridgeError):
        pycharm_bridge.resolve_pydevd_version("233.1.1")


def test_generate_bridge_script_contains_settrace(tmp_path):
    installation = pycharm_bridge.PyCharmInstallation(
        path=tmp_path, build="233.13135.95", product="PY",
        display_name="PyCharm 2023.3.2 (Professional)",
    )
    script = pycharm_bridge.generate_bridge_script(installation, "localhost", 12345)
    assert "pydevd_pycharm.settrace" in script
    assert "12345" in script
    assert "233.13135.95" in script


def test_write_bridge_script_creates_file(tmp_path):
    installation = pycharm_bridge.PyCharmInstallation(
        path=tmp_path, build="233.13135.95", product="PY",
        display_name="PyCharm 2023.3.2 (Professional)",
    )
    out_dir = tmp_path / "generated"
    path = pycharm_bridge.write_bridge_script(installation, "localhost", 12345, out_dir)
    assert path.exists()
    assert "settrace" in path.read_text()


def test_bridge_auto_configure_raises_not_found_when_nothing_detected(monkeypatch):
    monkeypatch.setattr(pycharm_bridge, "find_pycharm_installations", lambda: [])
    bridge = pycharm_bridge.PyCharmBridge()
    with pytest.raises(pycharm_bridge.PyCharmBridgeError) as exc_info:
        bridge.auto_configure_and_start()
    assert str(exc_info.value) == "not_found"


def test_bridge_auto_configure_raises_already_running():
    bridge = pycharm_bridge.PyCharmBridge()
    bridge._running = True  # noqa: SLF001 - test setup
    with pytest.raises(pycharm_bridge.PyCharmBridgeError) as exc_info:
        bridge.auto_configure_and_start()
    assert str(exc_info.value) == "already_running"


def test_bridge_stop_raises_when_not_running():
    bridge = pycharm_bridge.PyCharmBridge()
    with pytest.raises(pycharm_bridge.PyCharmBridgeError) as exc_info:
        bridge.stop()
    assert str(exc_info.value) == "not_running"
