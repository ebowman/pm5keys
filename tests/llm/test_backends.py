# Run from repo root: python -m unittest discover -s tests -t .
#
# Fully offline: no test in this module opens a real subprocess, HTTP
# connection, or imports the real `anthropic` package unless it's
# already installed as an optional extra (in which case the client
# construction itself makes no network call).

import os
import sys
import types
import unittest
from unittest import mock

from pm5keys.llm import backends as be


def _fake_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return mock.Mock(stdout=stdout, stderr=stderr, returncode=returncode)


def _envelope(result_text: str, is_error: bool = False) -> str:
    import json

    return json.dumps({"result": result_text, "is_error": is_error})


class ClaudeCliBackendTest(unittest.TestCase):
    def test_env_var_wins_over_which(self):
        with mock.patch.dict(os.environ, {"PM5KEYS_CLAUDE_BIN": "/custom/claude"}):
            with mock.patch("shutil.which") as which_mock:
                backend = be.ClaudeCliBackend()
                self.assertEqual(backend._resolve_path(), "/custom/claude")
                which_mock.assert_not_called()

    def test_which_used_when_env_unset(self):
        env = dict(os.environ)
        env.pop("PM5KEYS_CLAUDE_BIN", None)
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("shutil.which", return_value="/usr/local/bin/claude") as which_mock:
                backend = be.ClaudeCliBackend()
                self.assertEqual(backend._resolve_path(), "/usr/local/bin/claude")
                which_mock.assert_called_once_with("claude")

    def test_raises_extract_error_when_nothing_found(self):
        env = dict(os.environ)
        env.pop("PM5KEYS_CLAUDE_BIN", None)
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("shutil.which", return_value=None):
                backend = be.ClaudeCliBackend()
                with self.assertRaises(be.ExtractError):
                    backend._resolve_path()

    def test_no_hardcoded_home_path_fallback(self):
        # There must be no legacy hardcoded path constant at all --
        # unlike wod/llm_extract.py's LEGACY_CLAUDE_PATH.
        self.assertFalse(hasattr(be, "LEGACY_CLAUDE_PATH"))

    def test_complete_invokes_subprocess_and_returns_result(self):
        backend = be.ClaudeCliBackend(claude_path="/fake/claude")
        good = _envelope('{"kind": "single_distance"}')
        with mock.patch("subprocess.run", return_value=_fake_completed(good)) as run_mock:
            result = backend.complete("some prompt", "sonnet")
        self.assertEqual(result, '{"kind": "single_distance"}')
        cmd = run_mock.call_args.args[0]
        self.assertEqual(
            cmd, ["/fake/claude", "-p", "--model", "sonnet", "--output-format", "json"]
        )
        self.assertEqual(run_mock.call_args.kwargs["input"], "some prompt")

    def test_complete_defaults_model_to_sonnet_when_none(self):
        backend = be.ClaudeCliBackend(claude_path="/fake/claude")
        good = _envelope("{}")
        with mock.patch("subprocess.run", return_value=_fake_completed(good)) as run_mock:
            backend.complete("prompt", None)
        cmd = run_mock.call_args.args[0]
        self.assertIn("sonnet", cmd)

    def test_complete_raises_on_nonzero_exit(self):
        backend = be.ClaudeCliBackend(claude_path="/fake/claude")
        with mock.patch(
            "subprocess.run", return_value=_fake_completed("", returncode=1, stderr="boom")
        ):
            with self.assertRaises(be.ExtractError):
                backend.complete("prompt", "sonnet")

    def test_complete_raises_on_timeout(self):
        import subprocess

        backend = be.ClaudeCliBackend(claude_path="/fake/claude")
        with mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120)
        ):
            with self.assertRaises(be.ExtractError):
                backend.complete("prompt", "sonnet")

    def test_complete_raises_on_malformed_json_envelope(self):
        backend = be.ClaudeCliBackend(claude_path="/fake/claude")
        with mock.patch("subprocess.run", return_value=_fake_completed("not json")):
            with self.assertRaises(be.ExtractError):
                backend.complete("prompt", "sonnet")

    def test_complete_raises_on_is_error_envelope(self):
        backend = be.ClaudeCliBackend(claude_path="/fake/claude")
        with mock.patch(
            "subprocess.run", return_value=_fake_completed(_envelope("bad", is_error=True))
        ):
            with self.assertRaises(be.ExtractError):
                backend.complete("prompt", "sonnet")


class NoneBackendTest(unittest.TestCase):
    def test_complete_always_raises_llm_disabled(self):
        backend = be.NoneBackend()
        with self.assertRaises(be.ExtractError) as ctx:
            backend.complete("prompt", "sonnet")
        self.assertIn("LLM disabled", str(ctx.exception))


def _install_fake_anthropic_module(create_side_effect=None, create_return=None):
    """Install a fake `anthropic` module into sys.modules and return it,
    so AnthropicBackend.__init__'s lazy `import anthropic` succeeds
    without the real SDK being installed."""
    fake_module = types.ModuleType("anthropic")

    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured["create_kwargs"] = kwargs
            if create_side_effect is not None:
                raise create_side_effect
            return create_return

    class FakeAnthropic:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key
            self.messages = FakeMessages()

    fake_module.Anthropic = FakeAnthropic
    fake_module._captured = captured
    return fake_module


class AnthropicBackendTest(unittest.TestCase):
    def test_import_error_raises_install_hint(self):
        # Ensure the real module (if present) is hidden so __init__
        # exercises the ImportError branch regardless of whether the
        # optional extra happens to be installed in this environment.
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            with self.assertRaises(be.ExtractError) as ctx:
                be.AnthropicBackend()
        self.assertIn("pm5keys[llm]", str(ctx.exception))

    def test_missing_api_key_raises_extract_error(self):
        fake_module = _install_fake_anthropic_module()
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(be.ExtractError) as ctx:
                    be.AnthropicBackend()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_complete_builds_request_and_returns_text_block(self):
        fake_response = mock.Mock()
        text_block = mock.Mock()
        text_block.type = "text"
        text_block.text = '{"kind": "single_distance"}'
        fake_response.content = [text_block]

        fake_module = _install_fake_anthropic_module(create_return=fake_response)
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                backend = be.AnthropicBackend()
                result = backend.complete("extract this workout", "claude-sonnet-x")

        self.assertEqual(result, '{"kind": "single_distance"}')
        self.assertEqual(fake_module._captured["api_key"], "sk-fake")
        kwargs = fake_module._captured["create_kwargs"]
        self.assertEqual(kwargs["model"], "claude-sonnet-x")
        self.assertEqual(kwargs["max_tokens"], 1024)
        self.assertNotIn("temperature", kwargs)
        self.assertIn("JSON only", kwargs["system"])
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "extract this workout"}])

    def test_complete_defaults_to_default_anthropic_model(self):
        fake_response = mock.Mock()
        text_block = mock.Mock()
        text_block.type = "text"
        text_block.text = "{}"
        fake_response.content = [text_block]

        fake_module = _install_fake_anthropic_module(create_return=fake_response)
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                backend = be.AnthropicBackend()
                backend.complete("prompt", None)

        kwargs = fake_module._captured["create_kwargs"]
        self.assertEqual(kwargs["model"], be.DEFAULT_ANTHROPIC_MODEL)

    def test_complete_raises_extract_error_on_sdk_exception(self):
        fake_module = _install_fake_anthropic_module(
            create_side_effect=RuntimeError("network down")
        )
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                backend = be.AnthropicBackend()
                with self.assertRaises(be.ExtractError):
                    backend.complete("prompt", "sonnet")

    def test_complete_raises_when_no_text_block(self):
        fake_response = mock.Mock()
        fake_response.content = []
        fake_module = _install_fake_anthropic_module(create_return=fake_response)
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                backend = be.AnthropicBackend()
                with self.assertRaises(be.ExtractError):
                    backend.complete("prompt", "sonnet")

    def test_sdk_missing_only_names_install_hint(self):
        # SDK unavailable, key present: message must name pm5keys[llm]
        # and must NOT also claim the key is missing.
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                with self.assertRaises(be.ExtractError) as ctx:
                    be.AnthropicBackend()
        message = str(ctx.exception)
        self.assertIn("pm5keys[llm]", message)
        self.assertNotIn("ANTHROPIC_API_KEY", message)

    def test_key_missing_only_names_env_var(self):
        # SDK available, key absent: message must name ANTHROPIC_API_KEY
        # and must NOT also claim the SDK is missing.
        fake_module = _install_fake_anthropic_module()
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(be.ExtractError) as ctx:
                    be.AnthropicBackend()
        message = str(ctx.exception)
        self.assertIn("ANTHROPIC_API_KEY", message)
        self.assertNotIn("pm5keys[llm]", message)

    def test_both_missing_names_both_prerequisites(self):
        # Neither the SDK nor the key is available: the single
        # ExtractError raised must name both prerequisites.
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(be.ExtractError) as ctx:
                    be.AnthropicBackend()
        message = str(ctx.exception)
        self.assertIn("pm5keys[llm]", message)
        self.assertIn("ANTHROPIC_API_KEY", message)


class ResolveBackendTest(unittest.TestCase):
    def test_none_returns_none_backend(self):
        self.assertIsInstance(be.resolve_backend("none"), be.NoneBackend)

    def test_claude_cli_returns_claude_cli_backend(self):
        self.assertIsInstance(be.resolve_backend("claude-cli"), be.ClaudeCliBackend)

    def test_anthropic_name_constructs_anthropic_backend(self):
        fake_module = _install_fake_anthropic_module()
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                backend = be.resolve_backend("anthropic")
        self.assertIsInstance(backend, be.AnthropicBackend)

    def test_unknown_name_raises(self):
        with self.assertRaises(be.ExtractError):
            be.resolve_backend("bogus")

    def test_auto_prefers_anthropic_when_sdk_and_key_available(self):
        fake_module = _install_fake_anthropic_module()
        with mock.patch.dict(sys.modules, {"anthropic": fake_module}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-fake"}):
                with mock.patch("shutil.which", return_value="/usr/local/bin/claude"):
                    backend = be.resolve_backend("auto")
        self.assertIsInstance(backend, be.AnthropicBackend)

    def test_auto_falls_back_to_claude_cli_when_no_key(self):
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("shutil.which", return_value="/usr/local/bin/claude"):
                backend = be.resolve_backend("auto")
        self.assertIsInstance(backend, be.ClaudeCliBackend)

    def test_auto_falls_back_to_claude_cli_when_sdk_missing(self):
        env = dict(os.environ)
        env["ANTHROPIC_API_KEY"] = "sk-fake"
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.dict(sys.modules, {"anthropic": None}):
                with mock.patch("shutil.which", return_value="/usr/local/bin/claude"):
                    backend = be.resolve_backend("auto")
        self.assertIsInstance(backend, be.ClaudeCliBackend)

    def test_auto_falls_back_to_none_backend_when_nothing_available(self):
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("PM5KEYS_CLAUDE_BIN", None)
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("shutil.which", return_value=None):
                backend = be.resolve_backend("auto")
        self.assertIsInstance(backend, be.NoneBackend)

    def test_auto_prefers_claude_cli_via_env_var_over_which(self):
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env["PM5KEYS_CLAUDE_BIN"] = "/custom/claude"
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("shutil.which", return_value=None):
                backend = be.resolve_backend("auto")
        self.assertIsInstance(backend, be.ClaudeCliBackend)


if __name__ == "__main__":
    unittest.main()
