#!/usr/bin/env python3
"""Parser/formatter for Concept2 PM5 button-press notation.

Concept2's Workout-of-the-Day pages describe how to program a workout into
the PM5 monitor using a compact sequence notation such as::

    B-2D-5A-2B-E

A sequence is a list of tokens joined by '-'. Each token is an optional
positive integer *count* followed by exactly one uppercase letter A-E
(e.g. "4A" means "press the A button four times in succession"; a count
of 1 is written with no leading number, i.e. plain "A").

Legend (quoted verbatim from Concept2's WOD page): Starting from the Main
Menu, "A" corresponds to the top gray button on the right, "B"
corresponds to the second gray button on the right, and so on down
through "E". Note: 4A, for example, means press the A button four times
in succession.

Canonicalisation note: expanding a sequence to individual key presses and
then re-compressing it merges adjacent tokens for the same letter, e.g.
"2B-B" canonicalises to "3B". This is intentional: "2B" followed by "B"
is physically identical to three consecutive presses of B, so the two
notations are equivalent and collapse to the same canonical form.

See docs/PM5_KEYS.md for the full grammar, the physical button layout,
and worked examples.
"""

from __future__ import annotations

import re
import sys

# A single token: an optional count (one or more digits, no sign) followed
# by exactly one uppercase letter A-E. Anchored so re.match against a
# token-shaped string cannot match a substring or trailing garbage.
TOKEN_RE = re.compile(r"^(\d+)?([A-E])$")


def _describe_token(token: str, index: int) -> str:
    return f"invalid token {token!r} at position {index}"


def validate(seq: str) -> None:
    """Validate a PM5 key sequence string.

    Raises ValueError, naming the offending token and its 0-based index
    among '-'-separated tokens, if the sequence is invalid. A sequence is
    invalid if it is empty, contains whitespace anywhere, contains an
    empty token (from a leading/trailing/doubled '-'), or contains a
    token that is not [count]LETTER with LETTER in A-E and count (if
    present) a positive integer with no leading '+' or '-'.
    """
    if seq == "":
        raise ValueError("empty sequence")

    if any(ch.isspace() for ch in seq):
        raise ValueError(f"sequence contains whitespace: {seq!r}")

    tokens = seq.split("-")
    for index, token in enumerate(tokens):
        if token == "":
            raise ValueError(_describe_token(token, index))

        match = TOKEN_RE.match(token)
        if not match:
            raise ValueError(_describe_token(token, index))

        count_str = match.group(1)
        if count_str is not None and int(count_str) < 1:
            raise ValueError(_describe_token(token, index))


def expand(seq: str) -> list[str]:
    """Expand a PM5 key sequence string into a flat list of single-letter
    presses, e.g. "2B-B" -> ["B", "B", "B"]. Raises ValueError (via
    validate) on an invalid sequence.
    """
    validate(seq)

    presses: list[str] = []
    for token in seq.split("-"):
        match = TOKEN_RE.match(token)
        count_str, letter = match.group(1), match.group(2)
        count = int(count_str) if count_str is not None else 1
        presses.extend([letter] * count)
    return presses


def compress(presses: list[str]) -> str:
    """Compress a flat list of single-letter presses into canonical PM5
    key sequence notation, merging adjacent runs of the same letter into
    "<n><letter>" tokens (n omitted when 1). Returns '' for an empty
    list. Raises ValueError if any element is not a single uppercase
    letter A-E.
    """
    for press in presses:
        if not isinstance(press, str) or press not in "ABCDE" or len(press) != 1:
            raise ValueError(f"invalid press {press!r}: must be a single letter A-E")

    if not presses:
        return ""

    tokens: list[str] = []
    current_letter = presses[0]
    run_length = 1
    for press in presses[1:]:
        if press == current_letter:
            run_length += 1
        else:
            tokens.append(current_letter if run_length == 1 else f"{run_length}{current_letter}")
            current_letter = press
            run_length = 1
    tokens.append(current_letter if run_length == 1 else f"{run_length}{current_letter}")

    return "-".join(tokens)


def canonical(seq: str) -> str:
    """Return the canonical form of a PM5 key sequence string: equivalent
    to compress(expand(seq)). Raises ValueError on an invalid sequence.
    """
    return compress(expand(seq))


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 keyseq.py <sequence>", file=sys.stderr)
        return 1

    try:
        presses = expand(argv[1])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for i, press in enumerate(presses, start=1):
        print(f"{i}: {press}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
