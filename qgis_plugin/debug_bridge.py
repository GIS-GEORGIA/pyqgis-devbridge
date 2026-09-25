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

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5678


class DebugBridgeError(RuntimeError):
    pass


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
        try:
            import debugpy
        except ImportError as exc:
            raise DebugBridgeError("debugpy_missing") from exc

        # debugpy.listen() is idempotent-safe to call once per process;
        # QGIS plugin reload during development can call start() again,
        # so we track our own flag rather than relying on debugpy's state.
        debugpy.listen((self.host, self.port))
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
