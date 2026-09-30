"""Real Pipecat tests may not open network connections or audio devices."""
import socket

import pytest


@pytest.fixture(autouse=True)
def no_internet(monkeypatch):
    attempts = []
    for name in ("connect", "connect_ex", "sendto", "bind", "listen"):
        original = getattr(socket.socket, name)
        def guarded(sock, *args, _original=original, **kwargs):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                attempts.append(_original.__name__)
                raise AssertionError("Realtime tests must not use network")
            return _original(sock, *args, **kwargs)
        monkeypatch.setattr(socket.socket, name, guarded)
    yield
    assert not attempts
