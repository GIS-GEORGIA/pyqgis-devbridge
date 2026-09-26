"""Auto-detects an installed PyCharm build, resolves and installs the
matching `pydevd-pycharm` package into a folder of its own (using QGIS's
Python, found from its prefix — inside QGIS `sys.executable` is the QGIS
program, not Python), and connects to a PyCharm "Python Debug Server" run configuration — removing
the three manual steps documented in docs/*/usage.md and
.pycharm-debug/README.*.md (which remain as a fallback for setups this
can't detect: portable/unzipped PyCharm builds, offline machines, etc.).

Kept free of `qgis.*` imports, same as debug_bridge.py, so it is
independently unit-testable and reusable from the QGIS Python console.

Connection direction is the *reverse* of the debugpy/VS Code bridge:
PyCharm's "Python Debug Server" run configuration is the listening
server; QGIS (via pydevd_pycharm.settrace) is the client that connects
out to it. The PyCharm-side run configuration must already be running
before start()/auto_configure_and_start() is called.
"""
from __future__ import annotations

import json
import os
import platform
import importlib
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PYCHARM_HOST = "localhost"
DEFAULT_PYCHARM_PORT = 12345

_PYPI_RELEASES_URL = "https://pypi.org/pypi/pydevd-pycharm/json"


class PyCharmBridgeError(RuntimeError):
    """`str(exc)` is one of: already_running, not_found, pydevd_missing,
    connection_refused, not_running, or "pypi_unreachable: <detail>"."""


@dataclass
class PyCharmInstallation:
    path: Path
    build: str            # e.g. "233.13135.95" (matches pydevd-pycharm's own versioning)
    product: str           # "PY" (Professional) or "PC" (Community)
    display_name: str      # e.g. "PyCharm 2023.3.2 (Professional)"


# ---------------------------------------------------------------------------
# 1. Detection — fully offline, filesystem only
# ---------------------------------------------------------------------------

def _candidate_dirs() -> list[Path]:
    system = platform.system()
    candidates: list[Path] = []
    home = Path.home()

    if system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        for base in (local / "Programs", program_files, program_files_x86):
            candidates.extend(base.glob("PyCharm*"))
        candidates.extend((local / "JetBrains" / "Toolbox" / "apps").glob("PyCharm-*/ch-0/*"))

    elif system == "Linux":
        candidates.extend(Path("/opt").glob("pycharm*"))
        candidates.extend(Path("/usr/share").glob("pycharm*"))
        candidates.extend((home / ".local/share/JetBrains/Toolbox/apps").glob("PyCharm-*/ch-0/*"))
        candidates.extend(Path("/snap").glob("pycharm*/current"))

    elif system == "Darwin":
        candidates.extend(Path("/Applications").glob("PyCharm*.app/Contents"))
        candidates.extend((home / "Applications").glob("PyCharm*.app/Contents"))
        candidates.extend(
            (home / "Library/Application Support/JetBrains/Toolbox/apps").glob("PyCharm-*/ch-0/*")
        )

    return [c for c in candidates if c.exists()]


def _read_build_file(install_dir: Path) -> str | None:
    for name in ("build.txt", "Resources/build.txt"):
        f = install_dir / name
        if f.exists():
            try:
                return f.read_text(encoding="utf-8").strip()
            except OSError:
                return None
    return None


def _read_product_info(install_dir: Path) -> dict | None:
    for name in ("product-info.json", "Resources/product-info.json"):
        f = install_dir / name
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
    return None


def find_pycharm_installations() -> list[PyCharmInstallation]:
    """Newest build first."""
    results: list[PyCharmInstallation] = []
    for install_dir in _candidate_dirs():
        raw_build = _read_build_file(install_dir)
        if not raw_build:
            continue
        match = re.match(r"([A-Z]{2})-(\d+(?:\.\d+)*)", raw_build)
        if not match:
            continue
        product, build = match.group(1), match.group(2)

        info = _read_product_info(install_dir)
        version_label = info.get("version", build) if info else build
        product_name = "Professional" if product == "PY" else "Community"

        results.append(PyCharmInstallation(
            path=install_dir,
            build=build,
            product=product,
            display_name=f"PyCharm {version_label} ({product_name})",
        ))

    def _sort_key(inst: PyCharmInstallation) -> tuple:
        try:
            return tuple(int(p) for p in inst.build.split("."))
        except ValueError:
            return (-1,)

    results.sort(key=_sort_key, reverse=True)
    return results


# ---------------------------------------------------------------------------
# 2. Resolve + install the matching pydevd-pycharm version
# ---------------------------------------------------------------------------

def _available_pydevd_versions() -> list[str]:
    try:
        with urllib.request.urlopen(_PYPI_RELEASES_URL, timeout=10) as resp:
            data = json.load(resp)
    except Exception as exc:
        raise PyCharmBridgeError(f"pypi_unreachable: {exc}") from exc
    return list(data.get("releases", {}).keys())


def resolve_pydevd_version(build: str) -> str:
    """pydevd-pycharm releases are versioned to match PyCharm build
    numbers almost exactly. Try an exact match first, then fall back to
    the closest earlier release sharing the same major (year) component,
    since IDE patch releases don't always get a matching pydevd upload."""
    versions = _available_pydevd_versions()
    if build in versions:
        return build

    def _key(v: str) -> tuple:
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (-1,)

    target = _key(build)
    same_major = [v for v in versions if _key(v)[:1] == target[:1]]
    pool = same_major or versions
    older_or_equal = [v for v in pool if _key(v) <= target]
    if older_or_equal:
        return max(older_or_equal, key=_key)
    if pool:
        return min(pool, key=_key)
    raise PyCharmBridgeError("no_pydevd_versions_found")


def _other_debugger_loaded() -> bool:
    try:
        from .debugger_state import active_backend
    except ImportError:                      # imported as a top-level module
        from debugger_state import active_backend
    return active_backend() == "debugpy"


def default_install_dir() -> Path:
    """Where pydevd-pycharm is installed: next to the shared DevBridge settings,
    always writable, independent of QGIS's own (often read-only) site-packages."""
    try:
        from .shared_config import config_path
    except ImportError:                      # imported as a top-level module
        from shared_config import config_path
    return config_path().parent / "pydevd"


def _no_window() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def _python_version_of(exe: Path) -> str | None:
    try:
        out = subprocess.run(
            [str(exe), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=20, creationflags=_no_window(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def find_python_executable() -> str:
    """A real `python` matching the interpreter QGIS embeds.

    Inside QGIS, `sys.executable` is the QGIS program itself (`qgis-bin.exe`,
    `/usr/bin/qgis`, the .app binary), so `sys.executable -m pip` would start
    another QGIS. Derive the interpreter from the prefix instead."""
    major, minor = sys.version_info[:2]
    want = f"{major}.{minor}"
    exe = Path(sys.executable)

    candidates: list[Path] = []
    if exe.name.lower().startswith("python"):          # console / python-qgis.bat
        candidates.append(exe)
    for prefix in dict.fromkeys((sys.exec_prefix, sys.base_exec_prefix)):
        base = Path(prefix)
        if platform.system() == "Windows":
            candidates.append(base / "python.exe")
        else:
            candidates += [base / "bin" / f"python{want}", base / "bin" / "python3", base / "bin" / "python"]
    candidates += [exe.parent / "bin" / "python3", exe.parent / "python3"]       # macOS .app layouts
    for name in (f"python{want}", "python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for cand in dict.fromkeys(candidates):
        if cand.exists() and _python_version_of(cand) == want:
            return str(cand)
    raise PyCharmBridgeError("python_not_found")


def _installed_pydevd_version(target: Path | None = None) -> str | None:
    """Version in our own folder first, then anywhere Python can already see it."""
    if target is not None:
        for dist in sorted(target.glob("pydevd_pycharm-*.dist-info")):
            return dist.name[len("pydevd_pycharm-"):-len(".dist-info")]
    try:
        from importlib import metadata
        return metadata.version("pydevd-pycharm")
    except Exception:
        return None


def _ensure_on_path(target: Path) -> None:
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
    importlib.invalidate_caches()


def install_pydevd_pycharm(python_exe: str, version: str, target: Path, verbose_print=print) -> None:
    """`pip install --target <target>`: needs no rights on QGIS's own folders.
    The folder is ours alone, so it is emptied first (clean switch between versions)."""
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    verbose_print(f"pip install pydevd-pycharm=={version} -> {target}")
    cmd = [python_exe, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
           "--target", str(target), f"pydevd-pycharm=={version}"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace", creationflags=_no_window())
    except OSError as exc:
        raise PyCharmBridgeError(f"pip_failed: {exc}") from exc
    tail: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        if line:
            tail.append(line)
            verbose_print(line)
    if proc.wait() != 0:
        raise PyCharmBridgeError("pip_failed: " + " | ".join(tail[-3:]))


# ---------------------------------------------------------------------------
# 3. Ready-to-run attach script (for reuse outside the live bridge, e.g.
#    pasted into a plugin's own debug entry point)
# ---------------------------------------------------------------------------

_SCRIPT_TEMPLATE = '''\
"""Auto-generated by DevBridge for {display_name} (build {build}).
Start PyCharm's "Python Debug Server" run configuration on {host}:{port}
first, then run this from the QGIS Python console (or your plugin's
debug entry point) to attach.
"""
import sys
{path_line}import pydevd_pycharm

pydevd_pycharm.settrace(
    "{host}",
    port={port},
    stdoutToServer=True,
    stderrToServer=True,
    suspend=False,
)
'''


def generate_bridge_script(installation: PyCharmInstallation, host: str, port: int,
                           install_dir: Path | None = None) -> str:
    path_line = f'sys.path.insert(0, r"{install_dir}")\n' if install_dir else ""
    return _SCRIPT_TEMPLATE.format(
        display_name=installation.display_name,
        build=installation.build,
        host=host,
        port=port,
        path_line=path_line,
    )


def write_bridge_script(installation: PyCharmInstallation, host: str, port: int,
                         target_dir: Path, install_dir: Path | None = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "pycharm_attach.py"
    out_path.write_text(generate_bridge_script(installation, host, port, install_dir), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# 4. High-level bridge object — mirrors debug_bridge.DebugBridge's
#    start()/stop()/is_running shape so plugin.py can treat both
#    uniformly, but automates detection + install + connect in one call.
# ---------------------------------------------------------------------------

class PyCharmBridge:
    def __init__(self, host: str = DEFAULT_PYCHARM_HOST, port: int = DEFAULT_PYCHARM_PORT,
                 install_dir: Path | None = None):
        self.host = host
        self.port = port
        self.install_dir = install_dir or default_install_dir()
        self._running = False
        self.installation: PyCharmInstallation | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def prepare(self, verbose_print=print) -> PyCharmInstallation:
        """Detect PyCharm and make the matching pydevd-pycharm importable.
        Slow (may pip-install) and does not touch the debugger, so it is safe
        to run on a worker thread; call `connect()` afterwards on the main thread."""
        if self._running:
            raise PyCharmBridgeError("already_running")
        if _other_debugger_loaded():
            raise PyCharmBridgeError("other_debugger_loaded")

        installations = find_pycharm_installations()
        if not installations:
            raise PyCharmBridgeError("not_found")
        installation = installations[0]

        installed = _installed_pydevd_version(self.install_dir)
        if installed != installation.build:
            version = resolve_pydevd_version(installation.build)  # may raise pypi_unreachable
            if installed != version:
                install_pydevd_pycharm(find_python_executable(), version, self.install_dir, verbose_print)
        _ensure_on_path(self.install_dir)
        return installation

    def auto_configure_and_start(self, verbose_print=print) -> PyCharmInstallation:
        installation = self.prepare(verbose_print)
        self.connect(installation)
        return installation

    def connect(self, installation: PyCharmInstallation) -> None:
        """Attach QGIS's main thread to the listening PyCharm debug server."""
        if self._running:
            raise PyCharmBridgeError("already_running")
        if _other_debugger_loaded():
            raise PyCharmBridgeError("other_debugger_loaded")
        try:
            import pydevd_pycharm
        except ImportError as exc:
            raise PyCharmBridgeError("pydevd_missing") from exc

        # Never call settrace() unless PyCharm is really listening: a failed settrace leaves
        # pydevd half-installed, and inside QGIS (Qt event loop) that kills the whole process.
        try:
            with socket.create_connection((self.host, self.port), timeout=3):
                pass
        except OSError as exc:
            raise PyCharmBridgeError("connection_refused") from exc

        try:
            pydevd_pycharm.settrace(
                self.host, port=self.port,
                stdoutToServer=True, stderrToServer=True, suspend=False,
            )
        except Exception as exc:
            try:
                pydevd_pycharm.stoptrace()      # undo whatever settrace() had already hooked
            except Exception:
                pass
            raise PyCharmBridgeError("connection_refused") from exc

        self._running = True
        self.installation = installation

    def stop(self) -> None:
        if not self._running:
            raise PyCharmBridgeError("not_running")
        try:
            import pydevd_pycharm
            pydevd_pycharm.stoptrace()
        except Exception:
            pass  # best effort - the flag below is what the UI relies on
        self._running = False
