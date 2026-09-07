# The PM5 menu model

This document describes the PM5 monitor's menu and entry-screen state
machine that [`pm5_model.py`](../src/pm5keys/pm5_model.py) simulates —
what screen you land on for each button press, starting from the Main
Menu, and what workout ends up programmed. See
[notation.md](notation.md) for the button-press notation itself
(`B-2D-5A-2B-E` and friends — that particular sequence is the
RowErg/SkiErg button-press sequence for "8 x 500m, 2 minutes rest";
BikeErg's sequence for the same workout differs, since BikeErg
distances are typically doubled).

Everything below was reverse-engineered against every gold
`(title, pm5, spec)` row in `data/spec_parsed.jsonl` — 116 rows scraped
from Concept2's public WOD pages. See "How this was derived" at the
bottom for the numbers behind that claim.

## Glossary

Terms used below to categorise how a gold row compares against
`pm5keys`'s own compiled sequence or simulated result (see "The
evidence table" for the full counts):

- **EXACT** — `pm5keys` compiles the workout to the exact same button
  sequence Concept2 published.
- **EQUIVALENT** — `pm5keys` compiles a *different* button sequence
  than Concept2 published, but simulating both sequences produces the
  same resulting workout (same button path is not required, just the
  same end state).
- **GOLD_VARIABLE** — Concept2's published sequence programmed the
  workout through the PM5's Variable-interval screen even though every
  interval has identical work/rest — a shape the fixed-interval
  screens could have programmed directly. `pm5keys` compiles the
  simpler fixed-screen sequence instead; this category records that
  Concept2's own sequence, while different, still simulates to the
  same workout.
- **GOLD_MISMATCH** — Concept2's published sequence, when simulated,
  produces a workout that does not match its own title/description
  (i.e. gold itself looks wrong). `pm5keys` compiles what the
  title/description actually says, not gold's apparent error.
- **MODEL_ERROR** — the simulator or compiler failed outright on a
  gold row (an internal bug), rather than producing a sequence that
  can be compared to gold at all. There are currently 0 of these.

## The menu tree

| Screen | Button | Goes to |
|---|---|---|
| Main Menu | B | Select Workout |
| Select Workout | D | New Workout |
| New Workout | A | Single Distance |
| New Workout | B | Single Time |
| New Workout | C | Single Calorie |
| New Workout | D | Intervals |
| Intervals | A | Intervals: Distance |
| Intervals | B | Intervals: Time |
| Intervals | C | Intervals: Calorie |
| Intervals | D | Intervals: Variable |
| Intervals: Variable (type chooser) | B | Calorie entry screen |
| Intervals: Variable (type chooser) | C | Distance entry screen |
| Intervals: Variable (type chooser) | D | Time entry screen |
| Intervals: Variable (type chooser) | E | finish workout (after >= 1 interval confirmed) |

Note there is no "A" item on the Variable type chooser — only B/C/D
select a type, and E finishes.

Every other button on every one of these screens is invalid (pressing
it raises an error in the simulator, and would simply do nothing useful
on a real PM5).

## Entry screens

Every entry screen (single or fixed-interval) is a row of digit fields,
optionally followed by a rest sub-row of digit fields to its right.
Button semantics on an entry screen are uniform across all of them:

- **A** — cursor right one field
- **D** — cursor left one field
- **B** — +1 on the digit under the cursor
- **C** — -1 on the digit under the cursor
- **E** — confirm

Digits clamp at 0 and 9 and do **not** wrap around (pressing B on a 9 or
C on a 0 is an invalid press — nothing in the gold data ever needs
wraparound, so this has never been exercised against a real monitor;
see the evidence table below). Rest fields, when present, sit to the
right of the work fields, so the cursor always has to move right past
every work field before reaching rest.

| Screen | Fields (left to right) | Default value | Default cursor field |
|---|---|---|---|
| Single Distance | 10000s, 1000s, 100s, 10s, 1s (m) | 2000 m | 1000s digit |
| Single Time | hours, 10-min, min, 10-sec, sec | 30:00 | 10-minutes digit |
| Single Calorie | 100s, 10s, 1s (cal) | 50 cal | 10s digit |
| Intervals: Distance | 10000s, 1000s, 100s, 10s, 1s (m) + 10-min, min, 10-sec, sec (rest) | 500 m / 0:00 rest | 100s digit |
| Intervals: Time | hours, 10-min, min, 10-sec, sec + 10-min, min, 10-sec, sec (rest) | 1:00 / 0:00 rest | minutes digit |
| Intervals: Calorie | 100s, 10s, 1s (cal) + 10-min, min, 10-sec, sec (rest) | 50 cal / 0:00 rest | 10s digit |

The Intervals: Variable per-interval entry screens reuse these exact
same field layouts and defaults (Calorie -> Intervals: Calorie's
layout, Distance -> Intervals: Distance's, Time -> Intervals: Time's),
just reached via the type chooser instead of the Intervals chooser.

## Intervals: Variable rules

The Variable screen (Intervals -> D) works differently from the fixed
interval screens:

1. **Type is reselected before every interval**, even when it's the
   same type as the previous interval. Pressing E on an entry screen
   returns to the type chooser, not back to the entry screen — so
   starting interval 2 of a 5-interval Calorie ladder still requires
   pressing B (Calorie) again.
2. **Values are retained per type.** The *first* interval of a given
   type starts from that type's normal screen default (e.g. 50 cal for
   Calorie); every subsequent interval of the *same* type starts from
   whatever work/rest value was left on that type's screen after its
   previous interval, not the screen default.
3. **The cursor always resets** to that screen's default cursor
   position every time the entry screen is (re-)opened via a type
   letter, regardless of what value is retained.
4. **The last interval's rest is never meaningfully set.** The
   internal workout representation `pm5keys` compiles from (the
   WorkoutSpec, see `docs/SPEC.md`) doesn't record a rest value
   for the final interval, so `pm5keys` never emits a rest edit for it
   when compiling — whatever the screen happens to be holding (the
   type's default, or a value retained from an earlier interval of the
   same type) is left in place. This is a real field on the PM5, it
   just isn't information the compiler is responsible for filling in.
5. **One final E** — after the last interval's own confirming E, a
   second E (typically written fused as the sequence's trailing `2E`)
   finishes the whole workout.

Because the type-reselect press (rule 1) uses the same physical
button as that type's screen edits, and notation.md's
[canonical-form merging rule](notation.md#canonical-form-and-the-merging-rule)
doesn't know about screen boundaries, a
same-type reselect routinely fuses with the interval's own digit edits.
For example, the calorie ladder 50-40-30-20-10 gold sequence is:

```
B-3D-B-3A-2B-E-B-C-E-B-C-E-B-C-E-B-C-2E
```

Every `B-C-E` after the first interval is really [reselect Calorie
(B)]-[10s digit -1 (C)]-[confirm (E)], not a bare digit edit — it only
*looks* like one because the reselect press and the digit-edit press
happen to be different letters here and don't merge into a single
token. (When the reselect press *does* share a letter with the
following edit, e.g. selecting Distance (C) followed by more C presses
on the 100s digit, gold writes that as a single fused token like `6C`.)

Examples:

| Text | PM5 |
|---|---|
| 50 - 40 - 30 - 20 - 10 Cals with 2 minutes easy | B-3D-B-3A-2B-E-B-C-E-B-C-E-B-C-E-B-C-2E |

## Facts a rower will find surprising

### The interval count is never encoded

Nothing in the key sequence says how many intervals there are for a
workout with fixed (identical) work/rest on every interval — distance,
time, or calorie-based (`intervals_distance` / `intervals_time` /
`intervals_calorie` in the internal spec kind) — the PM5's
fixed-interval screens only ever
program *one* interval's work/rest values; the monitor itself repeats
it however many times you tell it separately (or run manually). Gold
confirms this directly: "4 x 1000m / 1 min easy" (RowErg and SkiErg,
2022-07-23) and "5 x 1000m / 1 min easy" (RowErg and SkiErg,
2022-08-06) press *identically*:

| Text | PM5 |
|---|---|
| 4 x 1000m / 1 min easy | B-2D-A-D-B-A-5C-4A-B-E |
| 5 x 1000m / 1 min easy | B-2D-A-D-B-A-5C-4A-B-E |

### Concept2 sometimes uses the Variable screen when the fixed screen would do

"10 x 1:40 / 20 seconds easy" (2024-06-26) and "4 x 1776m / 2 min easy"
(2024-07-04) are both workouts with identical work/rest on every
interval — exactly what the fixed interval screens (Intervals: Time /
Intervals: Distance) are for — but Concept2 programmed them through the
Variable screen instead, reselecting the type and re-entering the same
values on every interval:

- "10 x 1:40 / 20 seconds easy" gold:
  `B-4D-A-4B-4A-2B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-2E` (10 Time
  intervals of 100s/20s rest via Variable) versus the fixed-screen
  compile `B-2D-B-A-4B-4A-2B-E` (one Intervals: Time entry) — both
  program the same 100s-work/20s-rest interval body; `pm5keys`
  classifies this a `GOLD_VARIABLE` row (see the evidence table below)
  rather than a mismatch, because simulating gold's Variable sequence
  yields 10 intervals that all equal the fixed spec's work/rest.
- "4 x 1776m / 2 min easy" gold (RowErg and SkiErg):
  `B-3D-C-D-B-A-2B-A-7B-A-6B-2A-2B-E-C-E-C-E-C-2E` versus the
  fixed-screen compile `B-2D-A-D-B-A-2B-A-7B-A-6B-2A-2B-E` — same story,
  4 Distance intervals of 1776 m / 120 s rest each.

### The pyramid email typo

"5 min, 10 min, 15 min, 10 min, 5 min pyramid / 2 min easy"
(2022-11-28, and repeated on many later dates) is programmed through
the Variable screen with per-interval work, so its last leg's *work*
value is a real, meaningful field (unlike the *rest* field, which is
never meaningful on the last interval — see rule 4 above). Running the
gold sequence through the simulator shows the last leg is actually
**15:00**, not 5:00 as the title claims:

```
gold:     B-4D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-D-5B-2E
sim(gold): intervals = [300s, 600s, 900s, 600s, 900s]  (5:00, 10:00, 15:00, 10:00, 15:00)
```

Compiling the spec implied by the *title* (5:00, 10:00, 15:00, 10:00,
5:00 — a true pyramid, symmetric) instead produces:

```
compiled:      B-4D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-2D-C-A-5B-2E
sim(compiled): intervals = [300s, 600s, 900s, 600s, 300s]  (5:00, 10:00, 15:00, 10:00, 5:00)
```

The two sequences differ (`GOLD_MISMATCH` — see the evidence table),
and the difference is entirely explained by Concept2 having pressed one
extra B on the last leg of the *email/WOD-page instructions* — the
title's stated shape is the "true" pyramid, but the button sequence
gold actually publishes reproduces a workout whose last leg is 15
minutes, not 5. `pm5keys` reproduces the title's intended pyramid, not
this apparent typo.

### Single Time's default cursor is not where Interval Time's is

Single Time's entry screen defaults the cursor to the **10-minutes**
digit; Intervals: Time's entry screen defaults the cursor to the
**minutes** digit — one field to the right. This shows up directly in
gold:

| Sequence | Screen | Cursor detail |
|---|---|---|
| `B-D-B-D-B-A-3C-E` ("60 minutes") | Single Time | opens with the cursor on 10-minutes (the screen's default); D moves it *left* to hours first (B: 0->1), then A moves it back right to 10-minutes and 3xC zeroes that digit |
| `B-2D-3B-4A-2B-E` ("4 x 3 min / 2 min easy") | Intervals: Time | opens with the cursor already on minutes (one field right of Single Time's default); 2xB edits it directly (1->3) with zero cursor moves before the first digit edit |

### The evidence table

Counts below are computed directly from `data/spec_parsed.jsonl` by
workout kind (the internal spec's `kind` field; 116 gold rows total: 24
single distance, 3 single time, 1 single calorie, 32 fixed distance
intervals, 23 fixed time intervals, 4 fixed calorie intervals, 29
variable intervals):

| Screen / rule | Gold rows exercising it | Note |
|---|---|---|
| Single Distance | 24 | wide coverage, including the 10000 m five-digit case |
| Single Time | 3 | 30-minute default (x2) + 60-minute (hours digit, x1) |
| Single Time hours digit | 1 | only "60 minutes" (2022-11-06) touches the hours digit — a single row underwrites this whole field |
| Single Calorie | 1 | only "250 Calories" — the *entire* Single Calorie screen (layout, default, cursor) rests on one gold row |
| Intervals: Distance | 32 | wide coverage |
| Intervals: Time | 23 | wide coverage |
| Intervals: Calorie | 4 | narrowest of the fixed-interval screens, but > 1 |
| Intervals: Variable | 29 | wide coverage, including the calorie-ladder and pyramid cases above |
| Digits never wrap (0..9 clamp, no rollover) | 0 | **untested** — no gold row ever drives a digit to its clamp boundary in a way that would distinguish clamping from wraparound; this is an assumption, not an observed fact |

Per `compile_keys.py --verify`'s categorisation of all 116 rows: 108
EXACT, 4 EQUIVALENT (different button path, same resulting workout), 3
GOLD_VARIABLE (gold used the Variable screen for a fixed-shape workout,
per the "surprising facts" above), 1 GOLD_MISMATCH (the pyramid typo,
above). See `data/reports/compile_report.md` for the full per-row
report.

## Verifying on your own monitor

See [verification.md](verification.md) for how to check a `pm5keys`-
generated sequence against a real PM5 (pending: not yet pressed on
hardware).

## How this was derived

This model was reverse-engineered against 1,523 public Concept2 WOD
pages (`data/dataset.jsonl`'s unique `source_url` count), reduced to
116 unique `(title, pm5, spec)` gold rows
(`data/spec_parsed.jsonl`), using a hand-built simulator
(`pm5_model.py`) and compiler (`compile_keys.py`) rather than guesswork:
every rule above was checked against every gold row, not just a
representative sample. The result: 108/116 rows compile to gold's exact
button sequence, 4/116 compile to a different-but-equivalent sequence
(same resulting workout, different button path), 3/116 are cases where
gold itself used the Variable screen for a workout the fixed screens
could have programmed directly, and 1/116 is a gold data error (the
pyramid typo above) that `pm5keys` deliberately does not reproduce.
Separately, all 116/116 gold sequences round-trip through the simulator
(`pm5_model.run`) back to their originating spec, which is what
validates the *model* (as opposed to the *compiler*) against every row.
