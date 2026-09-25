"""These tests exercise the pure-filesystem logic without needing a real
QGIS install, by constructing a fake QgisInstallation pointing at a temp
directory that stands in for the QGIS python folder.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import pytest

from devbridge.detectors.base import QgisInstallation
from devbridge import env_builder


@pytest.fixture
def fake_qgis(tmp_path: Path) -> QgisInstallation:
    qgis_python_dir = tmp_path / "qgis_python"
    (qgis_python_dir / "qgis").mkdir(parents=True)
    (qgis_python_dir / "qgis" / "__init__.py").write_text("")
    plugins_dir = qgis_python_dir / "plugins"
    plugins_dir.mkdir()
    return QgisInstallation(
        root=tmp_path,
        python_exe=Path(sys.executable),
        qgis_python_dir=qgis_python_dir,
        plugins_dir=plugins_dir,
        bin_dirs=(),
        version_hint="test",
    )


def test_build_venv_creates_pth_file(fake_qgis: QgisInstallation, tmp_path: Path):
    venv_path = tmp_path / "venv"
    result = env_builder.build_venv(fake_qgis, venv_path, verbose_print=lambda *_: None)
    assert result == venv_path
    assert venv_path.exists()

    site_packages = env_builder._site_packages_dir(venv_path)
    pth_file = site_packages / "qgis.pth"
    assert pth_file.exists()
    content = pth_file.read_text()
    assert str(fake_qgis.qgis_python_dir) in content
    assert str(fake_qgis.plugins_dir) in content


def test_build_venv_is_idempotent(fake_qgis: QgisInstallation, tmp_path: Path):
    venv_path = tmp_path / "venv"
    env_builder.build_venv(fake_qgis, venv_path, verbose_print=lambda *_: None)
    # second call should not raise even though the venv already exists
    env_builder.build_venv(fake_qgis, venv_path, verbose_print=lambda *_: None)
