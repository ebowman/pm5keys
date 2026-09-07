# Verifying pm5keys against a real PM5

## Purpose

`pm5keys`'s menu model (`docs/pm5-model.md`, implemented in
[`pm5_model.py`](../src/pm5keys/pm5_model.py)) was reverse-engineered
entirely from Concept2's own published `(title, pm5, spec)` triples --
1,523 scraped WOD pages reduced to 116 unique gold rows. No step of
that process ever touched a physical PM5 monitor. That's a strong basis
for the *common* screens (Intervals: Distance and Intervals: Time each
have 20+ gold rows backing them), but two screens rest on a single
observed data point each: **Single Time's hours digit** (only "60
minutes" ever touches it) and the **entire Single Calorie screen**
(only "250 Calories" exercises it at all -- layout, default value, and
default cursor position all come from that one row). Separately, the
model assumes digit fields clamp at 0 and 9 rather than wrapping
around; no gold row ever drives a digit to its boundary, so this is an
assumption, not an observed fact. This checklist exists to close that
gap: press each of the following 11 sequences into a real PM5, by
hand, and record what the monitor actually shows.

## Instructions

1. Start from the **Main Menu** every time -- back all the way out
   between workouts (or power-cycle) rather than chaining sequences
   together, so each row is tested from a known state.
2. Press **exactly** the letters listed in the sequence column, in
   order, with no extra presses. `nX` means press button `X` `n`
   times in a row (e.g. `3B` = press B three times).
3. After the final `E`, compare what the monitor's screen shows
   against the "Expected final state" description for that row.
4. Before you start, note the firmware version shown under **More
   Options -> Utilities -> Product ID** (or wherever your PM5's menus
   actually surface it -- the exact path may differ by firmware
   version; look for a Product ID / firmware / device info screen)
   and record it in the Results block below.

## Summary table

| Text | PM5 |
|---|---|
| 2000m | B-D-A-E |
| 5000m time trial | B-D-A-3B-E |
| 60 minutes | B-D-B-D-B-A-3C-E |
| 250 Calories | B-D-C-D-2B-E |
| 8 x 500m, 2 minutes rest | B-2D-5A-2B-E |
| 12 x 250m / 45 sec easy | B-2D-A-3C-A-5B-4A-4B-A-5B-E |
| 4 x 2023m, 3 minutes rest. | B-2D-A-D-2B-A-5C-A-2B-A-3B-2A-3B-E |
| 10 x 1:40 / 20 seconds easy | B-2D-B-A-4B-4A-2B-E |
| 1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest | B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E |
| 2000/1500/1000/500m with three minutes rest | B-3D-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-E-6C-E-C-D-C-A-5B-2E |
| 10/20/30/40/50/60 Calories. 1 minute rest between intervals. | B-3D-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E |

## Results

- **Firmware:**
- **Date:**
- **Tester:**

## 1. 2000m

Command:

```
pm5keys --llm none --explain "2000m"
```

Sequence: `B-D-A-E`

Trace:

```
B  Main Menu      : Select Workout
D  Select Workout : New Workout
A  New Workout    : Distance
E  Single Distance: confirm
```

Expected final state: Single Distance screen showing a 2000m workout
programmed (the screen's own default value, confirmed unchanged), monitor
ready to start rowing 2000m.

- [ ] PASS  - [ ] FAIL  notes:

## 2. 5000m time trial

Command:

```
pm5keys --llm none --explain "5000m time trial"
```

Sequence: `B-D-A-3B-E`

Trace:

```
B    Main Menu      : Select Workout
D    Select Workout : New Workout
A    New Workout    : Distance
3xB  Single Distance: distance 1000s digit +3 (now 5)
E    Single Distance: confirm
```

Expected final state: Single Distance screen showing a 5000m workout
programmed, monitor ready to start rowing 5000m.

- [ ] PASS  - [ ] FAIL  notes:

## 3. 60 minutes (single-time hours digit: one gold row)

Command:

```
pm5keys --llm none --explain "60 minutes"
```

Sequence: `B-D-B-D-B-A-3C-E`

Trace:

```
B    Main Menu     : Select Workout
D    Select Workout: New Workout
B    New Workout   : Time
D    Single Time   : cursor left to time hours digit
B    Single Time   : time hours digit +1 (now 1)
A    Single Time   : cursor right to time 10-minutes digit
3xC  Single Time   : time 10-minutes digit -3 (now 0)
E    Single Time   : confirm
```

Expected final state: Single Time screen showing a 60:00 (1 hour)
workout programmed, monitor ready to row for 60 minutes. This is the
sole gold row backing the hours digit -- a mismatch here (e.g. the
monitor showing some other duration, or the hours digit behaving
differently than the tens-of-minutes digits) is plausible and should
be reported in detail.

- [ ] PASS  - [ ] FAIL  notes:

## 4. 250 Calories (single-calorie screen: one gold row)

Command:

```
pm5keys --llm none --explain "250 Calories"
```

Sequence: `B-D-C-D-2B-E`

Trace:

```
B    Main Menu     : Select Workout
D    Select Workout: New Workout
C    New Workout   : Calorie
D    Single Calorie: cursor left to calories 100s digit
2xB  Single Calorie: calories 100s digit +2 (now 2)
E    Single Calorie: confirm
```

Expected final state: Single Calorie screen showing a 250-calorie
workout programmed, monitor ready to row for 250 calories. The entire
Single Calorie screen model (field layout, default value, default
cursor position) rests on this one gold row -- a mismatch here (wrong
final calorie count, wrong field the cursor started on, etc.) is
plausible and should be reported in detail.

- [ ] PASS  - [ ] FAIL  notes:

## 5. 8 x 500m, 2 minutes rest

Command:

```
pm5keys --llm none --explain "8 x 500m, 2 minutes rest"
```

Sequence: `B-2D-5A-2B-E`

Trace:

```
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
A    Intervals          : Distance
4xA  Intervals: Distance: cursor right to rest minutes
2xB  Intervals: Distance: rest minutes +2 (now 2)
E    Intervals: Distance: confirm
```

Expected final state: Intervals: Distance screen showing 500m work,
2:00 rest, ready to start (the monitor itself repeats the interval as
many times as you tell it separately, or as you row manually -- the
"x8" count is not encoded in the button sequence at all).

- [ ] PASS  - [ ] FAIL  notes:

## 6. 12 x 250m / 45 sec easy (rest seconds digits)

Command:

```
pm5keys --llm none --explain "12 x 250m / 45 sec easy"
```

Sequence: `B-2D-A-3C-A-5B-4A-4B-A-5B-E`

Trace:

```
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
A    Intervals          : Distance
3xC  Intervals: Distance: distance 100s digit -3 (now 2)
A    Intervals: Distance: cursor right to distance 10s digit
5xB  Intervals: Distance: distance 10s digit +5 (now 5)
4xA  Intervals: Distance: cursor right to rest 10-seconds
4xB  Intervals: Distance: rest 10-seconds +4 (now 4)
A    Intervals: Distance: cursor right to rest seconds
5xB  Intervals: Distance: rest seconds +5 (now 5)
E    Intervals: Distance: confirm
```

Expected final state: Intervals: Distance screen showing 250m work,
0:45 rest, ready to start.

- [ ] PASS  - [ ] FAIL  notes:

## 7. 4 x 2023m, 3 minutes rest. (4-digit distance)

Command:

```
pm5keys --llm none --explain "4 x 2023m, 3 minutes rest."
```

Sequence: `B-2D-A-D-2B-A-5C-A-2B-A-3B-2A-3B-E`

Trace:

```
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
A    Intervals          : Distance
D    Intervals: Distance: cursor left to distance 1000s digit
2xB  Intervals: Distance: distance 1000s digit +2 (now 2)
A    Intervals: Distance: cursor right to distance 100s digit
5xC  Intervals: Distance: distance 100s digit -5 (now 0)
A    Intervals: Distance: cursor right to distance 10s digit
2xB  Intervals: Distance: distance 10s digit +2 (now 2)
A    Intervals: Distance: cursor right to distance 1s digit
3xB  Intervals: Distance: distance 1s digit +3 (now 3)
2xA  Intervals: Distance: cursor right to rest minutes
3xB  Intervals: Distance: rest minutes +3 (now 3)
E    Intervals: Distance: confirm
```

Expected final state: Intervals: Distance screen showing 2023m work,
3:00 rest, ready to start.

- [ ] PASS  - [ ] FAIL  notes:

## 8. 10 x 1:40 / 20 seconds easy (fixed time screen where Concept2 used the variable screen)

Command:

```
pm5keys --llm none --explain "10 x 1:40 / 20 seconds easy"
```

Sequence: `B-2D-B-A-4B-4A-2B-E`

Trace:

```
B    Main Menu      : Select Workout
D    Select Workout : New Workout
D    New Workout    : Intervals
B    Intervals      : Time
A    Intervals: Time: cursor right to time 10-seconds digit
4xB  Intervals: Time: time 10-seconds digit +4 (now 4)
4xA  Intervals: Time: cursor right to rest 10-seconds
2xB  Intervals: Time: rest 10-seconds +2 (now 2)
E    Intervals: Time: confirm
```

Expected final state: Intervals: Time screen showing 1:40 work, 0:20
rest, ready to start. Concept2's own published sequence for this
workout instead reselects and re-enters the same values 10 times
through the Variable screen (see docs/pm5-model.md's "Concept2
sometimes uses the Variable screen when the fixed screen would do");
`pm5keys` compiles the simpler fixed-screen path shown here, and both
paths should produce the same programmed interval body on the
monitor.

- [ ] PASS  - [ ] FAIL  notes:

## 9. 1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest (variable time)

Command:

```
pm5keys --llm none --explain "1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest"
```

Sequence: `B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E`

Trace:

```
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
D    Intervals          : Variable
D    Intervals: Variable: Time
4xA  Intervals: Time    : cursor right to rest minutes
2xB  Intervals: Time    : rest minutes +2 (now 2)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
B    Intervals: Time    : time minutes digit +1 (now 2)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
B    Intervals: Time    : time minutes digit +1 (now 3)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
B    Intervals: Time    : time minutes digit +1 (now 4)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
B    Intervals: Time    : time minutes digit +1 (now 5)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
C    Intervals: Time    : time minutes digit -1 (now 4)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
C    Intervals: Time    : time minutes digit -1 (now 3)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
C    Intervals: Time    : time minutes digit -1 (now 2)
E    Intervals: Time    : confirm
D    Intervals: Variable: Time
C    Intervals: Time    : time minutes digit -1 (now 1)
E    Intervals: Time    : confirm
E    Intervals: Variable: finish workout
```

Expected final state: workout programmed as 9 Variable Time intervals
of 1:00, 2:00, 3:00, 4:00, 5:00, 4:00, 3:00, 2:00, 1:00, each with 2:00
rest, monitor ready to start the first (1:00) interval. Check that the
monitor's interval list/summary shows all 9 legs with the pyramid
shape intact, not collapsed or truncated.

- [ ] PASS  - [ ] FAIL  notes:

## 10. 2000/1500/1000/500m with three minutes rest (variable distance, retained values)

Command:

```
pm5keys --llm none --explain "2000/1500/1000/500m with three minutes rest"
```

Sequence: `B-3D-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-E-6C-E-C-D-C-A-5B-2E`

Trace:

```
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
D    Intervals          : Variable
C    Intervals: Variable: Distance
D    Intervals: Distance: cursor left to distance 1000s digit
2xB  Intervals: Distance: distance 1000s digit +2 (now 2)
A    Intervals: Distance: cursor right to distance 100s digit
5xC  Intervals: Distance: distance 100s digit -5 (now 0)
4xA  Intervals: Distance: cursor right to rest minutes
3xB  Intervals: Distance: rest minutes +3 (now 3)
E    Intervals: Distance: confirm
C    Intervals: Variable: Distance
D    Intervals: Distance: cursor left to distance 1000s digit
C    Intervals: Distance: distance 1000s digit -1 (now 1)
A    Intervals: Distance: cursor right to distance 100s digit
5xB  Intervals: Distance: distance 100s digit +5 (now 5)
E    Intervals: Distance: confirm
C    Intervals: Variable: Distance
5xC  Intervals: Distance: distance 100s digit -5 (now 0)
E    Intervals: Distance: confirm
C    Intervals: Variable: Distance
D    Intervals: Distance: cursor left to distance 1000s digit
C    Intervals: Distance: distance 1000s digit -1 (now 0)
A    Intervals: Distance: cursor right to distance 100s digit
5xB  Intervals: Distance: distance 100s digit +5 (now 5)
E    Intervals: Distance: confirm
E    Intervals: Variable: finish workout
```

Expected final state: workout programmed as 4 Variable Distance
intervals of 2000m, 1500m, 1000m, 500m, each with 3:00 rest, monitor
ready to start the first (2000m) interval. Pay particular attention to
whether each interval's rest value actually reads 3:00 on the monitor
-- this exercises the model's claim that the Variable screen *retains*
the previous interval's rest value across reselections of the same
type (here every interval is Distance, so the 3:00 rest entered on
interval 1 should still be showing, unedited, on intervals 2-4).

- [ ] PASS  - [ ] FAIL  notes:

## 11. 10/20/30/40/50/60 Calories. 1 minute rest between intervals. (variable calorie)

Command:

```
pm5keys --llm none --explain "10/20/30/40/50/60 Calories. 1 minute rest between intervals."
```

Sequence: `B-3D-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E`

Trace:

```
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
D    Intervals          : Variable
B    Intervals: Variable: Calorie
4xC  Intervals: Calorie : calories 10s digit -4 (now 1)
3xA  Intervals: Calorie : cursor right to rest minutes
B    Intervals: Calorie : rest minutes +1 (now 1)
E    Intervals: Calorie : confirm
B    Intervals: Variable: Calorie
B    Intervals: Calorie : calories 10s digit +1 (now 2)
E    Intervals: Calorie : confirm
B    Intervals: Variable: Calorie
B    Intervals: Calorie : calories 10s digit +1 (now 3)
E    Intervals: Calorie : confirm
B    Intervals: Variable: Calorie
B    Intervals: Calorie : calories 10s digit +1 (now 4)
E    Intervals: Calorie : confirm
B    Intervals: Variable: Calorie
B    Intervals: Calorie : calories 10s digit +1 (now 5)
E    Intervals: Calorie : confirm
B    Intervals: Variable: Calorie
B    Intervals: Calorie : calories 10s digit +1 (now 6)
E    Intervals: Calorie : confirm
E    Intervals: Variable: finish workout
```

Expected final state: workout programmed as 6 Variable Calorie
intervals of 10, 20, 30, 40, 50, 60 calories, each with 1:00 rest,
monitor ready to start the first (10-calorie) interval.

- [ ] PASS  - [ ] FAIL  notes:

## PM3/PM4

`pm5keys`'s PM3/PM4 model (`docs/pm3-model.md`) was reverse-engineered
the same way as the PM5 model above -- entirely from Concept2's own
published `pm34` gold column, never touching physical hardware. The
same "press it by hand and compare" caveat applies; the three
sequences below are worth spot-checking on a real PM3 or PM4 first,
since they exercise both of PM3/PM4's differences from PM5 (the flat
New Workout chooser and, for the pyramid, the Intervals: Variable
screen reached directly by a different letter than on PM5):

| Text | PM3/PM4 |
|---|---|
| 8 x 500m, 2 minutes rest | B-D-C-4A-2B-E |
| 4 x 3 min / 2 min easy | B-2D-2B-4A-2B-E |
| 1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest | B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E |

Generate any of these yourself with `--monitor pm3` (or `pm4`, an
alias):

```
pm5keys --llm none --monitor pm3 "8 x 500m, 2 minutes rest"
```

## If something fails

If any row's actual monitor screen doesn't match its "Expected final
state" description, please file an issue
(<https://github.com/ericbowman/pm5keys/issues>) including:

- which workout (its number and text above)
- the exact button sequence you pressed
- what the screen actually showed (work value, rest value, cursor
  position, interval count -- whatever's relevant)
- the PM5 firmware version recorded in the Results block above

A failure on one (or both) of the two thin-evidence screens -- **60
minutes** (Single Time hours digit) or **250 Calories** (the entire
Single Calorie screen) -- is the most likely outcome of this
checklist, since each rests on a single gold data point rather than
broad corpus coverage; see docs/pm5-model.md's evidence table for
details. A failure on any other row would be more surprising and
worth investigating carefully.
