# PM5 button-press notation

Concept2's [Workout of the Day (WOD)](https://www.concept2.com/training/wod)
pages describe how to program a workout into the PM5 monitor using a
compact key-sequence notation, e.g. `B-2D-5A-2B-E`. This document specifies
that notation and the grammar implemented by `pm5keys/keyseq.py`.

## Legend

Quoted verbatim from Concept2's WOD page
(<https://www.concept2.com/training/wod>):

> Starting from the Main Menu, "A" corresponds to the top gray button on
> the right, "B" corresponds to the second gray button on the right, and
> so on down through "E". Note: 4A, for example, means press the A
> button four times in succession.

## Physical layout

The PM5 has five gray buttons stacked vertically along the right edge of
the screen:

```
 [A]  <- top
 [B]
 [C]
 [D]
 [E]  <- bottom
```

Each button acts on whatever menu item or field is displayed on the
screen next to it at the time it is pressed — the same physical button
(e.g. "A") can mean something different at each step of a sequence,
depending on which menu is currently showing. For what each button
actually *does* on each screen (Main Menu, Select Workout, the entry
screens, etc.), see [pm5-model.md](pm5-model.md).

## Grammar

```
sequence = token ('-' token)*
token    = [count] letter
count    = positive integer   ; digits only, no leading '+' or '-', >= 1
letter   = 'A' | 'B' | 'C' | 'D' | 'E'
```

Notes:

- A count of 1 is always written with no leading number: `A`, not `1A`.
- No whitespace is permitted anywhere in a sequence.
- Tokens must not be empty: leading `-`, trailing `-`, and doubled `--`
  are all invalid, as are lowercase letters, letters outside A-E, and
  multi-letter tokens such as `AB`.

## Canonical form and the merging rule

The canonical form of a sequence is obtained by expanding it to a flat
list of individual button presses and then re-compressing that list into
tokens, merging adjacent runs of the same letter:

```
canonical(seq) = compress(expand(seq))
```

Because `expand` flattens counts into individual presses before
`compress` regroups them, two notations that describe the same physical
button presses collapse to the same canonical form even if written
differently. For example, `2B-B` and `3B` both expand to `["B", "B",
"B"]` and both canonicalise to `3B`. This is intentional: `2B-B` is not
a meaningfully different instruction from `3B`, just a differently
segmented way of writing three consecutive presses of B.

This merging rule also explains why menu-selection presses routinely
fuse, in written sequences, with the first press on an entry screen —
see [pm5-model.md](pm5-model.md)'s note on chooser/entry-screen fusion.

## Worked examples

### Example 1: `B-2D-5A-2B-E`

From the WOD "8 x 500m, 2 minutes rest":

| Token | Meaning              |
|-------|----------------------|
| `B`   | press B once         |
| `2D`  | press D twice        |
| `5A`  | press A five times   |
| `2B`  | press B twice        |
| `E`   | press E once         |

Expansion: `B, D, D, A, A, A, A, A, B, B, E` (11 presses).

Examples:

| Text | PM5 |
|---|---|
| 8 x 500m, 2 minutes rest | B-2D-5A-2B-E |

### Example 2: `2B-B` (canonicalisation)

Expansion: `B, B, B` (3 presses). Canonical form: `3B` — demonstrating
the merging rule above.

### Example 3: the long pyramid sequence

```
B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E
```

This sequence's canonical form equals itself (no adjacent same-letter
tokens are split across a '-' boundary that would let them merge). It
expands to 37 individual button presses, starting `B, D, D, D, D, A, A,
A, A, B, B, E, D, B, E, ...` and ending `..., D, C, E, D, C, E, E` (the
final `2E` token expanding to two adjacent `E` presses).

## Reading a `pm5keys --explain` trace

This notation only records *which* button is pressed and how many times
in a row — it says nothing about what each press actually does, because
that depends entirely on which PM5 screen is displayed at that point in
the sequence (Main Menu, workout type selection, interval entry, etc.).
`pm5keys --explain "<text>"` runs the sequence through the PM5 menu
simulator ([pm5-model.md](pm5-model.md)) and prints one line per press,
showing the screen the press happened on and what it did, e.g.:

```
$ pm5keys --llm none --explain "4 x 3 min / 2 min easy"
4 x 3 min / 2 min easy
PM5: B-2D-3B-4A-2B-E
B    Main Menu      : Select Workout
D    Select Workout : New Workout
D    New Workout    : Intervals
B    Intervals      : Time
2xB  Intervals: Time: time minutes digit +2 (now 3)
4xA  Intervals: Time: cursor right to rest minutes
2xB  Intervals: Time: rest minutes +2 (now 2)
E    Intervals: Time: confirm
```

Each line is `<press(es)>  <screen>: <action>`. Consecutive presses on
the same screen that share the same letter and whose actions differ only
in the trailing "(now N)" value or cursor destination are collapsed to
`<n>x<press>` — e.g. `2xB  Intervals: Time: time minutes digit +2 (now
3)` means B was pressed twice in a row on the Intervals: Time entry
screen, taking the minutes digit from 1 (the screen's default) to 3.
The final row's action is always `confirm` (single/fixed workouts) or,
for Intervals: Variable, `finish workout` on the last press.
