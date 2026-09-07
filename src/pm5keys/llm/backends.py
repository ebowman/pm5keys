#!/usr/bin/env python3
"""Pluggable backends for the LLM fallback extractor.

A Backend is anything with a `complete(prompt, model)` method that
returns the raw text response for a single-turn completion. Three
backends are provided:

- ClaudeCliBackend: shells out to the `claude` CLI (the pre-existing
  wod/llm_extract.py subprocess path). The binary is resolved from the
  PM5KEYS_CLAUDE_BIN environment variable, else `shutil.which('claude')`.
  There is no hardcoded fallback path (the old wod/llm_extract.py's
  LEGACY_CLAUDE_PATH is gone) -- if neither resolves, ExtractError is
  raised.
- AnthropicBackend: calls the Anthropic Messages API directly via the
  `anthropic` package (an optional dependency, `pip install
  pm5keys[llm]`). The API key comes from the ANTHROPIC_API_KEY
  environment variable.
- NoneBackend: always raises ExtractError('LLM disabled'). Used when
  the caller explicitly disables the LLM fallback.

resolve_backend(name) maps a backend name ('auto', 'none', 'anthropic',
'claude-cli') to a Backend instance. 'auto' prefers AnthropicBackend
(if the anthropic SDK imports AND ANTHROPIC_API_KEY is set), then
ClaudeCliBackend (if the claude binary resolves), else NoneBackend.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from typing import Protocol

# Default model for AnthropicBackend. Current Anthropic model ids carry no
# date suffix; 'claude-opus-5' is the documented default and
# 'claude-sonnet-5' the current cheaper option (override with --model).
# Current models reject the temperature parameter, so it is not sent.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"

CLAUDE_TIMEOUT_S = 120

# Where the ClaudeCliBackend runs the subprocess from. wod/llm_extract.py
# ran it from the repo root so that any relative paths inside the
# claude CLI's own tool use resolved sensibly; pm5keys has no
# equivalent requirement, so the current working directory is used.


class ExtractError(Exception):
    """Raised when a backend cannot produce a completion."""


class Backend(Protocol):
    def complete(self, prompt: str, model: str | None) -> str:
        """Return the raw text response for a single-turn completion of
        `prompt`. Raises ExtractError on any backend-level failure
        (missing binary/SDK/key, subprocess failure, timeout, malformed
        response, etc.)."""
        ...


class ClaudeCliBackend:
    """Invokes the `claude` CLI as a subprocess:
    `claude -p --model <model> --output-format json` with the prompt on
    stdin, and returns the JSON envelope's `result` text.

    The binary path is resolved once per call (never cached across
    calls) via PM5KEYS_CLAUDE_BIN, else shutil.which('claude'). No
    hardcoded home-directory fallback path is used.
    """

    name = "claude-cli"

    def __init__(self, claude_path: str | None = None):
        self._claude_path = claude_path

    def _resolve_path(self) -> str:
        if self._claude_path:
            return self._claude_path

        env_path = os.environ.get("PM5KEYS_CLAUDE_BIN")
        if env_path:
            return env_path

        which_path = shutil.which("claude")
        if which_path:
            return which_path

        raise ExtractError("claude CLI not found: set PM5KEYS_CLAUDE_BIN or put 'claude' on PATH")

    def complete(self, prompt: str, model: str | None) -> str:
        claude_path = self._resolve_path()
        model_arg = model or "sonnet"
        cmd = [claude_path, "-p", "--model", model_arg, "--output-format", "json"]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractError(f"claude CLI timed out after {CLAUDE_TIMEOUT_S}s") from exc
        except OSError as exc:
            raise ExtractError(f"failed to launch claude CLI: {exc}") from exc

        if proc.returncode != 0:
            raise ExtractError(
                f"claude CLI exited with code {proc.returncode}: {proc.stderr.strip()}"
            )

        import json

        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ExtractError(f"claude CLI output is not valid JSON: {exc}") from exc

        if not isinstance(envelope, dict):
            raise ExtractError("claude CLI output envelope is not a JSON object")

        if envelope.get("is_error"):
            message = envelope.get("result") or envelope.get("error") or "unknown error"
            raise ExtractError(f"claude CLI reported is_error=true: {message}")

        result = envelope.get("result")
        if not isinstance(result, str):
            raise ExtractError("claude CLI output envelope missing string 'result'")

        return result


_ANTHROPIC_SYSTEM_PROMPT = (
    "You convert rowing workout descriptions to JSON specs. Answer with JSON only."
)


class AnthropicBackend:
    """Calls the Anthropic Messages API directly via the `anthropic`
    Python SDK (an optional dependency: `pip install pm5keys[llm]`).

    The `anthropic` package is imported lazily inside __init__ so that
    importing this module never requires the optional dependency to be
    installed. If the import fails, ExtractError('install
    pm5keys[llm]') is raised. The API key is read from the
    ANTHROPIC_API_KEY environment variable; if unset, ExtractError is
    raised naming ANTHROPIC_API_KEY.
    """

    name = "anthropic"

    def __init__(self):
        try:
            import anthropic
        except ImportError as exc:
            raise ExtractError("install pm5keys[llm]") from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ExtractError("ANTHROPIC_API_KEY is not set; export it or use --llm claude-cli")

        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, prompt: str, model: str | None) -> str:
        model_id = model or DEFAULT_ANTHROPIC_MODEL
        try:
            response = self._client.messages.create(
                model=model_id,
                max_tokens=1024,
                system=_ANTHROPIC_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ExtractError(f"anthropic API call failed: {exc}") from exc

        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text

        raise ExtractError("anthropic API response contained no text block")


class NoneBackend:
    """Always raises ExtractError('LLM disabled'). Used when the LLM
    fallback is explicitly disabled (--llm none / --no-llm)."""

    name = "none"

    def complete(self, prompt: str, model: str | None) -> str:
        raise ExtractError("LLM disabled")


def _anthropic_available() -> bool:
    """True iff the anthropic SDK imports AND ANTHROPIC_API_KEY is set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        importlib.import_module("anthropic")
    except ImportError:
        return False
    return True


def _claude_cli_available() -> bool:
    if os.environ.get("PM5KEYS_CLAUDE_BIN"):
        return True
    return shutil.which("claude") is not None


def resolve_backend(name: str = "auto") -> Backend:
    """Resolve a backend name to a Backend instance.

    - 'none': NoneBackend.
    - 'anthropic': AnthropicBackend (raises ExtractError if the SDK or
      key is unavailable).
    - 'claude-cli': ClaudeCliBackend (does not validate the binary
      eagerly -- resolution happens lazily on first complete() call).
    - 'auto': AnthropicBackend if the anthropic SDK imports AND
      ANTHROPIC_API_KEY is set; else ClaudeCliBackend if the claude
      binary resolves (PM5KEYS_CLAUDE_BIN or PATH); else NoneBackend.

    Raises ExtractError for an unrecognized name.
    """
    if name == "none":
        return NoneBackend()
    if name == "anthropic":
        return AnthropicBackend()
    if name == "claude-cli":
        return ClaudeCliBackend()
    if name == "auto":
        if _anthropic_available():
            return AnthropicBackend()
        if _claude_cli_available():
            return ClaudeCliBackend()
        return NoneBackend()

    raise ExtractError(
        f"unknown backend {name!r}: expected one of auto, none, anthropic, claude-cli"
    )
