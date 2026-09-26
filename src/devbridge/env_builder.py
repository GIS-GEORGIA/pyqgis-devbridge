"""Create a Python virtual environment that can `import qgis`, on either
Windows or Linux, following the community-standard recipe (OSGeo4W
--system-site-packages venv + qgis.pth + sitecustomize.py DLL shim).
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from .detectors.base import QgisInstallation
from .i18n_util import t
from .proc import run_logged


def build_venv(qgis: QgisInstallation, venv_path: Path, verbose_print=print) -> Path:
    venv_path = venv_path.resolve()
    if venv_path.exists():
        verbose_print(t("venv_exists", path=venv_path))
    else:
        verbose_print(t("creating_venv", path=venv_path))
        python_exe = str(qgis.python_exe)
        run_logged([python_exe, "-m", "venv", "--system-site-packages", str(venv_path)], verbose_print)

    verbose_print(t("writing_pth"))
    _link_qgis_python(qgis, venv_path)

    if platform.system() == "Windows":
        _write_sitecustomize(qgis, venv_path)
        _patch_pyvenv_cfg(qgis, venv_path)

    return venv_path


def _site_packages_dir(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Lib" / "site-packages"
    # The venv is created by the QGIS-bundled interpreter, whose minor version
    # can differ from the one running devbridge (typical on macOS), so look at
    # what the venv actually contains before falling back to our own version.
    existing = sorted((venv_path / "lib").glob("python3*/site-packages"))
    if existing:
        return existing[-1]
    major, minor = sys.version_info[:2]
    return venv_path / "lib" / f"python{major}.{minor}" / "site-packages"


def _link_qgis_python(qgis: QgisInstallation, venv_path: Path) -> None:
    site_packages = _site_packages_dir(venv_path)
    site_packages.mkdir(parents=True, exist_ok=True)
    pth_file = site_packages / "qgis.pth"
    lines = []
    if qgis.qgis_python_dir:
        lines.append(str(qgis.qgis_python_dir))
    if qgis.plugins_dir:
        lines.append(str(qgis.plugins_dir))
    pth_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_sitecustomize(qgis: QgisInstallation, venv_path: Path) -> None:
    """Windows only: make native Qt/GDAL DLLs loadable from inside the venv
    (mirrors the community-documented os.add_dll_directory() workaround)."""
    site_packages = _site_packages_dir(venv_path)
    lines = [
        "import os",
        "",
    ]
    for bin_dir in qgis.bin_dirs:
        escaped = str(bin_dir).replace("\\", "/")
        lines.append(f'if os.path.isdir(r"{bin_dir}"):')
        lines.append(f'    os.add_dll_directory(r"{bin_dir}")')
    (site_packages / "sitecustomize.py").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_pyvenv_cfg(qgis: QgisInstallation, venv_path: Path) -> None:
    """Point pyvenv.cfg's `home` at the QGIS-bundled Python so the venv
    resolves the same interpreter/version QGIS itself runs on."""
    cfg_path = venv_path / "pyvenv.cfg"
    if not cfg_path.exists():
        return
    python_dir = qgis.python_exe.parent
    text = cfg_path.read_text(encoding="utf-8")
    out_lines = []
    for line in text.splitlines():
        if line.lower().startswith("home ="):
            out_lines.append(f"home = {python_dir}")
        else:
            out_lines.append(line)
    cfg_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
