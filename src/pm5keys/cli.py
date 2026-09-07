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
    if spec is None and --llm != 'none':
        spec = llm.extract_spec(text, backend=<resolved --llm backend>, model=...)
    spec['machine'] = 'rower'
    keys = compile_keys.compile(spec)

The LLM fallback (pm5keys.llm) is an optional extra (`pip install
pm5keys[llm]`) and is imported lazily, only when the rule parser fails
and the LLM fallback has not been disabled. If the llm subpackage is
not installed, or the configured backend is unavailable, this prints
an install hint and exits 2.

CLI:
    pm5keys "<text>" [--llm {auto,none,anthropic,claude-cli}] [--no-llm]
             [--explain] [--verbose] [--model MODEL]
             [--monitor {pm5,pm3,pm4,both}]
        With no positional argument, the workout text is read from
        stdin. --llm selects which backend the LLM fallback uses
        (default: auto, which prefers the Anthropic SDK+key, then the
        claude CLI, then disables the fallback -- see
        pm5keys.llm.backends.resolve_backend). --no-llm is an alias for
        --llm none. --model passes a model id/alias through to the
        resolved backend. --monitor selects the target monitor(s):
        'pm5' (default), 'pm3', 'pm4' (a spelling alias of 'pm3'), or
        'both'. Prints the title line followed by one key-sequence line
        per requested monitor:

            <title line>
            PM5: <keys>

        or, for --monitor pm3/pm4:

            <title line>
            PM3/PM4: <keys>

        or, for --monitor both (PM3/PM4 line first, then PM5, matching
        Concept2's own WOD emails):

            <title line>
            PM3/PM4: <keys>
            PM5: <keys>

        where <title line> is the input text's first line, whitespace-
        normalised and truncated to 80 characters. With --verbose, the
        parsed spec (as JSON) and its source ('rules' or 'llm') are
        printed to stderr. With --explain, one line per press (from
        pm5_model/compile_keys explain()) is printed after the key-
        sequence line(s), formatted '<press>  <screen>: <action>' in
        aligned columns; consecutive presses that share the same press
        letter and screen, and whose actions differ only in the
        trailing '(now N)' digit-edit value or the cursor-move
        destination field, are collapsed to '<n>x<press>' (showing the
        last action's destination/value). With --monitor both,
        --explain prints each monitor's trace under its own 'PM3/PM4:'
        / 'PM5:' heading. --version prints pm5keys's version and exits
        0.

    Calorie workouts ('single_calorie'/'intervals_calorie' specs) are
    not supported on PM3/PM4 (Concept2's PM3/PM4 monitors have no
    calorie workout screens at all). --monitor pm3/pm4 with a calorie
    workout exits 2 with compile_keys.compile's NotImplementedError
    message. --monitor both still succeeds: it prints the PM5 line
    normally and a 'PM3/PM4: not supported (calorie workouts)' line in
    place of a PM3/PM4 key sequence.

Exit codes: 0 on success. 2, with a one-line message on stderr and no
traceback, when: the text is empty; parse_spec returns None and --llm
none (or --no-llm) was given ('unparsed: use without --llm none to try
the LLM'); the resolved backend is unavailable (e.g. NoneBackend
because auto-detection found nothing, or the llm extra is not
installed) when the LLM fallback is needed ('unparsed: rules could not
parse this text; enable the LLM fallback with --llm anthropic (pip
install pm5keys[llm] and set ANTHROPIC_API_KEY) or --llm claude-cli');
the LLM extractor raises ExtractError (its message is printed);
compile_keys.compile raises ValueError/NotImplementedError (its
message is printed); or -- for a single --monitor pm3/pm4 target -- the
workout is a calorie workout, which those monitors don't support.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from . import __version__, compile_keys
from . import pm5_model as pm5
from .spec import parse_spec


class Wod2KeysError(Exception):
    """Raised for any user-facing failure in run(); the CLI catches
    this and prints exc's message (no traceback) with exit code 2."""


def _normalise_title(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    normalised = " ".join(first_line.split())
    return normalised[:80]


_UNPARSED_NO_LLM_HINT = (
    "unparsed: rules could not parse this text; enable the LLM fallback "
    "with --llm anthropic (pip install pm5keys[llm] and set "
    "ANTHROPIC_API_KEY) or --llm claude-cli"
)


_MONITOR_LINE_LABEL = {"pm5": "PM5", "pm3": "PM3/PM4", "pm4": "PM3/PM4"}
_CALORIE_KINDS = ("single_calorie", "intervals_calorie")


def run(
    text: str,
    llm: str = "auto",
    model: str | None = None,
    extract_fn=None,
    monitor: str = "pm5",
) -> dict:
    """Run the full text -> spec -> keys pipeline. Returns a dict with
    keys: title, spec, source ('rules' or 'llm'), monitor (the
    normalised --monitor value, one of 'pm5'/'pm3'/'pm4'/'both'), lines
    (list of str, the 'PM5: ...' / 'PM3/PM4: ...' output lines in
    display order), and explains (list of (label, trace) pairs, one per
    monitor actually compiled, label being 'PM3/PM4' or 'PM5', trace a
    pm5_model.explain()-shaped list of (press, screen, action) tuples --
    monitors whose compile raised NotImplementedError have no entry
    here). Raises Wod2KeysError on any user-facing failure (empty input,
    unparsed text with the LLM fallback unavailable, LLM extraction
    failure, or -- for a single --monitor pm3/pm4 target -- a calorie
    workout, which those monitors don't support) with a one-line message
    suitable for printing to the user.

    llm selects the backend name passed to pm5keys.llm.resolve_backend
    ('auto' (default), 'none', 'anthropic', or 'claude-cli').

    extract_fn, if given, replaces the LLM extractor's extract_spec
    (for offline testing); it is called as extract_fn(text, model=model)
    and extract_fn's own exceptions are treated as user-facing failures
    (message forwarded verbatim).

    monitor selects the target monitor(s): 'pm5' (default), 'pm3', 'pm4'
    (an alias of 'pm3'), or 'both' (PM3/PM4 line first, then PM5, matching
    Concept2's own WOD emails). For a single monitor target, a calorie
    workout ('single_calorie'/'intervals_calorie') on 'pm3'/'pm4' raises
    Wod2KeysError with compile_keys.compile's NotImplementedError message.
    For 'both', a calorie workout still compiles and prints the PM5 line;
    the PM3/PM4 line reads 'PM3/PM4: not supported (calorie workouts)'
    instead of raising.
    """
    if not text or not text.strip():
        raise Wod2KeysError("empty input")

    spec = parse_spec(text, None)
    source = "rules"

    if spec is None:
        if extract_fn is not None:
            fn = extract_fn
            extract_error_types = (Exception,)
        else:
            try:
                from .llm import ExtractError, extract_spec, resolve_backend
                from .llm.backends import NoneBackend
            except ImportError as exc:
                raise Wod2KeysError(_UNPARSED_NO_LLM_HINT) from exc

            try:
                backend = resolve_backend(llm)
            except ExtractError as exc:
                raise Wod2KeysError(str(exc)) from exc

            if isinstance(backend, NoneBackend):
                raise Wod2KeysError(_UNPARSED_NO_LLM_HINT)

            extract_error_types = (ExtractError,)

            def fn(t, model=model):
                return extract_spec(t, backend=backend, model=model)

        try:
            spec = fn(text, model=model)
        except extract_error_types as exc:
            raise Wod2KeysError(str(exc)) from exc
        source = "llm"

    spec = dict(spec)
    spec["machine"] = "rower"

    if monitor == "both":
        target_monitors = ["pm3", "pm5"]  # PM3/PM4 line first, then PM5
    else:
        target_monitors = [monitor]

    lines = []
    explains = []
    primary_keys = None
    primary_explain = None
    for target in target_monitors:
        try:
            keys = compile_keys.compile(spec, monitor=target)
        except (ValueError, NotImplementedError) as exc:
            if monitor == "both" and target == "pm3" and spec.get("kind") in _CALORIE_KINDS:
                lines.append("PM3/PM4: not supported (calorie workouts)")
                continue
            raise Wod2KeysError(str(exc)) from exc

        label = _MONITOR_LINE_LABEL[target]
        lines.append(f"{label}: {keys}")
        trace = pm5.explain(keys, monitor=target)
        explains.append((label, trace))
        if target == monitor or (monitor == "both" and target == "pm5"):
            primary_keys = keys
            primary_explain = trace

    return {
        "title": _normalise_title(text),
        "spec": spec,
        "source": source,
        "monitor": monitor,
        "lines": lines,
        "explains": explains,
        # Backwards-compatible single-monitor fields: the compiled keys
        # and explain trace for the "primary" target (the requested
        # monitor itself, or PM5 when monitor='both', matching pre-R12
        # callers that assumed a single PM5 result).
        "keys": primary_keys,
        "explain": primary_explain,
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
            total_delta = sum(int(_DIGIT_EDIT_RE.match(a).group(3)) for a in actions)
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
    parser.add_argument(
        "text", nargs="?", default=None, help="workout description (else read from stdin)"
    )
    parser.add_argument(
        "--llm",
        default="auto",
        choices=["auto", "none", "anthropic", "claude-cli"],
        help="which LLM backend to use for the fallback (default: auto)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="alias for --llm none (do not fall back to the LLM extractor)",
    )
    parser.add_argument("--explain", action="store_true", help="print a per-press explanation")
    parser.add_argument(
        "--verbose", action="store_true", help="print spec JSON and source to stderr"
    )
    parser.add_argument("--model", default=None, help="LLM model id/alias to use")
    parser.add_argument(
        "--monitor",
        default="pm5",
        choices=["pm5", "pm3", "pm4", "both"],
        help="target monitor(s): pm5 (default), pm3, pm4 (alias of pm3), or both "
        "(prints the PM3/PM4 line first, then PM5, like Concept2's own WOD emails)",
    )
    parser.add_argument("--version", action="version", version=f"pm5keys {__version__}")

    args = parser.parse_args(argv)

    llm = "none" if args.no_llm else args.llm

    text = args.text if args.text is not None else _read_stdin_text()

    try:
        result = run(text, llm=llm, model=args.model, monitor=args.monitor)
    except Wod2KeysError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.verbose:
        print(json.dumps(result["spec"], indent=2), file=sys.stderr)
        print(f"source: {result['source']}", file=sys.stderr)

    print(result["title"])
    for line in result["lines"]:
        print(line)

    if args.explain:
        for label, trace in result["explains"]:
            if len(result["explains"]) > 1:
                print(f"{label}:")
            for line in _format_explain(trace):
                print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
