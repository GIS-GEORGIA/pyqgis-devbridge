"""Small socket helpers shared by `doctor`, `pipeline` (setup) and `launcher`
(launch), so all three agree on what "is this port free" means instead of
each probing it slightly differently.
"""
from __future__ import annotations

import socket

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def is_local_host(host: str) -> bool:
    """True for the usual "this machine only" spellings. Anything else - a
    real IP, `0.0.0.0`, a hostname - means the debug bridge's socket (which
    has no authentication of its own: debugpy and pydevd both just accept
    whoever connects) would be reachable from other machines too."""
    return (host or "").strip().lower() in _LOCAL_HOSTS


def port_free(host: str, port: int) -> bool:
    """True if a listening socket could be bound to `host:port` right now.
    Best-effort: the port can still be taken by someone else a moment
    later (TOCTOU), which is fine here - this is advisory, for messages,
    never a lock."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(host: str, start_port: int, tries: int = 20) -> int | None:
    """The first free port at or after `start_port`, checking at most
    `tries` of them; None if none of those were free."""
    for port in range(start_port, start_port + tries):
        if port_free(host, port):
            return port
    return None
