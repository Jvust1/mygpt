"""The installed scikit-learn oracle must run without network access."""
import socket
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("Lexical oracle must not use network")
    for method in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, method, denied)
