"""Shared socket helpers used by doctor, setup's port-conflict handling and
launch's port warning."""
from __future__ import annotations

import socket

from devbridge import netutil


def test_port_free_true_then_false_while_bound():
    assert netutil.port_free("localhost", 0) is True          # port 0: always bindable
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
        s.listen(1)
        assert netutil.port_free("localhost", port) is False
    assert netutil.port_free("localhost", port) is True        # released after the socket closes


def test_find_free_port_returns_the_requested_port_when_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        free_port = s.getsockname()[1]
    assert netutil.find_free_port("localhost", free_port) == free_port


def test_find_free_port_skips_busy_ports():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        busy = s.getsockname()[1]
        s.listen(1)
        found = netutil.find_free_port("localhost", busy)
        assert found is not None and found != busy


def test_find_free_port_gives_up_after_tries(monkeypatch):
    monkeypatch.setattr(netutil, "port_free", lambda host, port: False)
    assert netutil.find_free_port("localhost", 12345, tries=3) is None
