"""Auto-detects an installed PyCharm build, resolves and installs the
matching `pydevd-pycharm` package into QGIS's own interpreter, and
connects to a PyCharm "Python Debug Server" run configuration — removing
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
import re
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


def _installed_pydevd_version() -> str | None:
    try:
        from importlib import metadata
        return metadata.version("pydevd-pycharm")
    except Exception:
        return None


def install_pydevd_pycharm(python_exe: str, version: str, verbose_print=print) -> None:
    verbose_print(f"pip install pydevd-pycharm=={version} -> {python_exe}")
    subprocess.run(
        [python_exe, "-m", "pip", "install", f"pydevd-pycharm=={version}"],
        check=True,
    )


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
import pydevd_pycharm

pydevd_pycharm.settrace(
    "{host}",
    port={port},
    stdoutToServer=True,
    stderrToServer=True,
    suspend=False,
)
'''


def generate_bridge_script(installation: PyCharmInstallation, host: str, port: int) -> str:
    return _SCRIPT_TEMPLATE.format(
        display_name=installation.display_name,
        build=installation.build,
        host=host,
        port=port,
    )


def write_bridge_script(installation: PyCharmInstallation, host: str, port: int,
                         target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "pycharm_attach.py"
    out_path.write_text(generate_bridge_script(installation, host, port), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# 4. High-level bridge object — mirrors debug_bridge.DebugBridge's
#    start()/stop()/is_running shape so plugin.py can treat both
#    uniformly, but automates detection + install + connect in one call.
# ---------------------------------------------------------------------------

class PyCharmBridge:
    def __init__(self, host: str = DEFAULT_PYCHARM_HOST, port: int = DEFAULT_PYCHARM_PORT):
        self.host = host
        self.port = port
        self._running = False
        self.installation: PyCharmInstallation | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def auto_configure_and_start(self, verbose_print=print) -> PyCharmInstallation:
        if self._running:
            raise PyCharmBridgeError("already_running")

        installations = find_pycharm_installations()
        if not installations:
            raise PyCharmBridgeError("not_found")
        installation = installations[0]

        if _installed_pydevd_version() != installation.build:
            version = resolve_pydevd_version(installation.build)  # may raise pypi_unreachable
            install_pydevd_pycharm(sys.executable, version, verbose_print=verbose_print)

        try:
            import pydevd_pycharm
        except ImportError as exc:
            raise PyCharmBridgeError("pydevd_missing") from exc

        try:
            pydevd_pycharm.settrace(
                self.host, port=self.port,
                stdoutToServer=True, stderrToServer=True, suspend=False,
            )
        except (ConnectionRefusedError, OSError) as exc:
            raise PyCharmBridgeError("connection_refused") from exc

        self._running = True
        self.installation = installation
        return installation

    def stop(self) -> None:
        if not self._running:
            raise PyCharmBridgeError("not_running")
        try:
            import pydevd_pycharm
            pydevd_pycharm.stoptrace()
        except Exception:
            pass  # best effort - the flag below is what the UI relies on
        self._running = False
