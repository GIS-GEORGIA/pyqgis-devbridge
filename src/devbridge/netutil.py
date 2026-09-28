"""Small socket helpers shared by `doctor`, `pipeline` (setup) and `launcher`
(launch), so all three agree on what "is this port free" means instead of
each probing it slightly differently.
"""
from __future__ import annotations

import socket


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
