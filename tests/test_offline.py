# Run from repo root: python -m unittest discover -s tests -t .

"""Exercises the offline guards installed by tests/__init__.py.

tests/__init__.py patches socket.socket, subprocess.run, and
subprocess.Popen at import time so the whole suite fails loudly instead
of reaching the network or spawning a real `claude` CLI process. This
module verifies those guards actually fire (and that a test can opt out
of the subprocess guard for a specific basename via
tests._allow_subprocess_basename, which this module uses on itself to
prove the opt-in works without needing a real `claude` binary on PATH).
"""

from __future__ import annotations

import socket
import subprocess
import unittest

import tests


class SocketGuardTest(unittest.TestCase):
    def test_socket_socket_raises(self):
        with self.assertRaises(AssertionError):
            socket.socket()


class SubprocessGuardTest(unittest.TestCase):
    def test_run_blocks_bare_claude_basename(self):
        with self.assertRaises(AssertionError):
            subprocess.run(["claude", "--version"])

    def test_run_blocks_claude_full_path(self):
        with self.assertRaises(AssertionError):
            subprocess.run(["/usr/local/bin/claude", "-p"])

    def test_run_blocks_via_args_kwarg(self):
        with self.assertRaises(AssertionError):
            subprocess.run(args=["claude"])

    def test_popen_blocks_claude_basename(self):
        with self.assertRaises(AssertionError):
            subprocess.Popen(["claude", "--version"])

    def test_run_does_not_block_other_basenames(self):
        # Any non-'claude' basename must pass straight through to the
        # real subprocess.run -- use a command guaranteed to exist and
        # exit immediately.
        proc = subprocess.run(
            ["python3", "-c", "print('ok')"], capture_output=True, text=True, check=True
        )
        self.assertEqual(proc.stdout.strip(), "ok")

    def test_opt_in_allows_the_blocked_basename_through(self):
        # Redirect the allowed 'claude' basename to a harmless python3
        # invocation shaped like argv[0] == '.../claude' via os.path
        # basename spoofing is unnecessary here -- what matters is that
        # _allow_subprocess_basename lifts the block for that basename
        # so the *real* subprocess.run is reached. We verify this by
        # confirming no AssertionError is raised and instead we get
        # whatever error the real OS gives for a nonexistent binary.
        with tests._allow_subprocess_basename("claude"):
            with self.assertRaises(FileNotFoundError):
                subprocess.run(["claude-does-not-exist-on-this-machine/claude"])

    def test_opt_in_is_scoped_to_the_with_block(self):
        with tests._allow_subprocess_basename("claude"):
            pass
        with self.assertRaises(AssertionError):
            subprocess.run(["claude"])


if __name__ == "__main__":
    unittest.main()
