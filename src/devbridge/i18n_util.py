"""Minimal i18n loader — no external dependencies.

Usage:
    from devbridge.i18n_util import t, set_lang
    set_lang("ka")
    print(t("welcome"))
"""
from __future__ import annotations

import json
import locale
import os
from pathlib import Path

_I18N_DIR = Path(__file__).parent / "i18n"
_SUPPORTED = ("en", "ka")
_current_lang = "en"
_cache: dict[str, dict[str, str]] = {}


def _load(lang: str) -> dict[str, str]:
    if lang not in _cache:
        path = _I18N_DIR / f"{lang}.json"
        if not path.exists():
            lang = "en"
            path = _I18N_DIR / "en.json"
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def detect_system_lang() -> str:
    """Best-effort detection: DEVBRIDGE_LANG env var, then system locale, else 'en'."""
    env = os.environ.get("DEVBRIDGE_LANG")
    if env and env[:2].lower() in _SUPPORTED:
        return env[:2].lower()
    try:
        sys_locale = locale.getlocale()[0] or locale.getdefaultlocale()[0]
    except Exception:
        sys_locale = None
    if sys_locale and sys_locale.lower().startswith("ka"):
        return "ka"
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
