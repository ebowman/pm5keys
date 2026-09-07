#!/usr/bin/env python3
"""Compile a WorkoutSpec (see docs/SPEC.md) into a canonical PM5 key
sequence (see docs/notation.md), the reverse direction of pm5_model.py's
simulator.

Compile strategy ("canonical editing strategy"), which reproduces every
gold sequence in spec_parsed.jsonl that this module's compile()
supports (single_distance/time/calorie, intervals_distance/time/calorie,
and intervals_variable -- see pm5_model.py's module docstring for
field layouts/defaults and the menu-navigation model this builds on):

  1. Press the menu keys to reach the target entry screen (Main Menu ->
     B -> D -> chooser letter[s]) exactly as pm5_model.py's state
     machine expects them.
  2. On the entry screen, starting from the screen's default cursor
     position: press D (cursor left) until the cursor is on the
     leftmost field that needs to change from the screen's default (or
     the retained value, for a non-first interval of a repeated type in
     intervals_variable). If nothing needs to change, skip straight to
     step 4.
  3. Sweep the cursor right field by field with A, from the leftmost
     changed field to the rightmost changed field (inclusive), pressing
     B (+1) or C (-1) the required number of times on each field that
     differs from its current value; fields that don't need to change
     along the way get a single A and nothing else.
  4. Press E to confirm.

For intervals_variable, steps 1-4 repeat per interval (the "menu keys"
in step 1 become just the type letter B/C/D, since after the first
interval we're always back at the type chooser), and a final extra E is
pressed after the last interval's confirmation to finish the workout.

Because this literally emits one press per action, adjacent same-letter
presses across the menu/entry-screen boundary merge exactly the way
gold's sequences do once passed through keyseq.canonical (e.g.
selecting Intervals: Distance is "A", and if the entry screen then
needs 4 more A presses to reach the target field, this naturally
becomes "5A" post-canonicalisation) -- this module never special-cases
that merge; it falls out of always emitting presses and canonicalising
at the end.

compile(spec) raises NotImplementedError for spec kinds this module
cannot support (there are none among the six kinds handled -- every
WorkoutSpec kind has a corresponding PM5 screen) and ValueError for
spec values that don't fit the PM5's fields (distance > 99999m, a
computed field digit > 9 register meaning the value has too many
digits for the screen's field count, or rest > 99:59).

CLI:
    python3 -m pm5keys.compile_keys --verify spec_parsed.jsonl \
        [--out data/reports/compile_report.md]
        For every row, (i) runs the simulator on the GOLD sequence and
        checks same_workout(sim(gold), spec) -- this validates
        pm5_model's model; (ii) compiles the spec and compares to gold
        exactly; (iii) if not exact, checks
        same_workout(sim(compiled), sim(gold)). Categorises every row
        as EXACT / EQUIVALENT / GOLD_VARIABLE / GOLD_MISMATCH /
        MODEL_ERROR (see _classify_row's docstring for the precise
        rules), prints counts per category, and writes the report
        (`--out`, default `data/reports/compile_report.md` relative to
        the current working directory -- this module never writes next
        to its own file) with the per-row table.
"""

from __future__ import annotations

import json
import os
import sys

from . import keyseq
from . import pm5_model as pm5

# ---------------------------------------------------------------------------
# compile()
# ---------------------------------------------------------------------------

_UNIT_KEY = {
    "distance_m": "distance_m",
    "time_s": "time_s",
    "calories": "calories",
}

# Menu-key tables are keyed first by normalised monitor name ('pm5' or
# 'pm3' -- 'pm4' is normalised to 'pm3', see pm5_model._normalise_monitor),
# since the two monitor families use different New Workout choosers (see
# pm5_model.py's module docstring and docs/pm3-model.md). PM3/PM4 has no
# calorie screens at all, so 'single_calorie' and 'intervals_calorie'
# simply have no entry in the pm3 tables -- compile() checks for this and
# raises NotImplementedError before ever consulting these tables for an
# unsupported kind.
_SINGLE_MENU_KEY = {
    "pm5": {"single_distance": "A", "single_time": "B", "single_calorie": "C"},
    "pm3": {"single_distance": "A", "single_time": "B"},
}
_SINGLE_SCREEN = {
    "single_distance": pm5.SINGLE_DISTANCE,
    "single_time": pm5.SINGLE_TIME,
    "single_calorie": pm5.SINGLE_CALORIE,
}

# PM5 reaches a fixed-interval screen via the Intervals submenu (B-D-D-<letter>);
# PM3/PM4 reaches it directly from the flat New Workout chooser (B-D-<letter>).
# The "menu keys" below are the presses after 'B-D' (New Workout) and before
# the entry screen's own edits -- one letter for pm3 (the flat chooser
# letter), two letters for pm5 (D for "Intervals", then the submenu letter).
_FIXED_INTERVAL_MENU_KEYS = {
    "pm5": {
        "intervals_distance": ["D", "A"],
        "intervals_time": ["D", "B"],
        "intervals_calorie": ["D", "C"],
    },
    "pm3": {"intervals_distance": ["C"], "intervals_time": ["D"]},
}
_FIXED_INTERVAL_SCREEN = {
    "intervals_distance": pm5.INTERVALS_DISTANCE,
    "intervals_time": pm5.INTERVALS_TIME,
    "intervals_calorie": pm5.INTERVALS_CALORIE,
}

# Presses (after 'B-D', New Workout) that reach the Intervals: Variable
# type chooser: pm5 goes through the Intervals submenu (D) then Variable
# (D); pm3/pm4 reaches it directly from the flat chooser (E).
_VARIABLE_MENU_KEYS = {
    "pm5": ["D", "D"],
    "pm3": ["E"],
}

# The Variable type chooser itself (B=Calorie, C=Distance, D=Time) is
# identical on both monitor families -- variable-calorie legs are
# supported on PM3/PM4 even though a fixed/single calorie workout is not.
_VARIABLE_TYPE_KEY = {
    "distance_m": "C",
    "time_s": "D",
    "calories": "B",
}
_VARIABLE_TYPE_SCREEN = {
    "distance_m": pm5.INTERVALS_DISTANCE,
    "time_s": pm5.INTERVALS_TIME,
    "calories": pm5.INTERVALS_CALORIE,
}

_NO_CALORIE_MSG = "PM3/PM4 do not support calorie workouts"

_MAX_DISTANCE_M = 99999
_MAX_REST_S = 99 * 60 + 59
_MAX_TIME_S = 9 * 3600 + 59 * 60 + 59  # 9:59:59, the widest the 5-digit time screen holds
_MAX_CALORIES = 999


def _check_value_fits(unit: str, value: int, *, where: str) -> None:
    if unit == "distance_m":
        if not (0 <= value <= _MAX_DISTANCE_M):
            raise ValueError(f"{where}: distance_m {value} does not fit (0..{_MAX_DISTANCE_M})")
    elif unit == "time_s":
        if not (0 <= value <= _MAX_TIME_S):
            raise ValueError(f"{where}: time_s {value} does not fit (0..{_MAX_TIME_S})")
    elif unit == "calories":
        if not (0 <= value <= _MAX_CALORIES):
            raise ValueError(f"{where}: calories {value} does not fit (0..{_MAX_CALORIES})")
    else:
        raise ValueError(f"{where}: unknown unit {unit!r}")


def _check_rest_fits(rest_s: int, *, where: str) -> None:
    if not (0 <= rest_s <= _MAX_REST_S):
        raise ValueError(f"{where}: rest_s {rest_s} does not fit (0..{_MAX_REST_S})")


def _digits_for(screen: pm5._Screen, value: int) -> list:
    return pm5._value_to_digits(screen.work_fields, value)


def _rest_digits_for(screen: pm5._Screen, value: int) -> list:
    return pm5._value_to_digits(screen.rest_fields, value)


def _sweep_presses(
    current_digits: list, target_digits: list, current_cursor: int, default_cursor: int
) -> list:
    """Emit the D*/A*/B*/C* presses (each as a single-letter press, not yet
    merged) to move current_digits -> target_digits, starting from
    current_cursor (which must equal default_cursor -- the screen has just
    been (re)entered), and return the flat list of presses (cursor moves
    and digit edits), NOT including the final E.
    """
    assert current_cursor == default_cursor

    changed = [i for i in range(len(target_digits)) if current_digits[i] != target_digits[i]]
    presses: list = []
    if not changed:
        return presses

    leftmost, rightmost = min(changed), max(changed)

    cursor = default_cursor
    while cursor > leftmost:
        presses.append("D")
        cursor -= 1
    while cursor < leftmost:
        presses.append("A")
        cursor += 1

    for i in range(leftmost, rightmost + 1):
        delta = target_digits[i] - current_digits[i]
        if delta > 0:
            presses.extend(["B"] * delta)
        elif delta < 0:
            presses.extend(["C"] * (-delta))
        if i < rightmost:
            presses.append("A")

    return presses


def _compile_single_or_fixed(spec: dict, monitor: str) -> list:
    kind = spec["kind"]
    work = spec["work"]
    unit = next(iter(work.keys()))
    value = work[unit]
    _check_value_fits(unit, value, where=f"{kind}.work.{unit}")

    presses = ["B", "D"]  # Main Menu -> Select Workout -> New Workout

    if kind in _SINGLE_MENU_KEY[monitor]:
        presses.append(_SINGLE_MENU_KEY[monitor][kind])
        screen = _SINGLE_SCREEN[kind]
        target_work_digits = _digits_for(screen, value)
        target_digits = target_work_digits
        current_digits = _digits_for(screen, screen.default_work)
    else:
        rest_s = spec["rest_s"]
        _check_rest_fits(rest_s, where=f"{kind}.rest_s")
        presses.extend(_FIXED_INTERVAL_MENU_KEYS[monitor][kind])
        screen = _FIXED_INTERVAL_SCREEN[kind]
        target_digits = _digits_for(screen, value) + _rest_digits_for(screen, rest_s)
        current_digits = _digits_for(screen, screen.default_work) + _rest_digits_for(
            screen, screen.default_rest
        )

    presses.extend(
        _sweep_presses(current_digits, target_digits, screen.default_cursor, screen.default_cursor)
    )
    presses.append("E")
    return presses


def _compile_variable(spec: dict, monitor: str) -> list:
    intervals = spec["intervals"]

    # Main Menu -> Select Workout -> New Workout -> ... -> Variable
    presses = ["B", "D"] + list(_VARIABLE_MENU_KEYS[monitor])

    retained: dict = {}
    n = len(intervals)
    for i, iv in enumerate(intervals):
        work = iv["work"]
        unit = next(iter(work.keys()))
        value = work[unit]
        rest_s = iv["rest_s"]
        _check_value_fits(unit, value, where=f"intervals[{i}].work.{unit}")
        # The final interval's rest is not meaningfully specified by the
        # WorkoutSpec schema (SPEC.md: only the last interval may be 0,
        # and it means "not recorded", not "explicitly zero") -- do not
        # emit any rest edit for it; whatever the screen already holds
        # (the type's default, or the value retained from this type's
        # previous interval) is left in place.
        is_last = i == n - 1

        screen = _VARIABLE_TYPE_SCREEN[unit]
        presses.append(_VARIABLE_TYPE_KEY[unit])

        if unit in retained:
            cur_work_val, cur_rest_val = retained[unit]
        else:
            cur_work_val, cur_rest_val = screen.default_work, screen.default_rest

        current_digits = _digits_for(screen, cur_work_val) + _rest_digits_for(screen, cur_rest_val)

        if is_last:
            target_rest_val = cur_rest_val
        else:
            _check_rest_fits(rest_s, where=f"intervals[{i}].rest_s")
            target_rest_val = rest_s
        target_digits = _digits_for(screen, value) + _rest_digits_for(screen, target_rest_val)

        presses.extend(
            _sweep_presses(
                current_digits, target_digits, screen.default_cursor, screen.default_cursor
            )
        )
        presses.append("E")

        retained[unit] = (value, target_rest_val)

    presses.append("E")  # finish the workout
    return presses


def compile(spec: dict, monitor: str = "pm5") -> str:
    """Compile a WorkoutSpec dict into a canonical key sequence string for
    the given monitor ('pm5' (default), 'pm3', or 'pm4' -- 'pm4' is a
    spelling alias for 'pm3'; see pm5_model.py's module docstring).
    Raises NotImplementedError for an unsupported (monitor, spec kind)
    combination -- every one of the six WorkoutSpec kinds is supported on
    'pm5', but 'pm3'/'pm4' do not support 'single_calorie' or
    'intervals_calorie' (Concept2's PM3/PM4 monitors have no calorie
    workout screens at all) -- and ValueError for values that don't fit
    the monitor's entry-screen fields."""
    monitor = pm5._normalise_monitor(monitor)
    kind = spec.get("kind")

    if monitor == "pm3" and kind in ("single_calorie", "intervals_calorie"):
        raise NotImplementedError(_NO_CALORIE_MSG)

    if kind in _SINGLE_MENU_KEY["pm5"] or kind in _FIXED_INTERVAL_MENU_KEYS["pm5"]:
        presses = _compile_single_or_fixed(spec, monitor)
    elif kind == "intervals_variable":
        presses = _compile_variable(spec, monitor)
    else:
        raise NotImplementedError(f"cannot compile spec kind {kind!r}")

    return keyseq.compress(presses)


def explain(spec: dict, monitor: str = "pm5") -> list:
    """Compile spec for the given monitor and return
    pm5_model.explain()'s human-readable trace over the resulting
    sequence."""
    return pm5.explain(compile(spec, monitor=monitor), monitor=monitor)


# ---------------------------------------------------------------------------
# same_workout()
# ---------------------------------------------------------------------------


def same_workout(spec_a: dict, spec_b: dict) -> bool:
    """True if spec_a and spec_b describe the same workout for PM5-
    programming purposes: same kind, same work amount(s), same rest(s) --
    ignoring count, machine, notes, and (for intervals_variable) the
    last interval's rest_s, which the schema does not treat as a
    meaningful value."""
    if spec_a.get("kind") != spec_b.get("kind"):
        return False
    kind = spec_a["kind"]

    if kind == "intervals_variable":
        ivs_a = spec_a.get("intervals", [])
        ivs_b = spec_b.get("intervals", [])
        if len(ivs_a) != len(ivs_b):
            return False
        n = len(ivs_a)
        for i, (a, b) in enumerate(zip(ivs_a, ivs_b, strict=True)):
            if a.get("work") != b.get("work"):
                return False
            if i < n - 1 and a.get("rest_s") != b.get("rest_s"):
                return False
        return True

    if spec_a.get("work") != spec_b.get("work"):
        return False
    if kind.startswith("intervals_"):
        if spec_a.get("rest_s") != spec_b.get("rest_s"):
            return False
    return True


# ---------------------------------------------------------------------------
# --verify CLI
# ---------------------------------------------------------------------------


def _classify_row(spec: dict, gold_seq: str, monitor: str = "pm5") -> dict:
    """Run the full per-row verification described in the module
    docstring's CLI section, against the given monitor's gold sequence
    (gold_seq -- the row's 'pm5' column for monitor='pm5', or its
    'pm34' column for monitor='pm3'/'pm4'). Returns a dict with keys:
    category, sim_gold, sim_compiled (may be None), compiled (may be
    None), error (str or None).

    Categories:
      MODEL_ERROR   -- pm5.run(gold_seq, monitor) raised (the model
                       itself is wrong for this row); everything else
                       is skipped.
      EXACT         -- compile(spec, monitor) canonicalises to exactly
                       gold_seq.
      EQUIVALENT    -- compile(spec, monitor) differs from gold
                       textually, but same_workout(sim(compiled),
                       sim(gold)) holds (a different button path to the
                       same workout).
      GOLD_VARIABLE -- sim(gold) is not same_workout(spec) directly, but
                       is an intervals_variable expansion of a fixed-
                       interval spec: len(intervals) == spec['count'] and
                       every interval equals spec's work/rest (gold
                       programmed the workout via the Variable screen
                       instead of the matching fixed screen).
      GOLD_MISMATCH -- sim(gold) is not the spec at all, and is not a
                       GOLD_VARIABLE case either (a genuine gold-data
                       error, e.g. a Concept2 typo). A spec kind
                       unsupported on this monitor (compile() raising
                       NotImplementedError, e.g. a calorie kind on
                       pm3/pm4) also falls through to this category,
                       since sim(gold) still describes a real (if
                       uncompilable) workout to compare against.
    """
    try:
        sim_gold = pm5.run(gold_seq, monitor=monitor)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any
        # exception here means the model is wrong for this row.
        return {
            "category": "MODEL_ERROR",
            "sim_gold": None,
            "sim_compiled": None,
            "compiled": None,
            "error": str(exc),
        }

    try:
        compiled = compile(spec, monitor=monitor)
    except (NotImplementedError, ValueError) as exc:
        compiled = None
        compile_error = str(exc)
    else:
        compile_error = None

    gold_canonical = keyseq.canonical(gold_seq)

    if compiled is not None and compiled == gold_canonical:
        return {
            "category": "EXACT",
            "sim_gold": sim_gold,
            "sim_compiled": sim_gold,
            "compiled": compiled,
            "error": None,
        }

    sim_compiled = None
    if compiled is not None:
        try:
            sim_compiled = pm5.run(compiled, monitor=monitor)
        except Exception as exc:  # noqa: BLE001
            return {
                "category": "MODEL_ERROR",
                "sim_gold": sim_gold,
                "sim_compiled": None,
                "compiled": compiled,
                "error": f"simulator raised on our own compiled sequence: {exc}",
            }
        if same_workout(sim_compiled, sim_gold):
            return {
                "category": "EQUIVALENT",
                "sim_gold": sim_gold,
                "sim_compiled": sim_compiled,
                "compiled": compiled,
                "error": None,
            }

    # Not exact/equivalent (or compile() raised) -- check whether gold
    # used the Variable screen for what the spec says is a fixed-interval
    # workout (GOLD_VARIABLE), else it's a genuine mismatch.
    if (
        spec.get("kind", "").startswith("intervals_")
        and spec.get("kind") != "intervals_variable"
        and sim_gold.get("kind") == "intervals_variable"
    ):
        count = spec.get("count")
        ivs = sim_gold.get("intervals", [])
        expected_work = spec.get("work")
        expected_rest = spec.get("rest_s")
        if (
            count is not None
            and len(ivs) == count
            and all(
                iv.get("work") == expected_work and iv.get("rest_s") == expected_rest for iv in ivs
            )
        ):
            return {
                "category": "GOLD_VARIABLE",
                "sim_gold": sim_gold,
                "sim_compiled": sim_compiled,
                "compiled": compiled,
                "error": compile_error,
            }

    return {
        "category": "GOLD_MISMATCH",
        "sim_gold": sim_gold,
        "sim_compiled": sim_compiled,
        "compiled": compiled,
        "error": compile_error,
    }


_DEFAULT_VERIFY_OUT = os.path.join("data", "reports", "compile_report.md")
_DEFAULT_VERIFY_OUT_PM3 = os.path.join("data", "reports", "compile_report_pm3.md")

# Default location of the raw scrape dataset.jsonl, which carries the
# 'pm34' gold column that spec_parsed.jsonl does not. Used only when
# monitor != 'pm5' to join spec_parsed.jsonl rows to their pm34 gold
# sequence by (title, description, machines) -- see _load_pm34_lookup.
_DEFAULT_DATASET_PATH = os.path.join("data", "dataset.jsonl")


def _load_pm34_lookup(dataset_path: str) -> dict:
    """Build a {(title, description, machines): pm34_or_None} lookup from
    dataset.jsonl, used to join spec_parsed.jsonl rows (which have no
    'pm34' field of their own) to their PM3/PM4 gold sequence. Every
    (title, description, machines) key in dataset.jsonl maps to a single
    consistent pm34 value (verified against the full 1,950-row dataset
    when this join was designed); if a key legitimately had conflicting
    pm34 values, the last row processed wins."""
    lookup: dict = {}
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row["title"], row["description"], row["machines"])
            lookup[key] = row.get("pm34")
    return lookup


def _verify(
    path: str,
    out_path: str | None = None,
    monitor: str = "pm5",
    dataset_path: str = _DEFAULT_DATASET_PATH,
) -> int:
    monitor = pm5._normalise_monitor(monitor)
    if out_path is None:
        out_path = _DEFAULT_VERIFY_OUT if monitor == "pm5" else _DEFAULT_VERIFY_OUT_PM3

    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    pm34_lookup = None
    skipped_null = 0
    if monitor != "pm5":
        pm34_lookup = _load_pm34_lookup(dataset_path)

    counts: dict = {}
    report_rows = []

    for row in rows:
        spec = row["spec"]
        if monitor == "pm5":
            gold_seq = row["pm5"]
        else:
            key = (row["title"], row["description"], row["machines"])
            gold_seq = pm34_lookup.get(key)
            if gold_seq is None:
                skipped_null += 1
                continue
        result = _classify_row(spec, gold_seq, monitor=monitor)
        category = result["category"]
        counts[category] = counts.get(category, 0) + 1
        report_rows.append((row, gold_seq, result))

    print("Per-category counts:")
    for category in ("EXACT", "EQUIVALENT", "GOLD_VARIABLE", "GOLD_MISMATCH", "MODEL_ERROR"):
        print(f"  {category}: {counts.get(category, 0)}")
    print(f"  TOTAL: {len(report_rows)}")
    if monitor != "pm5":
        print(f"  SKIPPED (null pm34, e.g. calorie workouts): {skipped_null}")

    _write_report(report_rows, out_path, monitor=monitor, skipped_null=skipped_null)

    return 0


def _write_report(
    report_rows, out_path: str = _DEFAULT_VERIFY_OUT, monitor: str = "pm5", skipped_null: int = 0
) -> None:
    monitor_label = "PM5" if monitor == "pm5" else "PM3/PM4"
    lines = [
        f"# compile_keys.py --verify report ({monitor_label})",
        "",
        "Per-row verification of pm5_model.py's simulator and compile_keys.py's",
        "compiler against every row of spec_parsed.jsonl. See",
        "compile_keys.py's module docstring for what each category means.",
    ]
    if monitor != "pm5":
        lines.append(
            f"Rows whose gold pm34 sequence is null (calorie workouts, which PM3/PM4 "
            f"do not support) are skipped: {skipped_null} skipped."
        )
    lines.extend(
        [
            "",
            f"| Title | Machines | Category | Gold ({monitor_label}) | Compiled |",
            "|---|---|---|---|---|",
        ]
    )
    for row, gold_seq, result in report_rows:
        title = row["title"].replace("|", "\\|")
        machines = row["machines"]
        category = result["category"]
        compiled = result["compiled"] or (result["error"] or "")
        lines.append(f"| {title} | {machines} | {category} | `{gold_seq}` | `{compiled}` |")

    lines.append("")
    lines.append("## Non-EXACT rows in detail")
    lines.append("")
    for row, gold_seq, result in report_rows:
        if result["category"] == "EXACT":
            continue
        lines.append(f"### {row['title']} ({row['machines']})")
        lines.append("")
        lines.append(f"- category: {result['category']}")
        lines.append(f"- gold: `{gold_seq}`")
        lines.append(f"- compiled: `{result['compiled']}`")
        if result["error"]:
            lines.append(f"- compile error: {result['error']}")
        lines.append(f"- spec: `{json.dumps(row['spec'])}`")
        lines.append(f"- sim(gold): `{json.dumps(result['sim_gold'])}`")
        if result["sim_compiled"] is not None:
            lines.append(f"- sim(compiled): `{json.dumps(result['sim_compiled'])}`")
        lines.append("")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


_VERIFY_USAGE = (
    "usage: python3 -m pm5keys.compile_keys --verify <spec_parsed.jsonl> "
    f"[--out PATH] [--monitor {{pm5,pm3,pm4}}] [--dataset {_DEFAULT_DATASET_PATH}]"
)


def _main(argv: list) -> int:
    if len(argv) >= 3 and argv[1] == "--verify":
        spec_path = argv[2]
        out_path = None
        monitor = "pm5"
        dataset_path = _DEFAULT_DATASET_PATH
        rest = argv[3:]
        i = 0
        while i < len(rest):
            if rest[i] == "--out" and i + 1 < len(rest):
                out_path = rest[i + 1]
                i += 2
            elif rest[i] == "--monitor" and i + 1 < len(rest):
                monitor = rest[i + 1]
                i += 2
            elif rest[i] == "--dataset" and i + 1 < len(rest):
                dataset_path = rest[i + 1]
                i += 2
            else:
                print(_VERIFY_USAGE, file=sys.stderr)
                return 1
        try:
            return _verify(spec_path, out_path, monitor=monitor, dataset_path=dataset_path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(_VERIFY_USAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
