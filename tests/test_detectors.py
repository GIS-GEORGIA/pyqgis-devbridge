"""Detector tests use monkeypatched filesystem roots so they run on CI
without a real QGIS install."""
from __future__ import annotations

from pathlib import Path

from devbridge.detectors import windows as win_detector


def test_windows_detector_finds_osgeo4w_layout(tmp_path: Path, monkeypatch):
    root = tmp_path / "OSGeo4W64"
    qgis_python = root / "apps" / "qgis" / "python"
    (qgis_python / "qgis").mkdir(parents=True)
    py_dir = root / "apps" / "Python312"
    py_dir.mkdir(parents=True)
    (py_dir / "python.exe").write_text("")
    (root / "bin").mkdir(parents=True)

    monkeypatch.setattr(win_detector, "_CANDIDATE_ROOTS", [str(root)])
    monkeypatch.setattr(win_detector, "_env_root", lambda: None)

    result = win_detector.find_qgis()
    assert result is not None
    assert result.qgis_python_dir == qgis_python
    assert result.python_exe == py_dir / "python.exe"


def test_windows_detector_returns_none_when_nothing_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(win_detector, "_CANDIDATE_ROOTS", [str(tmp_path / "nope")])
    monkeypatch.setattr(win_detector, "_env_root", lambda: None)
    assert win_detector.find_qgis() is None


from devbridge.detectors import macos as mac_detector  # noqa: E402


def _make_bundle(apps: Path, name: str = "QGIS-LTR.app") -> Path:
    contents = apps / name / "Contents"
    (contents / "Resources" / "python" / "qgis").mkdir(parents=True)
    (contents / "Resources" / "python" / "plugins").mkdir()
    (contents / "MacOS" / "bin").mkdir(parents=True)
    (contents / "MacOS" / "bin" / "python3").write_text("")
    (contents / "Frameworks").mkdir()
    return contents


def test_macos_detector_finds_app_bundle(tmp_path: Path, monkeypatch):
    contents = _make_bundle(tmp_path)
    monkeypatch.setattr(mac_detector, "_APP_DIRS", [str(tmp_path)])

    result = mac_detector.find_qgis()
    assert result is not None
    assert result.root == contents.parent
    assert result.qgis_python_dir == contents / "Resources" / "python"
    assert result.plugins_dir == contents / "Resources" / "python" / "plugins"
    assert result.python_exe == contents / "MacOS" / "bin" / "python3"
    assert contents / "Frameworks" in result.bin_dirs


def test_macos_detector_returns_none_when_nothing_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(mac_detector, "_APP_DIRS", [str(tmp_path / "nope")])
    monkeypatch.setattr(mac_detector.shutil, "which", lambda _name: None)
    assert mac_detector.find_qgis() is None


def test_get_detector_picks_module_by_platform(monkeypatch):
    import platform

    from devbridge import detectors

    for system, expected in (("Windows", "windows"), ("Darwin", "macos"), ("Linux", "linux")):
        monkeypatch.setattr(platform, "system", lambda s=system: s)
        assert detectors.get_detector().__name__.rsplit(".", 1)[-1] == expected
