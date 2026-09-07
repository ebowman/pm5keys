#!/usr/bin/env python3
"""End-to-end tool: a free-form RowErg workout description in, the
Concept2 email-style PM5 press text out.

Scope: RowErg only. There is no --machine flag -- the machine is
always forced to 'rower' regardless of what pm5keys.spec's rule parser
or the LLM extractor infer (BikeErg parentheticals in the input text
are ignored, since parse_spec is always called with machines=None, and
the LLM extractor always forces machine='rower' internally).

Pipeline:
    spec = spec.parse_spec(text, None)
    if spec is None and not --no-llm:
        spec = llm.extract_spec(text, model=...)
    spec['machine'] = 'rower'
    keys = compile_keys.compile(spec)

The LLM fallback (pm5keys.llm) is an optional extra (`pip install
pm5keys[llm]`) and is imported lazily, only when the rule parser fails
and --no-llm was not given. If the llm subpackage is not installed, or
the configured backend is unavailable, this prints an install hint and
exits 2.

CLI:
    pm5keys "<text>" [--no-llm] [--explain] [--verbose] [--model sonnet]
        With no positional argument, the workout text is read from
        stdin. Prints exactly two lines to stdout:

            <title line>
            PM5: <keys>

        where <title line> is the input text's first line, whitespace-
        normalised and truncated to 80 characters. With --verbose, the
        parsed spec (as JSON) and its source ('rules' or 'llm') are
        printed to stderr. With --explain, one line per press (from
        pm5_model/compile_keys explain()) is printed after the two
        lines, formatted '<press>  <screen>: <action>' in aligned
        columns; consecutive presses that share the same press letter
        and screen, and whose actions differ only in the trailing
        '(now N)' digit-edit value or the cursor-move destination
        field, are collapsed to '<n>x<press>' (showing the last
        action's destination/value). --version prints pm5keys's
        version and exits 0.

Exit codes: 0 on success. 2, with a one-line message on stderr and no
traceback, when: the text is empty; parse_spec returns None and
--no-llm was given ('unparsed: use without --no-llm to try the LLM');
the llm extra is not installed or its backend is unavailable when the
LLM fallback is needed ('unparsed: rules could not parse this text;
install pm5keys[llm] or use --llm claude-cli for free-form
descriptions'); the LLM extractor raises ExtractError (its message is
printed); or compile_keys.compile raises ValueError/NotImplementedError
(its message is printed).
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from . import compile_keys
from . import pm5_model as pm5
from .spec import parse_spec
from . import __version__


class Wod2KeysError(Exception):
    """Raised for any user-facing failure in run(); the CLI catches
    this and prints exc's message (no traceback) with exit code 2."""


def _normalise_title(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    normalised = " ".join(first_line.split())
    return normalised[:80]


def run(text: str, use_llm: bool = True, model: str = "sonnet", extract_fn=None) -> dict:
    """Run the full text -> spec -> keys pipeline. Returns a dict with
    keys: title, keys, spec, source ('rules' or 'llm'), explain (list
    of (press, screen, action) tuples). Raises Wod2KeysError on any
    user-facing failure (empty input, unparsed text with LLM disabled,
    LLM extraction failure, or compile failure) with a one-line
    message suitable for printing to the user.

    extract_fn, if given, replaces the LLM extractor's extract_spec
    (for offline testing); it is called as extract_fn(text, model=model).
    """
    if not text or not text.strip():
        raise Wod2KeysError("empty input")

    spec = parse_spec(text, None)
    source = "rules"

    if spec is None:
        if not use_llm:
            raise Wod2KeysError("unparsed: use without --no-llm to try the LLM")

        if extract_fn is not None:
            fn = extract_fn
            extract_error_types = (Exception,)
        else:
            try:
                from .llm import extract_spec as fn, ExtractError
            except ImportError:
                raise Wod2KeysError(
                    "unparsed: rules could not parse this text; install "
                    "pm5keys[llm] or use --llm claude-cli for free-form "
                    "descriptions"
                )
            extract_error_types = (ExtractError,)

        try:
            spec = fn(text, model=model)
        except extract_error_types as exc:
            raise Wod2KeysError(str(exc)) from exc
        source = "llm"

    spec = dict(spec)
    spec["machine"] = "rower"

    try:
        keys = compile_keys.compile(spec)
    except (ValueError, NotImplementedError) as exc:
        raise Wod2KeysError(str(exc)) from exc

    explain_trace = pm5.explain(keys)

    return {
        "title": _normalise_title(text),
        "keys": keys,
        "spec": spec,
        "source": source,
        "explain": explain_trace,
    }


# Matches a trailing '... +N (now V)' or '... -N (now V)' digit-edit
# action, capturing the field-name prefix before ' +'/' -', the sign,
# the per-press delta magnitude, and the resulting value.
_DIGIT_EDIT_RE = re.compile(r"^(.*) ([+-])(\d+) \(now (\d+)\)$")
# Matches a 'cursor left/right to <field>' cursor-move action, capturing
# the fixed 'cursor left/right to' prefix (the direction, not the
# destination field).
_CURSOR_MOVE_RE = re.compile(r"^(cursor (?:left|right) to) .+$")


def _action_group_key(action: str):
    """Return a key such that two actions collapse together iff they
    are the same press repeated on the same screen and differ only in
    the trailing '(now N)' value (digit edits) or the cursor
    destination field (cursor moves); otherwise the action itself is
    the key, so unrelated actions never collapse."""
    m = _DIGIT_EDIT_RE.match(action)
    if m:
        return ("digit_edit", m.group(1), m.group(2))
    m = _CURSOR_MOVE_RE.match(action)
    if m:
        return ("cursor_move", m.group(1))
    return ("other", action)


def _format_explain(trace: list) -> list:
    """Format an explain() trace (list of (press, screen, action)) into
    display lines, collapsing consecutive presses that share the same
    press letter and screen, and whose actions differ only in the
    trailing '(now N)' digit-edit value or the cursor-move destination
    field, into '<n>x<press>  <screen>: <action>'. For a collapsed
    cursor-move group, the *last* press's destination field is shown
    (that's where the cursor ends up); for a collapsed digit-edit
    group, the delta is the sum of the group's per-press deltas (e.g.
    two consecutive '+1' presses collapse to '+2') and the value shown
    is the *last* press's resulting value. Other consecutive identical
    (press, screen, action) triples also collapse under the same rule.
    Column-aligns the press and screen fields using ': ' as the
    separator."""
    groups = []
    for press, screen, action in trace:
        key = (press, screen, _action_group_key(action))
        if groups and groups[-1][0] == key:
            groups[-1][1].append(action)
        else:
            groups.append([key, [action]])

    labels = []
    for key, actions in groups:
        press, screen, group_key = key
        count = len(actions)
        label = press if count == 1 else f"{count}x{press}"
        last_action = actions[-1]
        if group_key[0] == "digit_edit" and count > 1:
            field, sign, _delta, _value = _DIGIT_EDIT_RE.match(last_action).groups()
            total_delta = sum(
                int(_DIGIT_EDIT_RE.match(a).group(3)) for a in actions
            )
            final_value = _DIGIT_EDIT_RE.match(last_action).group(4)
            action = f"{field} {sign}{total_delta} (now {final_value})"
        else:
            action = last_action
        labels.append((label, screen, action))

    if not labels:
        return []

    label_width = max(len(label) for label, _, _ in labels)
    screen_width = max(len(screen) for _, screen, _ in labels)

    lines = []
    for label, screen, action in labels:
        lines.append(f"{label.ljust(label_width)}  {screen.ljust(screen_width)}: {action}")
    return lines


def _read_stdin_text() -> str:
    return sys.stdin.read()


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        prog="pm5keys",
        description="Turn a free-form RowErg workout description into PM5 button presses.",
    )
    parser.add_argument("text", nargs="?", default=None, help="workout description (else read from stdin)")
    parser.add_argument("--no-llm", action="store_true", help="do not fall back to the LLM extractor")
    parser.add_argument("--explain", action="store_true", help="print a per-press explanation")
    parser.add_argument("--verbose", action="store_true", help="print spec JSON and source to stderr")
    parser.add_argument("--model", default="sonnet", help="LLM model to use (default: sonnet)")
    parser.add_argument("--version", action="version", version=f"pm5keys {__version__}")

    args = parser.parse_args(argv)

    text = args.text if args.text is not None else _read_stdin_text()

    try:
        result = run(text, use_llm=not args.no_llm, model=args.model)
    except Wod2KeysError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.verbose:
        print(json.dumps(result["spec"], indent=2), file=sys.stderr)
        print(f"source: {result['source']}", file=sys.stderr)

    print(result["title"])
    print(f"PM5: {result['keys']}")

    if args.explain:
        for line in _format_explain(result["explain"]):
            print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
