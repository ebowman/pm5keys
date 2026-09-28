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
             [--explain] [--summary] [--verbose] [--model MODEL]
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
        last action's destination/value). For an intervals_variable
        workout, runs of consecutive legs that press-for-press program
        identically are additionally collapsed into one '<n>x ...'
        summary line covering the leg range. With --monitor both,
        --explain prints each monitor's trace under its own 'PM3/PM4:'
        / 'PM5:' heading. With --summary, a plain-text leg table for
        the parsed spec is printed before the key-sequence line(s) (one
        row per leg for intervals_variable, collapsing consecutive
        identical legs into a range row; one line for fixed intervals
        or a single piece), followed by a blank line. --summary and
        --explain compose (table, then key line(s), then explain).
        --version prints pm5keys's version and exits 0.

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


def _compute_press_groups(trace: list) -> list:
    """Group consecutive presses per the collapsing rule shared by
    _format_explain and _format_explain_legs: the same press letter and
    screen, and actions that are identical, or differ only in the
    trailing '(now N)' digit-edit value or the cursor-move destination
    field. Returns a list of dicts {'label', 'screen', 'action',
    'start', 'end'} -- 'start'/'end' are the inclusive trace indices
    spanned by the group, 'label' is the press (or '<n>x<press>' for a
    collapsed group), and 'action' is the group's combined/last action
    (see _format_explain's docstring for the collapsed-value rules)."""
    raw_groups = []
    for idx, (press, screen, action) in enumerate(trace):
        key = (press, screen, _action_group_key(action))
        if raw_groups and raw_groups[-1]["key"] == key:
            raw_groups[-1]["actions"].append(action)
            raw_groups[-1]["end"] = idx
        else:
            raw_groups.append({"key": key, "actions": [action], "start": idx, "end": idx})

    groups = []
    for g in raw_groups:
        press, screen, group_key = g["key"]
        count = len(g["actions"])
        label = press if count == 1 else f"{count}x{press}"
        last_action = g["actions"][-1]
        if group_key[0] == "digit_edit" and count > 1:
            field, sign, _delta, _value = _DIGIT_EDIT_RE.match(last_action).groups()
            total_delta = sum(int(_DIGIT_EDIT_RE.match(a).group(3)) for a in g["actions"])
            final_value = _DIGIT_EDIT_RE.match(last_action).group(4)
            action = f"{field} {sign}{total_delta} (now {final_value})"
        else:
            action = last_action
        groups.append(
            {
                "label": label,
                "screen": screen,
                "action": action,
                "start": g["start"],
                "end": g["end"],
            }
        )
    return groups


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
    groups = _compute_press_groups(trace)
    if not groups:
        return []

    label_width = max(len(g["label"]) for g in groups)
    screen_width = max(len(g["screen"]) for g in groups)

    return [
        f"{g['label'].ljust(label_width)}  {g['screen'].ljust(screen_width)}: {g['action']}"
        for g in groups
    ]


# Screen name of the Intervals: Variable per-leg type chooser; a press
# on this screen selecting a type (Time/Distance/Calorie) marks a leg
# boundary, and the trailing 'E' (finish workout) press on this same
# screen marks the end of the whole variable-interval workout.
_VARIABLE_TYPE_CHOOSER_SCREEN = "Intervals: Variable"
_LEG_START_ACTIONS = {"Time", "Distance", "Calorie"}


def _leg_boundaries(trace: list):
    """Return (starts, finish) for an intervals_variable explain()
    trace: starts is the list of trace indices marking the start of
    each leg (the press selecting that leg's type on the 'Intervals:
    Variable' type-chooser screen), in leg order; finish is the trace
    index of the trailing 'finish workout' press, or None. starts is []
    (and finish is None) for a trace with no variable-interval legs at
    all (i.e. any non-intervals_variable spec)."""
    starts = []
    finish = None
    for i, (_press, screen, action) in enumerate(trace):
        if screen != _VARIABLE_TYPE_CHOOSER_SCREEN:
            continue
        if action in _LEG_START_ACTIONS:
            starts.append(i)
        elif action == "finish workout":
            finish = i
    return starts, finish


def _render_leg_range_line(start_leg: int, end_leg: int, leg_groups: list, intervals: list) -> str:
    """Render one collapsed summary line for legs start_leg..end_leg
    (1-based, inclusive), all of which share leg_groups' press-group
    signature (leg_groups is that shared signature, taken from the
    first leg in the range)."""
    count = end_leg - start_leg + 1
    press_seq = "-".join(g["label"] for g in leg_groups)
    if (
        len(leg_groups) == 2
        and leg_groups[0]["action"] in _LEG_START_ACTIONS
        and leg_groups[1]["action"] == "confirm"
    ):
        # The common case: no digit edits were needed for any leg in
        # this range (the work/rest values already matched what the
        # previous leg of this type left behind), so each leg is just
        # 'select type' -> 'confirm'.
        type_name = leg_groups[0]["action"]
        detail = f"legs {start_leg}-{end_leg}"
        if intervals and 0 <= start_leg - 1 < len(intervals):
            iv = intervals[start_leg - 1]
            detail += f", {_format_work(iv['work'])} work"
            if iv.get("rest_s"):
                detail += f", rest carries over at {_format_time_mmss(iv['rest_s'])}"
        return f"{count}x   {press_seq}   Intervals: Variable: {type_name} -> confirm ({detail})"

    desc = "; ".join(f"{g['screen']}: {g['action']}" for g in leg_groups)
    return f"{count}x   {press_seq}   {desc} (legs {start_leg}-{end_leg})"


def _format_explain_legs(trace: list, spec: dict) -> list:
    """Like _format_explain, but for an intervals_variable trace,
    additionally collapses runs of consecutive legs whose full
    press-group signature is identical into one summary line covering
    the leg range (e.g. '9x   D-E   Intervals: Variable: Time ->
    confirm (legs 3-11, 1:00 work, rest carries over at 1:00)'), so
    long variable-interval workouts don't dump one line per press.
    Non-repeated legs, and the pre-leg chooser presses / trailing
    'finish workout' press, are formatted exactly as _format_explain
    would format them. Falls back to _format_explain(trace) unchanged
    when there are fewer than 2 legs (nothing to collapse) or the
    trace has no leg boundaries at all (not an intervals_variable
    trace) -- leg boundaries come from PM5's own explain() trace (the
    'Intervals: Variable' type-chooser screen marks each leg), so no
    separate leg-tracking is needed."""
    starts, finish = _leg_boundaries(trace)
    if len(starts) < 2 or finish is None:
        return _format_explain(trace)

    groups = _compute_press_groups(trace)
    intervals = (spec or {}).get("intervals") or []
    n_legs = len(starts)

    def leg_of(idx):
        for k in range(n_legs):
            lo = starts[k]
            hi = starts[k + 1] - 1 if k + 1 < n_legs else finish - 1
            if lo <= idx <= hi:
                return k + 1
        return None

    per_leg = {k: [] for k in range(1, n_legs + 1)}
    other = []
    for g in groups:
        leg = leg_of(g["start"])
        if leg is None:
            other.append(g)
        else:
            per_leg[leg].append(g)

    def sig(k):
        return tuple((g["label"], g["screen"], g["action"]) for g in per_leg[k])

    ranges = []
    k = 1
    while k <= n_legs:
        j = k
        while j + 1 <= n_legs and sig(j + 1) == sig(k):
            j += 1
        ranges.append((k, j))
        k = j + 1

    # Column widths are computed only from groups that will actually
    # render as standalone '<label>  <screen>: <action>' lines (the
    # collapsed range lines have their own distinct format).
    standalone = list(other)
    for start_leg, end_leg in ranges:
        if end_leg == start_leg:
            standalone.extend(per_leg[start_leg])
    label_width = max((len(g["label"]) for g in standalone), default=0)
    screen_width = max((len(g["screen"]) for g in standalone), default=0)

    def render(g):
        return f"{g['label'].ljust(label_width)}  {g['screen'].ljust(screen_width)}: {g['action']}"

    header = [g for g in other if g["start"] < starts[0]]
    trailer = [g for g in other if g["start"] >= finish]

    lines = [render(g) for g in header]
    for start_leg, end_leg in ranges:
        if end_leg > start_leg:
            lines.append(_render_leg_range_line(start_leg, end_leg, per_leg[start_leg], intervals))
        else:
            lines.extend(render(g) for g in per_leg[start_leg])
    lines.extend(render(g) for g in trailer)
    return lines


def _format_time_mmss(total_s: int) -> str:
    """Format a non-negative second count as 'M:SS' (minutes, unpadded;
    seconds, zero-padded to 2 digits). Minutes are not capped at 59 --
    e.g. 3660 -> '61:00', matching the mm:ss fields PM5 entry screens
    themselves use (see pm5_model.py)."""
    minutes, seconds = divmod(total_s, 60)
    return f"{minutes}:{seconds:02d}"


def _format_work(work: dict) -> str:
    """Format a WorkoutSpec work dict ({distance_m|time_s|calories: N})
    for display: 'M:SS' for time, '<N>m' for distance, '<N> cal' for
    calories."""
    if "time_s" in work:
        return _format_time_mmss(work["time_s"])
    if "distance_m" in work:
        return f"{work['distance_m']}m"
    if "calories" in work:
        return f"{work['calories']} cal"
    # pragma: no cover -- validate_spec guarantees exactly one of the three
    raise ValueError(f"unrecognised work dict: {work!r}")


def _build_variable_summary_lines(intervals: list) -> list:
    """Build the --summary leg table for an intervals_variable spec's
    'intervals' list: a header line ('Workout (M:SS, N legs)' when
    every leg is time-based, else 'Workout (N legs)'), followed by one
    row per leg (or per run of consecutive identical legs, collapsed
    into a single 'start-end ... (xN)' range row). Row columns: leg
    number/range (padded to 7 columns), work (padded to 10 columns),
    then 'rest M:SS' or an em dash '—' for a leg with no trailing
    rest (rest_s == 0; per the WorkoutSpec schema this can only be the
    final leg)."""
    n = len(intervals)
    all_time_based = all("time_s" in iv["work"] for iv in intervals)
    if all_time_based:
        total_s = sum(iv["work"]["time_s"] for iv in intervals) + sum(
            iv["rest_s"] for iv in intervals[:-1]
        )
        header = f"Workout ({_format_time_mmss(total_s)}, {n} legs)"
    else:
        header = f"Workout ({n} legs)"
    lines = [header]

    i = 0
    while i < n:
        j = i
        while (
            j + 1 < n
            and intervals[j + 1]["work"] == intervals[i]["work"]
            and intervals[j + 1]["rest_s"] == intervals[i]["rest_s"]
        ):
            j += 1
        start_num, end_num = i + 1, j + 1
        label = str(start_num) if start_num == end_num else f"{start_num}-{end_num}"
        work_str = _format_work(intervals[i]["work"])
        rest_s = intervals[i]["rest_s"]
        rest_str = "—" if rest_s == 0 else f"rest {_format_time_mmss(rest_s)}"
        row = f"{label.ljust(7)}{work_str.ljust(10)}{rest_str}"
        count = end_num - start_num + 1
        if count > 1:
            row += f"   (x{count})"
        lines.append(row)
        i = j + 1

    return lines


def _build_summary_lines(spec: dict) -> list:
    """Build the --summary output for any parsed WorkoutSpec: the
    multi-row leg table (see _build_variable_summary_lines) for
    intervals_variable, one line 'Workout: N x <work> / M:SS rest' for
    fixed intervals (distance/time/calorie), or one line 'Workout:
    <work>' for a single piece."""
    kind = spec.get("kind")
    if kind == "intervals_variable":
        return _build_variable_summary_lines(spec["intervals"])

    work_str = _format_work(spec["work"])
    if kind.startswith("intervals_"):
        rest_str = _format_time_mmss(spec["rest_s"])
        return [f"Workout: {spec['count']} x {work_str} / {rest_str} rest"]
    return [f"Workout: {work_str}"]


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
        "--summary",
        action="store_true",
        help="print a plain-text leg table for the parsed spec before the key line(s)",
    )
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

    if args.summary:
        for line in _build_summary_lines(result["spec"]):
            print(line)
        print()

    for line in result["lines"]:
        print(line)

    if args.explain:
        spec_kind = result["spec"].get("kind")
        for label, trace in result["explains"]:
            if len(result["explains"]) > 1:
                print(f"{label}:")
            if spec_kind == "intervals_variable":
                formatted = _format_explain_legs(trace, result["spec"])
            else:
                formatted = _format_explain(trace)
            for line in formatted:
                print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
