"""Adds the repo root to sys.path so qgis_plugin/ (not part of the
pip-installed `devbridge` package) can be imported directly in tests.
Only pure modules without `qgis.*` imports (debug_bridge.py,
pycharm_bridge.py) are safe to import this way outside a real QGIS
process — plugin.py and ui/ are excluded from test collection for that
reason.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Tests never read or write the user's real DevBridge settings and always start in English
    (the developer's machine may well be set to Georgian)."""
    monkeypatch.setenv("DEVBRIDGE_CONFIG", str(tmp_path / "devbridge-config.json"))
    monkeypatch.setenv("DEVBRIDGE_LANG", "en")
    from devbridge.i18n_util import set_lang
    set_lang("en")
    yield
    set_lang("en")
