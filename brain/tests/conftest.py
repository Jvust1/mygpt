"""No outbound network in tests. AF_UNIX loop wakeups remain usable.

This detects accidental Python network activity, not a hardened OS sandbox.
The production prototype itself still exposes no live provider selection.
"""
import os
import socket
import pytest


@pytest.fixture(autouse=True)
def no_outbound_network(monkeypatch):
    attempts = []

    def guard(original):
        def checked(sock, *args, **kwargs):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                attempts.append(original.__name__)
                raise AssertionError("Network use is prohibited in offline Brain tests")
            return original(sock, *args, **kwargs)
        return checked

    for name in ("connect", "connect_ex", "sendto", "bind", "listen"):
        monkeypatch.setattr(socket.socket, name, guard(getattr(socket.socket, name)))
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    yield
    assert not attempts, "Network attempt occurred even if a library swallowed its exception"


def pytest_report_teststatus(report, config):
    if os.environ.get("MYGPT_STRICT_SDK_TESTS") == "1" and report.skipped:
        # The acceptance runner additionally checks JUnit and rejects skipped tests.
        return "skipped", "s", "SDK ACCEPTANCE BLOCKED: skip is not a pass"
