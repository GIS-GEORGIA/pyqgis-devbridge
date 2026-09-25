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
