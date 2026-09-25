"""Write .vscode/settings.json + launch.json wired for:
  1. Editing with the venv interpreter (autocomplete for qgis/PyQt).
  2. Attaching to a debugpy server started from inside a running QGIS
     session (via the companion QGIS DevBridge plugin), on DEFAULT_PORT.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

from .i18n_util import t

DEFAULT_PORT = 5678


def write_vscode_config(project_dir: Path, venv_path: Path, port: int = DEFAULT_PORT,
                         verbose_print=print) -> None:
    verbose_print(t("writing_vscode"))
    vscode_dir = project_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Windows":
        interpreter = venv_path / "Scripts" / "python.exe"
    else:
        interpreter = venv_path / "bin" / "python"

    settings = {
        "python.defaultInterpreterPath": str(interpreter),
        "python.terminal.activateEnvironment": True,
    }
    (vscode_dir / "settings.json").write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    launch = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "PyQGIS: Attach to running QGIS",
                "type": "debugpy",
                "request": "attach",
                "connect": {"host": "localhost", "port": port},
                "justMyCode": False,
            }
        ],
    }
    (vscode_dir / "launch.json").write_text(
        json.dumps(launch, indent=2, ensure_ascii=False), encoding="utf-8"
    )
