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
