"""pm5keys: turn a rowing workout description into the Concept2 PM5
button-press sequence.

See docs/SPEC.md for the WorkoutSpec schema and docs/PM5_KEYS.md for
the PM5 button-press notation.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .compile_keys import compile, explain
from .keyseq import canonical, expand
from .pm5_model import run
from .spec import parse_spec, validate_spec

__all__ = [
    "__version__",
    "compile",
    "explain",
    "parse_spec",
    "validate_spec",
    "expand",
    "canonical",
    "run",
]
