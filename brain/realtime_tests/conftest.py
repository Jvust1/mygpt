"""Real Pipecat tests may use owned loopback HTTP, never external network."""
import socket

import pytest


@pytest.fixture(autouse=True)
def no_internet(monkeypatch):
    attempts = []
    for name in ("connect", "connect_ex", "sendto", "bind", "listen"):
        original = getattr(socket.socket, name)
        def guarded(sock, *args, _original=original, **kwargs):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                if _original.__name__ == "listen":
                    address = sock.getsockname()
                else:
                    address = args[1] if _original.__name__ == "sendto" and len(args) > 1 else args[0] if args else kwargs.get("address")
                if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                    return _original(sock, *args, **kwargs)
                attempts.append(_original.__name__)
                raise AssertionError("Realtime tests must not use network")
            return _original(sock, *args, **kwargs)
        monkeypatch.setattr(socket.socket, name, guarded)
    yield
    assert not attempts
