"""Settings file shared with the standalone DevBridge tool.

Deliberate copy of `src/devbridge/config.py` (this plugin ships as a
standalone folder and cannot import the pip package); the format, the
location and the defaults must stay identical —
tests/test_shared_config.py enforces that.
"""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path

DEFAULTS: dict = {
    "lang": None,
    "host": "localhost",
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
