"""Find and start the standalone DevBridge tool from inside QGIS.

The tool (the `devbridge` package: CLI + Tk GUI) travels inside the plugin
as ``<plugin>/tool/devbridge``. When the plugin is a link to a repo clone
(development), it falls back to the repo's ``src/devbridge``.

No qgis.* imports: everything here is plain Python and unit-testable.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# resolve() so a junction/symlink into a repo clone finds the repo, not the profile
_PLUGIN_DIR = Path(__file__).resolve().parent
_gui_python_cache: list[str] | None = None


class ToolMissingError(RuntimeError):
    """The bundled tool could not be found."""


class NoTkError(RuntimeError):
    """No Python with tkinter was found to run the desktop GUI."""


def tool_dir() -> Path | None:
    """Folder that contains the ``devbridge`` package (put it on sys.path / PYTHONPATH)."""
    for base in (_PLUGIN_DIR / "tool", _PLUGIN_DIR.parent / "src"):
        if (base / "devbridge" / "__init__.py").exists():
            return base
    return None


def folder_to_open() -> Path | None:
    """What the 'Open tool folder' button shows: the tool folder with the
    launcher script in it (or the repo root when linked to a clone)."""
    base = tool_dir()
    if base is None:
        return None
    return base.parent if base.name == "src" else base


def ensure_importable() -> Path:
    base = tool_dir()
    if base is None:
        raise ToolMissingError("tool_missing")
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    return base


def guess_qgis_root(prefix_path: str) -> Path | None:
    """`<root>/apps/qgis-ltr` (Windows installers) -> `<root>`."""
    p = Path(prefix_path)
    return p.parents[1] if p.parent.name == "apps" else None


def scrubbed_env(extra_pythonpath: Path | None = None) -> dict:
    """Environment for a *different* Python: QGIS's own PYTHONHOME/PYTHONPATH
    would make it load the wrong standard library."""
    env = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONEXECUTABLE"):
        env.pop(key, None)
    if extra_pythonpath is not None:
        env["PYTHONPATH"] = str(extra_pythonpath)
    return env


def _candidates() -> list[list[str]]:
    if platform.system() == "Windows":
        found = [["py", "-3"], ["python"], ["python3"]]
    else:
        found = [["python3"], ["python"]]
    # QGIS's own interpreter (OSGeo4W layout: <root>/apps/Python3xx/python.exe)
    own = Path(sys.exec_prefix) / ("python.exe" if platform.system() == "Windows" else "bin/python3")
    if own.exists():
        found.append([str(own)])
    return found


def find_gui_python(force: bool = False) -> list[str]:
    """First interpreter that can `import tkinter`, as an argv prefix."""
    global _gui_python_cache
    if _gui_python_cache is not None and not force:
        return _gui_python_cache

    probe = "import tkinter, sys; print(sys.executable)"
    for cand in _candidates():
        exe = shutil.which(cand[0])
        if not exe:
            continue
        try:
            out = subprocess.run([exe, *cand[1:], "-c", probe], capture_output=True, text=True,
                                 timeout=30, env=scrubbed_env())
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode != 0 or not out.stdout.strip():
            continue
        real = Path(out.stdout.strip().splitlines()[-1])
        if platform.system() == "Windows":
            windowless = real.with_name("pythonw.exe")   # no console flash
            if windowless.exists():
                real = windowless
        _gui_python_cache = [str(real)]
        return _gui_python_cache
    raise NoTkError("no_tk")


def launch_gui() -> subprocess.Popen:
    """Start the standalone GUI as an independent process."""
    base = tool_dir()
    if base is None:
        raise ToolMissingError("tool_missing")
    argv = [*find_gui_python(), "-m", "devbridge", "gui"]
    flags = 0
    if platform.system() == "Windows":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen(argv, env=scrubbed_env(base), cwd=str(base), creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_in_vscode(path: Path) -> bool:
    names = ["code.cmd", "code"] if platform.system() == "Windows" else ["code"]
    code = next((w for w in map(shutil.which, names) if w), None)
    if not code:
        return False
    subprocess.Popen([code, str(path)], shell=platform.system() == "Windows",
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def run_setup(project_dir: Path, port: int, lang: str, log, qgis_prefix_path: str | None = None) -> None:
    """Prepare `project_dir` for debugging, in this (QGIS) process, using the
    bundled tool. Blocking — call it from a worker thread."""
    ensure_importable()
    if qgis_prefix_path and not os.environ.get("OSGEO4W_ROOT"):
        root = guess_qgis_root(qgis_prefix_path)
        if root is not None:
            os.environ["OSGEO4W_ROOT"] = str(root)   # lets the detector find this exact install
    from devbridge import i18n_util, pipeline   # noqa: PLC0415 - bundled, path added above
    i18n_util.set_lang(lang)
    pipeline.run_setup(Path(project_dir), port=port, log=log)
