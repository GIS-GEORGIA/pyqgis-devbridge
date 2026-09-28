""".devbridge.json - the small, portable contract written by `devbridge setup`
and read by `devbridge launch`. Holds no absolute paths, so it is safe to
commit alongside the plugin/project it describes.

Machine-specific values (interpreter paths) belong in the generated
`.vscode/` files instead, never here.
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_NAME = ".devbridge.json"
SCHEMA_VERSION = 1

DEFAULTS = {
    "schemaVersion": SCHEMA_VERSION,
    "host": "localhost",
    "port": 5678,
    "pluginName": None,
    "venvName": ".venv",
}


def _valid_port(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535


def read_project_config(project_dir: Path) -> dict:
    """Never raises: a missing file, invalid JSON or bad fields fall back to defaults."""
    config = dict(DEFAULTS)
    path = Path(project_dir) / CONFIG_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config
    if not isinstance(data, dict):
        return config
    if isinstance(data.get("host"), str) and data["host"].strip():
        config["host"] = data["host"].strip()
    if _valid_port(data.get("port")):
        config["port"] = data["port"]
    if isinstance(data.get("pluginName"), str) and data["pluginName"].strip():
        config["pluginName"] = data["pluginName"].strip()
    if isinstance(data.get("venvName"), str) and data["venvName"].strip():
        config["venvName"] = data["venvName"].strip()
    return config


def write_project_config(project_dir: Path, *, host: str, port: int,
                         plugin_name: str | None, venv_name: str) -> Path:
    path = Path(project_dir) / CONFIG_NAME
    data = {
        "schemaVersion": SCHEMA_VERSION,
        "host": host,
        "port": port,
        "pluginName": plugin_name or None,
        "venvName": venv_name,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
