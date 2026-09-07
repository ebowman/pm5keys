# The PM3/PM4 menu model

This document describes what's different about Concept2's PM3 and PM4
monitors compared to the PM5 model described in
[pm5-model.md](pm5-model.md), which `pm3` support in
[`pm5_model.py`](../src/pm5keys/pm5_model.py) and
[`compile_keys.py`](../src/pm5keys/compile_keys.py) is built on. Read
pm5-model.md first — everything not called out below (entry-screen
field layouts and defaults, cursor positions, button semantics, the
Intervals: Variable rules) is identical between the two monitor
families.

PM3 and PM4 share a single gold button-sequence column in the scraped
Concept2 dataset (`pm34` in `data/dataset.jsonl`), so `pm5keys` treats
them as one model: `monitor='pm3'` and `monitor='pm4'` are accepted
everywhere a monitor name is expected (`pm5_model.PM5(monitor=...)`,
`pm5_model.run/explain(..., monitor=...)`,
`compile_keys.compile/explain(..., monitor=...)`, and the CLI's
`--monitor` flag), and `'pm4'` is a pure spelling alias normalised to
`'pm3'` internally.

## What's different

### A flat New Workout chooser, no Intervals submenu

PM5's New Workout chooser is four items (A/B/C/D) where D descends into
a second-level Intervals submenu (itself four items, A/B/C/D). PM3/PM4
has **no Intervals submenu at all** — its New Workout chooser is a
single flat five-item list:

| Screen | Button | Goes to |
|---|---|---|
| New Workout | A | Single Distance |
| New Workout | B | Single Time |
| New Workout | C | Intervals: Distance |
| New Workout | D | Intervals: Time |
| New Workout | E | Intervals: Variable |

Compare PM5's two-level chooser (New Workout -> D -> Intervals -> A/B/C/D)
in pm5-model.md's menu tree table. This was the one part of the
hand-derived hypothesis handed into this implementation that gold
directly contradicted: the hypothesis assumed PM3/PM4 kept PM5's nested
Intervals submenu shape (just relabelling items), but every gold `pm34`
row shows the fixed-interval and Variable screens reached in a single
press directly from New Workout (e.g. Intervals: Distance is
`B-D-C-...`, not `B-D-D-A-...`). The model implemented here follows the
data.

### No calorie screens at all

PM3/PM4 has neither a Single Calorie screen nor an Intervals: Calorie
screen — Concept2's own documentation states the PM3 and PM4 monitors
do not support calorie-based fixed-interval or single workouts. This
shows up in the gold data as `pm34: null` for every `single_calorie` /
`intervals_calorie` row (5 of the 116 `spec_parsed.jsonl` rows; 40 of
the 1,950 raw `dataset.jsonl` rows, once every machine variant of each
such workout is counted).

`compile_keys.compile(spec, monitor='pm3')` raises
`NotImplementedError("PM3/PM4 do not support calorie workouts")` for
`single_calorie` and `intervals_calorie` spec kinds. `pm5_model.PM5(monitor='pm3')`
has no way to reach a calorie screen at all — none of its New Workout
chooser letters (A-E) lead to one (see `tests/test_pm3_model.py`'s
`Pm3NoCalorieMenuTest`).

**Variable-calorie legs are still supported**, even though fixed/single
calorie workouts are not: the Intervals: Variable per-interval type
chooser (B = Calorie, C = Distance, D = Time) is identical on both
monitor families, and gold confirms it — e.g. "10/20/30/40/50/60
Calories, 1 minute rest between intervals" compiles on PM3/PM4 to
`B-D-E-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E`, using Calorie legs
inside the Variable screen.

### Everything else is identical

Confirmed against every non-null gold `pm34` row (111 of 116
`spec_parsed.jsonl` rows — the remaining 5 are the null-pm34 calorie
rows described above):

- Entry-screen field layouts, default values, and default cursor
  positions (Single Distance, Single Time, Intervals: Distance,
  Intervals: Time, and each Variable-interval type's screen) are
  byte-for-byte identical to PM5's.
- Button semantics (A = cursor right, D = cursor left, B = +1, C = -1,
  E = confirm) are identical.
- The Intervals: Variable rules — type reselected before every
  interval, per-type value retention, cursor always resets to the
  screen default, one final E to finish — are identical; only the
  press that reaches the Variable screen itself differs (`E` directly
  from New Workout on PM3/PM4, vs `D-D` through the Intervals submenu
  on PM5).
- The interval count is still never encoded in the key sequence.
- Concept2 still occasionally uses the Variable screen for a
  fixed-shape workout, and the pyramid-typo gold-data quirk described
  in pm5-model.md still exists — these are properties of the
  underlying *workout data*, not the monitor, so they reproduce
  identically on both monitor families (see the evidence table below).

## Evidence

Counts from `python -m pm5keys.compile_keys --verify data/spec_parsed.jsonl
--monitor pm3` (see `data/reports/compile_report_pm3.md` for the full
per-row report; categories are defined in `compile_keys.py`'s module
docstring, same meanings as the PM5 report):

| Category | Count |
|---|---|
| EXACT | 103 |
| EQUIVALENT | 4 |
| GOLD_VARIABLE | 3 |
| GOLD_MISMATCH | 1 |
| MODEL_ERROR | 0 |
| **Verified TOTAL** | **111** |
| Skipped (null `pm34`, calorie workouts) | 5 |

The non-EXACT rows are the *same* underlying gold rows flagged
EQUIVALENT/GOLD_VARIABLE/GOLD_MISMATCH in the PM5 report (see
pm5-model.md's evidence table and "Facts a rower will find
surprising") — e.g. the pyramid-typo row ("5 min, 10 min, 15 min, 10
min, 5 min pyramid / 2 min easy") is GOLD_MISMATCH on both monitors,
for the same reason (Concept2's own published sequence's last leg is
15:00, not 5:00 as the title claims). No PM3/PM4-specific data
anomaly was found; MODEL_ERROR is 0, confirming the flat-chooser /
no-calorie-screens model above accounts for every difference between
the `pm5` and `pm34` gold columns.

## Verifying on your own monitor

See [verification.md](verification.md) for a short PM3/PM4 section
with worked examples; the same "press it by hand and compare" caveats
in that document's PM5 checklist apply here too — none of this has
been pressed on physical hardware.
