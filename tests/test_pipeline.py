"""pipeline.py's port-conflict handling in run_setup (the rest of run_setup
needs a real QGIS to build a venv against, so it's only exercised
indirectly through the CLI tests, with run_setup itself monkeypatched)."""
from __future__ import annotations

import socket

import pytest

from devbridge import pipeline


def test_resolve_port_keeps_a_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        free_port = s.getsockname()[1]
    assert pipeline._resolve_port("localhost", free_port, log=lambda _m: None) == free_port


def test_resolve_port_switches_to_a_free_one_when_busy():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
        s.listen(1)
        msgs = []
        alt = pipeline._resolve_port("localhost", port, log=msgs.append)
        assert alt != port
        assert any(str(port) in m and str(alt) in m for m in msgs)


def test_resolve_port_raises_when_nothing_free_nearby(monkeypatch):
    monkeypatch.setattr(pipeline, "port_free", lambda host, port: False)
    monkeypatch.setattr(pipeline, "find_free_port", lambda host, start, tries=20: None)
    with pytest.raises(pipeline.SetupError):
        pipeline._resolve_port("localhost", 5678, log=lambda _m: None)


def test_warn_if_remote_host_is_silent_for_localhost():
    msgs = []
    pipeline._warn_if_remote_host("localhost", 5678, log=msgs.append)
    assert msgs == []


def test_warn_if_remote_host_warns_for_a_real_address():
    msgs = []
    pipeline._warn_if_remote_host("0.0.0.0", 5678, log=msgs.append)
    assert len(msgs) == 1 and "0.0.0.0" in msgs[0] and "5678" in msgs[0]
