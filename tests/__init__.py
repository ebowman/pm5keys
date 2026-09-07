"""Test package for pm5keys.

Guards the whole suite against accidental network access: `socket.socket`
is patched at import time to raise, so any test that tries to open a
real socket (e.g. an unmocked HTTP/API call) fails loudly instead of
hanging or silently reaching the network. Tests that exercise backends
(pm5keys.llm) must mock every call that would otherwise reach a real
subprocess or HTTP client.

Also guards against accidentally spawning a real `claude` CLI process:
`subprocess.run` and `subprocess.Popen` are patched at import time to
raise whenever argv[0]'s basename is 'claude', so a test that forgets
to mock ClaudeCliBackend.complete() fails loudly instead of shelling
out to (or hanging on) a real `claude` binary. This does not affect
`mock.patch("subprocess.run"/"subprocess.Popen", ...)` -- that replaces
the patched function/class entirely for the duration of the `with`
block, so the guard is simply not consulted for mocked calls. Tests
that must exercise this guard's target basename directly (e.g. to test
the guard itself) can opt out by calling
`tests._allow_subprocess_basename("claude")` as a context manager.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import threading


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        raise AssertionError(
            "network access attempted during tests: socket.socket() is "
            "blocked by tests/__init__.py -- mock the backend instead"
        )


socket.socket = _BlockedSocket


_BLOCKED_BASENAMES = frozenset({"claude"})
_allowed_basenames = threading.local()


def _current_allowed() -> frozenset:
    return getattr(_allowed_basenames, "names", frozenset())


@contextlib.contextmanager
def _allow_subprocess_basename(*basenames: str):
    """Temporarily allow spawning a process whose argv[0] basename is in
    `basenames`, for tests that need to exercise the guard itself or a
    real, sandboxed, non-`claude` subprocess. Not for use with `claude`
    outside of tests that specifically verify the guard's behaviour.
    """
    previous = _current_allowed()
    _allowed_basenames.names = previous | frozenset(basenames)
    try:
        yield
    finally:
        _allowed_basenames.names = previous


def _argv0_basename(args) -> str | None:
    if isinstance(args, (str, bytes, os.PathLike)):
        cmd = args
    else:
        try:
            cmd = args[0]
        except (IndexError, TypeError):
            return None
    if isinstance(cmd, bytes):
        cmd = cmd.decode("utf-8", errors="replace")
    return os.path.basename(str(cmd))


def _check_not_blocked(args) -> None:
    basename = _argv0_basename(args)
    if basename in _BLOCKED_BASENAMES and basename not in _current_allowed():
        raise AssertionError(
            f"subprocess spawn of {basename!r} attempted during tests: "
            "subprocess.run()/Popen() are blocked for this basename by "
            "tests/__init__.py -- mock subprocess.run/Popen (or the "
            "backend method that calls it) instead"
        )


_real_subprocess_run = subprocess.run
_real_subprocess_popen = subprocess.Popen


def _guarded_run(*args, **kwargs):
    if args:
        _check_not_blocked(args[0])
    else:
        _check_not_blocked(kwargs.get("args"))
    return _real_subprocess_run(*args, **kwargs)


class _GuardedPopen(_real_subprocess_popen):
    def __init__(self, args, *rest, **kwargs):
        _check_not_blocked(args)
        super().__init__(args, *rest, **kwargs)


subprocess.run = _guarded_run
subprocess.Popen = _GuardedPopen
