"""Optional LLM fallback for pm5keys: turns free-form RowErg workout
text into a WorkoutSpec dict when pm5keys.spec's rule parser can't.

This subpackage is only imported when the rule parser fails and the
LLM fallback hasn't been disabled; it depends on the optional `llm`
extra (`pip install pm5keys[llm]`) only for the AnthropicBackend path
-- the ClaudeCliBackend and NoneBackend backends have no extra
dependencies.
"""

from __future__ import annotations

from .backends import ExtractError, resolve_backend
from .extract import extract_spec

__all__ = ["ExtractError", "extract_spec", "resolve_backend"]
