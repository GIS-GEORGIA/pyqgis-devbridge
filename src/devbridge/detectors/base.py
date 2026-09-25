"""Shared data structure for a detected QGIS installation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class QgisInstallation:
    root: Path            # e.g. C:\OSGeo4W64  or  /usr
    python_exe: Path      # interpreter that can `import qgis`
    qgis_python_dir: Path | None = None   # site-packages-like dir holding `qgis`
    plugins_dir: Path | None = None       # .../apps/qgis/python/plugins (core plugins)
    bin_dirs: tuple[Path, ...] = ()       # dll/so search dirs to expose (Windows mainly)
    version_hint: str | None = None

    def as_dict(self) -> dict:
        return {
            "root": str(self.root),
            "python_exe": str(self.python_exe),
            "qgis_python_dir": str(self.qgis_python_dir) if self.qgis_python_dir else None,
            "plugins_dir": str(self.plugins_dir) if self.plugins_dir else None,
            "bin_dirs": [str(p) for p in self.bin_dirs],
            "version_hint": self.version_hint,
        }
