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
from .i18n_util import t

PLUGIN_NAME = "DevBridge"


def plugin_source() -> Path | None:
    """The DevBridge plugin folder: ``qgis_plugin/`` in a repo clone
    (editable install), or the plugin itself when this package is the copy
    bundled in ``<plugin>/tool/devbridge``. Not available from a wheel."""
    top = Path(__file__).resolve().parents[2]
    for candidate in (top / "qgis_plugin", top):
        if (candidate / "metadata.txt").exists() and (candidate / "plugin.py").exists():
            return candidate
    return None


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


def install(source: Path, plugins_dir: Path, copy: bool = False, force: bool = False,
           name: str = PLUGIN_NAME) -> str:
    """Returns ``linked`` | ``copied`` | ``already`` | ``exists``. ``name`` is
    the target folder name under ``plugins_dir`` - defaults to DevBridge
    itself, but this is also what ``devbridge link-plugin`` uses for an
    arbitrary plugin folder."""
    plugins_dir.mkdir(parents=True, exist_ok=True)
    target = plugins_dir / name

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


def set_plugin_enabled(ini: Path, name: str = PLUGIN_NAME, enabled: bool = True) -> None:
    """Set ``[PythonPlugins] <name>=true`` (or ``=false`` with
    ``enabled=False``, used by ``devbridge uninstall``) in a QGIS ini,
    editing lines in place so the rest of the file is left exactly as QGIS
    wrote it."""
    with open(ini, encoding="utf-8", newline="") as f:  # newline="" keeps CRLF visible
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    entry = f"{name}={'true' if enabled else 'false'}"

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


def is_plugin_enabled(ini: Path, name: str = PLUGIN_NAME) -> bool | None:
    """None when the ini has no `[PythonPlugins] <name>=` entry at all -
    QGIS just hasn't recorded a choice yet, not necessarily "disabled"."""
    try:
        with open(ini, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "[PythonPlugins]")
    except StopIteration:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    for i in range(start + 1, end):
        key, _, value = lines[i].partition("=")
        if key.strip() == name:
            return value.strip().lower() in ("true", "1", "yes")
    return None


def find_ini(profile_dir: Path) -> Path | None:
    for name in ("QGIS3.ini", "QGIS4.ini"):
        ini = profile_dir / "QGIS" / name
        if ini.exists():
            return ini
    return None


def install_into_profiles(profile: str | None = None, copy: bool = False, force: bool = False,
                          log=print) -> int:
    """Install + enable DevBridge in each matching QGIS profile. Returns a
    process-style exit code (0 = everything fine)."""
    source = plugin_source()
    if source is None:
        log(t("bridge_source_missing"))
        return 1
    targets = profile_dirs(profile)
    if not targets:
        log(t("bridge_no_profile"))
        return 1

    status = 0
    running = qgis_running()
    for prof in targets:
        plugins_dir = prof / "python" / "plugins"
        result = install(source, plugins_dir, copy=copy, force=force)
        target = plugins_dir / PLUGIN_NAME
        if result == "exists":
            log(t("bridge_exists", target=target))
            status = 1
            continue
        log(t(f"bridge_{result}", target=target))

        ini = find_ini(prof)
        if ini is None:
            log(t("bridge_enable_no_ini", profile=prof))
        elif running:
            log(t("bridge_enable_skipped_running"))
        else:
            set_plugin_enabled(ini)
            log(t("bridge_enabled"))
    log(t("bridge_restart_hint"))
    return status


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
