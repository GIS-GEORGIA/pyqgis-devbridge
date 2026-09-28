"""Core debugpy bridge logic — deliberately UI-free so it's independently
testable and reusable from the QGIS Python console without loading the
plugin's menu integration.

    >>> from debug_bridge import DebugBridge
    >>> bridge = DebugBridge()
    >>> bridge.start()          # doctest: +SKIP
    >>> bridge.is_running
    True
"""
from __future__ import annotations

from .pyexe import PythonNotFoundError, find_python_executable

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5678


class DebugBridgeError(RuntimeError):
    """`str(exc)` is one of: already_running, debugpy_missing, python_not_found,
    other_debugger_loaded, not_running."""


def _active_backend() -> str | None:
    try:
        from .debugger_state import active_backend
    except ImportError:                      # imported as a top-level module
        from debugger_state import active_backend
    return active_backend()


class DebugBridge:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, wait_for_client: bool = False) -> None:
        if self._running:
            raise DebugBridgeError("already_running")
        if _active_backend() == "pycharm":
            raise DebugBridgeError("other_debugger_loaded")
        try:
            import debugpy
        except ImportError as exc:
            raise DebugBridgeError("debugpy_missing") from exc

        # Verified against a real QGIS (qgis-bin.exe --code): inside QGIS,
        # sys.executable is the QGIS program, not python. Without this,
        # debugpy.listen() spawns its background adapter through the QGIS
        # binary, which never starts it, and listen() fails ~20-30s later
        # with "timed out waiting for adapter to connect" - every time,
        # not just occasionally.
        try:
            debugpy.configure(python=find_python_executable())
        except PythonNotFoundError as exc:
            raise DebugBridgeError("python_not_found") from exc

        try:
            debugpy.listen((self.host, self.port))
        except ImportError as exc:            # a foreign pydevd got in first
            raise DebugBridgeError("other_debugger_loaded") from exc
        except RuntimeError as exc:
            # debugpy allows one listener per process. A plugin reload (common
            # while developing) creates a fresh DebugBridge whose own flag is
            # False while the old listener is still alive; debugpy then
            # refuses a second listen(). Documented behaviour, not directly
            # reproduced with a real reload in this session - treat it as
            # "already running" rather than crashing the reload.
            self._running = True
            raise DebugBridgeError("already_running") from exc
        if wait_for_client:
            debugpy.wait_for_client()
        self._running = True

    def stop(self) -> None:
        # debugpy has no public "stop listening" API; the socket lives for
        # the life of the QGIS process. We only flip our own bookkeeping
        # flag so the UI reflects reality and won't offer a second
        # `start()` that would raise. A genuine stop requires restarting
        # QGIS - this is documented in docs/*/usage.md.
        if not self._running:
            raise DebugBridgeError("not_running")
        self._running = False
