"""Self-contained i18n loader for the plugin package (does not depend on
the pyqgis-devbridge library being importable, since QGIS plugins are
copied as standalone folders into the user's profile)."""
from __future__ import annotations

import json
import os
from pathlib import Path

_I18N_DIR = Path(__file__).parent / "i18n"
_SUPPORTED = ("en", "ka")
_cache: dict[str, dict[str, str]] = {}
_current_lang = "en"


def _load(lang: str) -> dict[str, str]:
    if lang not in _cache:
        path = _I18N_DIR / f"{lang}.json"
        if not path.exists():
            path = _I18N_DIR / "en.json"
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def detect_system_lang() -> str:
    env = os.environ.get("DEVBRIDGE_LANG")
    if env and env[:2].lower() in _SUPPORTED:
        return env[:2].lower()
    try:
        from qgis.core import QgsApplication
        locale_str = QgsApplication.instance().locale()
        if locale_str and locale_str[:2].lower() == "ka":
            return "ka"
    except Exception:
        pass
    return "en"


def set_lang(lang: str) -> None:
    global _current_lang
    _current_lang = lang if lang in _SUPPORTED else "en"


def get_lang() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    strings = _load(_current_lang)
    template = strings.get(key) or _load("en").get(key, key)
    return template.format(**kwargs) if kwargs else template


set_lang(detect_system_lang())
