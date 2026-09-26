"""Install the DevBridge QGIS plugin (``qgis_plugin/`` in this repo) into the
user's QGIS profile(s) and switch it on, so no manual copying/ticking in
the Plugin Manager is needed.

The plugin is linked (symlink / Windows junction) rather than copied by
default, so edits in the repo are live in QGIS; ``copy=True`` falls back
to a plain copy.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from . import profiles

PLUGIN_NAME = "DevBridge"


def plugin_source() -> Path | None:
    """``qgis_plugin/`` next to ``src/`` — only present in a repo clone
    (editable install), not in a wheel."""
    candidate = Path(__file__).resolve().parents[2] / "qgis_plugin"
    return candidate if (candidate / "metadata.txt").exists() else None


def profile_dirs(profile: str | None = None) -> list[Path]:
    """Existing QGIS profile folders to install into: the ``default``
    profile of each QGIS major version, or the named one."""
    wanted = profile or "default"
    return [
        root / wanted
        for root in profiles.profile_roots()
        if (root / wanted).is_dir()
    ]


def _make_link(source: Path, target: Path) -> None:
    if platform.system() == "Windows":
        # Junctions need no admin rights / developer mode, unlike symlinks.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(source, target, target_is_directory=True)


def _remove(target: Path) -> None:
    """Remove a link/junction without touching what it points at; only
    a real directory is deleted recursively."""
    try:
        os.unlink(target)
        return
    except (OSError, PermissionError):
        pass
    try:
        os.rmdir(target)          # junction, or an empty directory
        return
    except OSError:
        pass
    shutil.rmtree(target)


def install(source: Path, plugins_dir: Path, copy: bool = False, force: bool = False) -> str:
    """Returns ``linked`` | ``copied`` | ``already`` | ``exists``."""
    plugins_dir.mkdir(parents=True, exist_ok=True)
    target = plugins_dir / PLUGIN_NAME

    if target.exists() or target.is_symlink():
        if not copy and target.resolve() == source.resolve():
            return "already"
        if not force:
            return "exists"
        _remove(target)

    if not copy:
        try:
            _make_link(source, target)
            return "linked"
        except (OSError, subprocess.CalledProcessError):
            pass  # fall through to a plain copy
    shutil.copytree(
        source, target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return "copied"


def set_plugin_enabled(ini: Path, name: str = PLUGIN_NAME) -> None:
    """Set ``[PythonPlugins] <name>=true`` in a QGIS ini, editing lines in
    place so the rest of the file is left exactly as QGIS wrote it."""
    with open(ini, encoding="utf-8", newline="") as f:  # newline="" keeps CRLF visible
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    entry = f"{name}=true"

    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "[PythonPlugins]")
    except StopIteration:
        lines += ["", "[PythonPlugins]", entry]
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
        for i in range(start + 1, end):
            if lines[i].split("=", 1)[0].strip() == name:
                lines[i] = entry
                break
        else:
            lines.insert(start + 1, entry)
    with open(ini, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(lines) + nl)


def find_ini(profile_dir: Path) -> Path | None:
    for name in ("QGIS3.ini", "QGIS4.ini"):
        ini = profile_dir / "QGIS" / name
        if ini.exists():
            return ini
    return None


def qgis_running() -> bool:
    """QGIS rewrites its ini on exit, so editing it while it runs is lost."""
    try:
        if platform.system() == "Windows":
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, timeout=15).stdout
            return any(ln.lower().startswith('"qgis') for ln in out.splitlines())
        return subprocess.run(["pgrep", "-ix", "qgis.*"],
                              capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
