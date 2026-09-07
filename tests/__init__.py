"""Test package for pm5keys.

Guards the whole suite against accidental network access: `socket.socket`
is patched at import time to raise, so any test that tries to open a
real socket (e.g. an unmocked HTTP/API call) fails loudly instead of
hanging or silently reaching the network. Tests that exercise backends
(pm5keys.llm) must mock every call that would otherwise reach a real
subprocess or HTTP client.
"""

from __future__ import annotations

import socket


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        raise AssertionError(
            "network access attempted during tests: socket.socket() is "
            "blocked by tests/__init__.py -- mock the backend instead"
        )


socket.socket = _BlockedSocket
