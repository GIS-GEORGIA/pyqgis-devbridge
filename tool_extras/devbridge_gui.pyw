"""Double-click (Windows) or run `python3 devbridge_gui.pyw` to open the
DevBridge desktop tool. Needs Python 3.9+ with Tk (tkinter); nothing else.
დააწკაპუნეთ ორჯერ (Windows) ან გაუშვით `python3 devbridge_gui.pyw`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from devbridge.gui import launch  # noqa: E402

launch()
