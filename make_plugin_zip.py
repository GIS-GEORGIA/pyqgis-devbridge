#!/usr/bin/env python3
"""Build dist/DevBridge.zip — the file for plugins.qgis.ge / the QGIS plugin manager.

Layout inside the zip (the root folder name must equal the ZIP name and the
plugin id, or QGIS cannot match an installed copy to the repository entry):

    DevBridge/                 <- qgis_plugin/ (metadata.txt, plugin.py, ui/, i18n/, ...)
    DevBridge/tool/devbridge/  <- copy of src/devbridge (the standalone CLI + Tk GUI)
    DevBridge/tool/devbridge_gui.pyw, README.txt   <- from tool_extras/
    DevBridge/LICENSE

The plugin never imports from src/ at run time: it only sees the copy under
tool/, so a plugin installed from this zip is fully self-contained.

    python make_plugin_zip.py              # -> dist/DevBridge.zip
    python make_plugin_zip.py --out DIR    # write somewhere else
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "DevBridge"
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv"}
SKIP_EXTS = {".pyc", ".pyo"}

# Pinned so the same sources always give the same bytes (matches qgis-plugins-repo/tools/build.py).
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _files(base: Path):
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if path.is_file() and not (set(rel.parts) & SKIP_DIRS) and path.suffix not in SKIP_EXTS:
            yield path, rel


def collect() -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    entries += [(p, f"{NAME}/{r.as_posix()}") for p, r in _files(ROOT / "qgis_plugin")]
    entries += [(p, f"{NAME}/tool/devbridge/{r.as_posix()}") for p, r in _files(ROOT / "src" / "devbridge")]
    entries += [(p, f"{NAME}/tool/{r.as_posix()}") for p, r in _files(ROOT / "tool_extras")]
    entries.append((ROOT / "LICENSE", f"{NAME}/LICENSE"))
    return sorted(entries, key=lambda e: e[1])


def build(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{NAME}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in collect():
            info = zipfile.ZipInfo(arcname, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes().replace(b"\r\n", b"\n") if path.suffix in
                        {".py", ".pyw", ".json", ".txt", ".md"} else path.read_bytes())
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "dist"), help="output directory")
    args = parser.parse_args()
    target = build(Path(args.out))
    with zipfile.ZipFile(target) as zf:
        print(f"{target}  ({target.stat().st_size // 1024} KiB, {len(zf.namelist())} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
