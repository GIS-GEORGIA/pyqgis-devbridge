"""Settings shared between the standalone tool, the CLI and the DevBridge
QGIS plugin, stored as one small JSON file so a value changed in one place
shows up in the others.

`qgis_plugin/shared_config.py` reads/writes the same file. The plugin can't
import this package (it is installed as a standalone folder), so that file
is a deliberate copy of `config_path()` / `load()` / `save()`;
tests/test_shared_config.py keeps the two in step.
"""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path

DEFAULTS: dict = {
    "lang": None,            # "en" | "ka" | None (= follow the system)
    "host": "localhost",     # VS Code (debugpy) bridge
    "port": 5678,
    "pycharm_host": "localhost",
    "pycharm_port": 12345,
}


def config_path() -> Path:
    override = os.environ.get("DEVBRIDGE_CONFIG")
    if override:
        return Path(override)
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "DevBridge" / "config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "DevBridge" / "config.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "devbridge" / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(data, dict):
        cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    return cfg


def save(cfg: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
