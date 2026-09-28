"""`devbridge doctor` - one command that checks the whole chain end to end and
prints a clear OK/FAIL line (+ a one-line hint on failure) for each piece,
instead of the user guessing which of the many moving parts (QGIS install,
venv, debugpy, the DevBridge plugin, .vscode/) is the broken one.

Plain ASCII markers ([OK]/[FAIL]/[--]), not unicode glyphs: this has to be
readable on a plain cp1252 Windows console too.
"""
from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import bridge_plugin, pipeline, project_config, vscode_config
from .detectors.base import QgisInstallation
from .i18n_util import t
from .netutil import port_free as _port_free


@dataclass
class Check:
    label: str
    ok: bool | None          # True/False, or None = skipped (not applicable here)
    hint: str = field(default="")


def _no_window_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def _try_import(interpreter: Path, module: str, timeout: int) -> bool:
    try:
        out = subprocess.run(
            [str(interpreter), "-c", f"import {module}"],
            capture_output=True, timeout=timeout, creationflags=_no_window_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0


def _qgis_python_wrapper(qgis: QgisInstallation) -> Path | None:
    """The `python-qgis[-<edition>].bat` next to a Windows install: it sets up
    PYTHONPATH/PATH/QGIS_PREFIX_PATH the same way QGIS itself would before
    running Python, so `import qgis.core` behaves exactly as it would inside
    a real QGIS session - reconstructing that environment by hand (PATH,
    PYTHONPATH, os.add_dll_directory per bin dir) was tried first and still
    left "DLL load failed" on a real OSGeo4W install; this wrapper script
    just works, first try."""
    if qgis.qgis_python_dir is None:
        return None
    edition = qgis.qgis_python_dir.parent.name       # "qgis" or "qgis-ltr"
    candidate = qgis.root / "bin" / f"python-{edition}.bat"
    return candidate if candidate.exists() else None


def _python_can_import(python_exe: Path, module: str, timeout: int = 45,
                       qgis: QgisInstallation | None = None) -> bool:
    """A bare `python -c "import ..."` is enough for a venv (env_builder
    already prepares qgis.pth + a DLL-directory sitecustomize.py for it).
    A QGIS-bundled interpreter run directly generally is not - use its own
    python-qgis.bat wrapper for that case, when there is one."""
    if platform.system() == "Windows" and qgis is not None:
        wrapper = _qgis_python_wrapper(qgis)
        if wrapper is not None:
            return _try_import(wrapper, module, timeout)
    return _try_import(python_exe, module, timeout)


def _plugin_enabled_anywhere() -> bool | None:
    """True if enabled in at least one profile, False if installed but
    nowhere enabled, None if not installed into any profile at all."""
    targets = bridge_plugin.profile_dirs()
    if not targets:
        return None
    found_any_install = False
    for prof in targets:
        if not (prof / "python" / "plugins" / bridge_plugin.PLUGIN_NAME).exists():
            continue
        found_any_install = True
        ini = bridge_plugin.find_ini(prof)
        if ini and bridge_plugin.is_plugin_enabled(ini):
            return True
    return False if found_any_install else None


def _vscode_has_attach_config(project_dir: Path) -> bool:
    launch_json = project_dir / ".vscode" / "launch.json"
    if not launch_json.exists():
        return False
    try:
        data = json.loads(launch_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    names = {c.get("name") for c in data.get("configurations", []) if isinstance(c, dict)}
    return vscode_config.ATTACH_NAME in names


def run_checks(project_dir: Path | None = None, port: int | None = None,
               qgis: QgisInstallation | None = None,
               log: Callable[[str], None] = lambda _m: None) -> list[Check]:
    """Runs every check it can; never raises. `log` receives progress notes
    for slow steps (the import checks each start a real interpreter)."""
    checks: list[Check] = []

    installs = pipeline.find_all_qgis(log=log)
    if not installs:
        checks.append(Check(t("doctor_qgis_found"), False, t("doctor_qgis_found_hint")))
    else:
        qgis = qgis or installs[0]
        checks.append(Check(t("doctor_qgis_found"), True, str(qgis.root)))
        if len(installs) > 1:
            checks.append(Check(t("doctor_qgis_multiple", count=len(installs)), None,
                                ", ".join(str(q.root) for q in installs)))

        log(t("doctor_checking_import"))
        ok = _python_can_import(qgis.python_exe, "qgis.core", qgis=qgis)
        checks.append(Check(t("doctor_qgis_import"), ok, "" if ok else t("doctor_qgis_import_hint")))

        ok = _python_can_import(qgis.python_exe, "debugpy", timeout=15)
        checks.append(Check(t("doctor_debugpy_qgis"), ok, "" if ok else t("doctor_debugpy_qgis_hint")))

    enabled = _plugin_enabled_anywhere()
    if enabled is None:
        checks.append(Check(t("doctor_plugin_installed"), False, t("doctor_plugin_not_installed_hint")))
    else:
        checks.append(Check(t("doctor_plugin_enabled"), enabled,
                            "" if enabled else t("doctor_plugin_not_enabled_hint")))

    port = port if port is not None else vscode_config.DEFAULT_PORT
    free = _port_free("localhost", port)
    checks.append(Check(t("doctor_port_free", port=port), free, "" if free else t("doctor_port_busy_hint")))

    if project_dir is not None:
        project_dir = Path(project_dir).resolve()
        venv_python = pipeline.venv_python(project_dir / ".venv")
        if venv_python.exists():
            log(t("doctor_checking_import"))
            ok = _python_can_import(venv_python, "qgis.core")
            checks.append(Check(t("doctor_venv_import"), ok, "" if ok else t("doctor_venv_import_hint")))
            ok = _python_can_import(venv_python, "debugpy", timeout=15)
            checks.append(Check(t("doctor_debugpy_venv"), ok, "" if ok else t("doctor_debugpy_venv_hint")))
        else:
            checks.append(Check(t("doctor_venv_import"), False, t("doctor_no_venv_hint")))

        has_cfg = (project_dir / project_config.CONFIG_NAME).exists()
        checks.append(Check(t("doctor_devbridge_json"), has_cfg,
                            "" if has_cfg else t("doctor_no_devbridge_json_hint")))

        has_attach = _vscode_has_attach_config(project_dir)
        checks.append(Check(t("doctor_vscode_config"), has_attach,
                            "" if has_attach else t("doctor_no_vscode_hint")))

    return checks


def print_report(checks: list[Check], log: Callable[[str], None] = print) -> bool:
    """Prints every check, returns True iff nothing failed (skipped checks
    don't count against it)."""
    all_ok = True
    for c in checks:
        marker = "[--]" if c.ok is None else ("[OK]  " if c.ok else "[FAIL]")
        log(f"{marker} {c.label}")
        if c.hint:
            log(f"       {c.hint}")
        if c.ok is False:
            all_ok = False
    log(t("doctor_all_ok") if all_ok else t("doctor_some_failed"))
    return all_ok
