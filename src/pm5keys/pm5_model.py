#!/usr/bin/env python3
"""A simulator of the PM5 monitor's menu/entry-screen state machine.

This module answers the question keyseq.py explicitly leaves open:
given a sequence of button presses starting from the Main Menu, what
workout ends up programmed? PM5.press(key) advances one physical
button press; PM5.run(seq) expands a PM5_KEYS.md-notation sequence
(via keyseq.expand) and interprets it into a WorkoutSpec-shaped dict
(see docs/SPEC.md).

Model summary (all of this was reverse-engineered against every gold
(title, pm5, spec) row in spec_parsed.jsonl -- see "Deviations
from the hand-derived hypothesis" below for the one non-obvious
correction):

Main Menu -> B (Select Workout) -> D (New Workout) -> a chooser
screen with four items, A/B/C/D:

    A = Single Distance      B = Single Time
    C = Single Calorie       D = Intervals menu

The Intervals menu is itself a four-item chooser, A/B/C/D:

    A = Intervals: Distance  B = Intervals: Time
    C = Intervals: Calorie   D = Intervals: Variable

Machine (rower/skierg/bikeerg/all) never changes any key; a BikeErg
distance override is already baked into the spec's numeric work
values by the time this module sees them. The FIXED interval COUNT
is never encoded in the key sequence at all -- gold confirms this
(4x1000/r60 and 5x1000/r60 press identically; PM5_KEYS.md's own
worked example, 8x500m/r120, is `B-2D-5A-2B-E` with no count
information anywhere).

Entry screens
-------------
Every entry screen (single or fixed-interval) is a row of digit
fields, optionally followed by a rest sub-row of digit fields to its
right. A = cursor right one field, D = cursor left one field, B = +1
on the field under the cursor, C = -1 on the field under the cursor
(digits clamp 0..9, no wraparound -- nothing in the gold data needs
wraparound). E = confirm/advance.

    Single Distance    [10000s,1000s,100s,10s,1s]                default 2000m,  cursor 1000s (idx1)
    Single Time         [hours,10min,min,10s,s]                  default 30:00,  cursor 10min (idx1)
    Single Calorie       [100s,10s,1s]                           default 50,     cursor 10s   (idx1)
    Intervals: Distance [10000s,1000s,100s,10s,1s]+[10min,min,10s,s]  default 500m/0:00,  cursor 100s (idx2)
    Intervals: Time      [hours,10min,min,10s,s]+[10min,min,10s,s]   default 1:00/0:00,  cursor min  (idx2)
    Intervals: Calorie    [100s,10s,1s]+[10min,min,10s,s]         default 50/0:00,   cursor 10s  (idx1)

These field layouts and defaults reproduce, byte for byte, every
gold single/fixed-interval sequence in spec_parsed.jsonl, e.g.:
    Single Distance 2000  -> B-D-A-E        (no change: default already 2000)
    Single Distance 5000  -> B-D-A-3B-E
    Single Distance 10000 -> B-D-A-D-B-A-2C-E
    Single Time 30:00     -> B-D-B-E
    Single Time 60:00     -> B-D-B-D-B-A-3C-E
    Single Calorie 250    -> B-D-C-D-2B-E
    Intervals:Distance 500/2:00  -> B-2D-5A-2B-E
    Intervals:Time 3:00/2:00     -> B-2D-3B-4A-2B-E
    Intervals:Calorie 20/0:20    -> B-2D-4C-4A-2B-E

The Main-Menu-chooser presses (A/B/C/D selecting Single
Distance/Time/Calorie/Intervals, and the Intervals-menu A/B/C/D
selecting Distance/Time/Calorie/Variable) use the *same physical
buttons* as the entry-screen actions, and keyseq's canonical-form
merging rule (adjacent same-letter runs collapse across '-'
boundaries) does not know about screen transitions. So a chooser
selection press routinely fuses, in the written sequence, with the
entry screen's first cursor-move/increment press on the same letter
-- e.g. selecting Intervals:Distance is "A", and if the entry screen
then needs 4 more A presses to reach the field to edit, gold writes
this as a single "5A" token, not "A-4A". This module reproduces that
by simulating individual presses and never special-casing screen
boundaries; the merging is a natural side effect of canonical
sequence notation, not something pm5_model has to implement
specially.

Intervals: Variable
--------------------
Selecting D from the Intervals menu reaches a per-interval type
chooser: B = Calorie, C = Distance, D = Time (there is no A item on
this screen). Pressing a type letter opens that type's entry screen
(the same field layout/defaults as the corresponding fixed-interval
screen above). Pressing E on that entry screen confirms the interval
and returns to the type chooser -- not to the entry screen -- so
starting the *next* interval always requires pressing a type letter
again, even when it is the same type as before (this, too, routinely
fuses with the following field edits under canonical merging, e.g.
gold's "6C" = re-selecting Distance (C) plus 5 more C presses on the
100s digit). Pressing E a second time in a row (rendered "2E" at the
end of a sequence) after the last interval's confirmation finishes
the whole workout.

Within Intervals: Variable, an interval's WORK and REST *values* are
retained from the previous interval of the *same type* (the first
interval of a given type starts from that screen's normal default),
but the CURSOR always resets to that screen's default position when
the entry screen is (re-)opened via a type-letter press. The last
interval's rest is a real field on the PM5 -- the spec's rest_s: 0 on
the last variable interval is simply "not the WorkoutSpec compiler's
job to represent," per SPEC.md -- but nothing about the PM5 model
itself needs to special-case it; run()/explain() report whatever
value that field is left holding (typically retained from the
previous interval), and same_workout() (in compile_keys.py) is what
ignores it during comparison.

Deviations from the hand-derived hypothesis
--------------------------------------------
The hypothesis handed into this module was correct on every point
checked against gold except that it described the Intervals:Variable
per-interval type chooser as reappearing implicitly, without
spelling out that re-selecting the type is a *real, mandatory* key
press every single interval (even same-type back-to-back) that
merges with subsequent presses under canonical notation -- e.g. the
calorie ladder 50-40-30-20-10 gold is
`B-3D-B-3A-2B-E-B-C-E-B-C-E-B-C-E-B-C-2E`: every "B-C-E" after the
first interval is [reselect Calorie]-[10s digit -1]-[confirm], not a
bare digit edit. Once that was made explicit the entire gold corpus
(116 rows) is reproduced by a single, uniform state machine with no
per-kind special cases. No other deviation was needed; every numeric
field layout, default value, and default cursor position in the
hypothesis reproduced gold exactly on inspection (see the module-level
GOLD_EXAMPLES list below, each of which this module's tests exercise).

CLI: none. See compile_keys.py for the --verify CLI that exercises
this module against spec_parsed.jsonl.
"""

from __future__ import annotations

from . import keyseq


# ---------------------------------------------------------------------------
# Screen field layouts
# ---------------------------------------------------------------------------

# Each screen is described by:
#   work_fields: list of (place_value, ) for the work digit row, most
#                significant first, e.g. distance = [10000,1000,100,10,1]
#   rest_fields: list of place values for the rest digit row (or None if
#                this screen has no rest row), e.g. [600,60,10,1] (10min,
#                min,10s,s)
#   default_work: int, the value the work row starts at
#   default_rest: int, the value the rest row starts at (0 if present)
#   default_cursor: index into the combined field list (work_fields +
#                   rest_fields) where the cursor starts
#   unit: 'distance_m' | 'time_s' | 'calories' -- which WorkoutSpec work
#         key this screen edits

_DIST_WORK = [10000, 1000, 100, 10, 1]
_TIME_WORK = [3600, 600, 60, 10, 1]  # hours,10min,min,10s,s
_CAL_WORK = [100, 10, 1]
_REST_FIELDS = [600, 60, 10, 1]  # 10min,min,10s,s


class _Screen:
    def __init__(self, unit, work_fields, default_work, has_rest, default_rest, default_cursor):
        self.unit = unit
        self.work_fields = work_fields
        self.default_work = default_work
        self.has_rest = has_rest
        self.rest_fields = _REST_FIELDS if has_rest else []
        self.default_rest = default_rest
        self.default_cursor = default_cursor

    @property
    def fields(self):
        return self.work_fields + self.rest_fields

    @property
    def n_work_fields(self):
        return len(self.work_fields)


SINGLE_DISTANCE = _Screen("distance_m", _DIST_WORK, 2000, False, 0, 1)
SINGLE_TIME = _Screen("time_s", _TIME_WORK, 1800, False, 0, 1)
SINGLE_CALORIE = _Screen("calories", _CAL_WORK, 50, False, 0, 1)

INTERVALS_DISTANCE = _Screen("distance_m", _DIST_WORK, 500, True, 0, 2)
INTERVALS_TIME = _Screen("time_s", _TIME_WORK, 60, True, 0, 2)
INTERVALS_CALORIE = _Screen("calories", _CAL_WORK, 50, True, 0, 1)

# Human-readable screen names, keyed by id() of the _Screen singletons
# above -- used by explain() for both the menu-chooser labels and the
# entry-screen labels (an entry screen's name is the same "workout
# screen name" whether reached via the fixed chooser or the Variable
# type chooser).
_SCREEN_NAME = {
    id(SINGLE_DISTANCE): "Single Distance",
    id(SINGLE_TIME): "Single Time",
    id(SINGLE_CALORIE): "Single Calorie",
    id(INTERVALS_DISTANCE): "Intervals: Distance",
    id(INTERVALS_TIME): "Intervals: Time",
    id(INTERVALS_CALORIE): "Intervals: Calorie",
}

# Human-readable field names, in field-index order, per screen (work
# fields followed by rest fields when the screen has a rest row). Work
# fields (distance/time/calories) are named "... digit" (e.g. "distance
# 100s digit"); rest fields are named without the word "digit" (e.g.
# "rest minutes") to match Concept2's own labelling of the rest row.
_DIST_FIELD_NAMES = [
    "distance 10000s digit",
    "distance 1000s digit",
    "distance 100s digit",
    "distance 10s digit",
    "distance 1s digit",
]
_TIME_FIELD_NAMES = [
    "time hours digit",
    "time 10-minutes digit",
    "time minutes digit",
    "time 10-seconds digit",
    "time seconds digit",
]
_CAL_FIELD_NAMES = ["calories 100s digit", "calories 10s digit", "calories 1s digit"]
_REST_FIELD_NAMES = ["rest 10-minutes", "rest minutes", "rest 10-seconds", "rest seconds"]

_WORK_FIELD_NAMES = {
    id(SINGLE_DISTANCE): _DIST_FIELD_NAMES,
    id(SINGLE_TIME): _TIME_FIELD_NAMES,
    id(SINGLE_CALORIE): _CAL_FIELD_NAMES,
    id(INTERVALS_DISTANCE): _DIST_FIELD_NAMES,
    id(INTERVALS_TIME): _TIME_FIELD_NAMES,
    id(INTERVALS_CALORIE): _CAL_FIELD_NAMES,
}


def _field_names(screen) -> list:
    names = list(_WORK_FIELD_NAMES[id(screen)])
    if screen.has_rest:
        names = names + _REST_FIELD_NAMES
    return names


_FIXED_KIND_FOR_UNIT = {
    "distance_m": "intervals_distance",
    "time_s": "intervals_time",
    "calories": "intervals_calorie",
}
_SINGLE_KIND_FOR_UNIT = {
    "distance_m": "single_distance",
    "time_s": "single_time",
    "calories": "single_calorie",
}


def _digits_to_value(fields, digit_values):
    total = 0
    for place, dv in zip(fields, digit_values):
        total += place * dv
    return total


def _value_to_digits(fields, value):
    digits = []
    remaining = value
    for i, place in enumerate(fields):
        if i == len(fields) - 1:
            d = remaining // place if place else 0
        else:
            d = remaining // place
        digits.append(d)
        remaining -= d * place
    return digits


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

# Top-level menu states.
_S_MAIN = "main"
_S_SELECT_WORKOUT = "select_workout"  # after B (Select Workout); D = New Workout
_S_NEW_WORKOUT_CHOOSER = "new_workout_chooser"  # A/B/C/D after B-D
_S_INTERVALS_CHOOSER = "intervals_chooser"  # A/B/C/D after B-D-D
_S_VARIABLE_TYPE_CHOOSER = "variable_type_chooser"  # after B-D-D-D
_S_ENTRY = "entry"  # a digit-editing screen (single/fixed/variable-interval)
_S_DONE = "done"  # workout fully programmed (after the final E)

_VARIABLE_TYPE_LETTERS = {"B": "calories", "C": "distance_m", "D": "time_s"}


class PM5:
    """A simulator of the PM5's menu/entry-screen state machine, starting
    from the Main Menu. press(key) advances exactly one physical button
    press ('A'..'E'); raises ValueError on an impossible press (unknown
    key, cursor past a field-row end, or a digit that would go out of
    0..9 range).
    """

    def __init__(self):
        self.state = _S_MAIN
        self.screen = None  # current _Screen, once on an entry screen
        self.cursor = 0
        self.digits = []  # current field digit values (work + rest)
        # Retained per-type work/rest for Intervals: Variable, keyed by
        # WorkoutSpec unit ('distance_m'/'time_s'/'calories') -> (work_value,
        # rest_value). Populated lazily with each type's screen default the
        # first time that type is used.
        self._variable_retained = {}
        self._variable_type = None  # unit of the entry screen currently open
        self.result = None  # filled in once _S_DONE is reached

        # For fixed-kind singles/intervals.
        self._fixed_kind = None
        # For variable intervals: list of {"work": {...}, "rest_s": int}
        self._variable_intervals = []

    # -- public API ---------------------------------------------------

    def press(self, key: str) -> None:
        if key not in "ABCDE":
            raise ValueError(f"unknown key: {key!r}")

        handler = getattr(self, f"_press_{self.state}", None)
        if handler is None:
            raise ValueError(f"no presses are valid in state {self.state!r}")
        handler(key)

    def run(self, seq: str) -> dict:
        """Expand and execute a PM5_KEYS.md sequence from the Main Menu;
        return the resulting workout as a WorkoutSpec-like dict (kind,
        work/rest_s or intervals; count omitted; machine 'all')."""
        for key in keyseq.expand(seq):
            self.press(key)
        if self.state != _S_DONE:
            raise ValueError(f"sequence ended in state {self.state!r}, workout incomplete")
        return self.result

    def explain(self, seq: str) -> list:
        """Like run(), but returns a list of (press, screen, action)
        human-readable trace tuples instead of (only) the final result.
        Each element: (press:str, screen:str, action:str)."""
        trace = []
        for key in keyseq.expand(seq):
            screen_before = self._describe_screen()
            action = self._press_and_describe(key)
            trace.append((key, screen_before, action))
        return trace

    # -- internal: description helpers for explain() -------------------

    def _describe_screen(self) -> str:
        if self.state == _S_MAIN:
            return "Main Menu"
        if self.state == _S_SELECT_WORKOUT:
            return "Select Workout"
        if self.state == _S_NEW_WORKOUT_CHOOSER:
            return "New Workout"
        if self.state == _S_INTERVALS_CHOOSER:
            return "Intervals"
        if self.state == _S_VARIABLE_TYPE_CHOOSER:
            return "Intervals: Variable"
        if self.state == _S_ENTRY:
            return _SCREEN_NAME[id(self.screen)]
        if self.state == _S_DONE:
            return "done"
        return self.state

    def _press_and_describe(self, key: str) -> str:
        state_before = self.state
        cursor_before = self.cursor
        screen_before = self.screen
        self.press(key)

        if state_before == _S_ENTRY and self.state == _S_ENTRY:
            field_names = _field_names(screen_before)
            if self.cursor != cursor_before:
                direction = "right" if self.cursor > cursor_before else "left"
                destination = field_names[self.cursor]
                return f"cursor {direction} to {destination}"
            field_name = field_names[cursor_before]
            sign = "+1" if key == "B" else "-1"
            return f"{field_name} {sign} (now {self.digits[cursor_before]})"

        if state_before == _S_ENTRY and self.state != _S_ENTRY:
            return "confirm"

        if state_before == _S_VARIABLE_TYPE_CHOOSER and key == "E":
            return "finish workout"

        if state_before == _S_MAIN:
            return "Select Workout"
        if state_before == _S_SELECT_WORKOUT:
            return "New Workout"
        if state_before == _S_NEW_WORKOUT_CHOOSER:
            return {"A": "Distance", "B": "Time", "C": "Calorie", "D": "Intervals"}[key]
        if state_before == _S_INTERVALS_CHOOSER:
            return {"A": "Distance", "B": "Time", "C": "Calorie", "D": "Variable"}[key]
        if state_before == _S_VARIABLE_TYPE_CHOOSER:
            return {"B": "Calorie", "C": "Distance", "D": "Time"}[key]

        return f"{state_before} -> {self.state}"

    # -- state handlers -------------------------------------------------

    def _press_main(self, key):
        if key != "B":
            raise ValueError(f"Main Menu: only B (Select Workout) is valid, got {key!r}")
        self.state = _S_SELECT_WORKOUT

    def _press_select_workout(self, key):
        if key != "D":
            raise ValueError(f"Select Workout: only D (New Workout) is valid, got {key!r}")
        self.state = _S_NEW_WORKOUT_CHOOSER

    def _press_new_workout_chooser(self, key):
        if key == "A":
            self._enter_screen(SINGLE_DISTANCE)
        elif key == "B":
            self._enter_screen(SINGLE_TIME)
        elif key == "C":
            self._enter_screen(SINGLE_CALORIE)
        elif key == "D":
            self.state = _S_INTERVALS_CHOOSER
        else:
            raise ValueError(f"New Workout chooser: invalid key {key!r}")

    def _press_intervals_chooser(self, key):
        if key == "A":
            self._enter_screen(INTERVALS_DISTANCE)
        elif key == "B":
            self._enter_screen(INTERVALS_TIME)
        elif key == "C":
            self._enter_screen(INTERVALS_CALORIE)
        elif key == "D":
            self.state = _S_VARIABLE_TYPE_CHOOSER
        else:
            raise ValueError(f"Intervals chooser: invalid key {key!r}")

    def _press_variable_type_chooser(self, key):
        if key == "E":
            # E on the type chooser finishes the whole variable workout --
            # valid only once at least one interval has been confirmed.
            if not self._variable_intervals:
                raise ValueError(
                    "Intervals: Variable type chooser: E (finish) pressed "
                    "before any interval was confirmed"
                )
            self.result = {
                "machine": "all",
                "kind": "intervals_variable",
                "intervals": self._variable_intervals,
                "notes": "",
            }
            self.state = _S_DONE
            return

        if key not in _VARIABLE_TYPE_LETTERS:
            raise ValueError(
                f"Intervals: Variable type chooser: invalid key {key!r} "
                "(must be B=Calorie, C=Distance, D=Time, or E=finish)"
            )
        unit = _VARIABLE_TYPE_LETTERS[key]
        screen = {
            "distance_m": INTERVALS_DISTANCE,
            "time_s": INTERVALS_TIME,
            "calories": INTERVALS_CALORIE,
        }[unit]
        self._variable_type = unit
        if unit in self._variable_retained:
            work_val, rest_val = self._variable_retained[unit]
        else:
            work_val, rest_val = screen.default_work, screen.default_rest
        self._enter_screen(screen, work_val=work_val, rest_val=rest_val)

    def _enter_screen(self, screen, work_val=None, rest_val=None):
        self.screen = screen
        self.state = _S_ENTRY
        self.cursor = screen.default_cursor
        if work_val is None:
            work_val = screen.default_work
        if rest_val is None:
            rest_val = screen.default_rest
        work_digits = _value_to_digits(screen.work_fields, work_val)
        rest_digits = _value_to_digits(screen.rest_fields, rest_val) if screen.has_rest else []
        self.digits = work_digits + rest_digits

    def _press_entry(self, key):
        fields = self.screen.fields
        if key == "A":
            if self.cursor >= len(fields) - 1:
                raise ValueError("cursor already at rightmost field")
            self.cursor += 1
        elif key == "D":
            if self.cursor <= 0:
                raise ValueError("cursor already at leftmost field")
            self.cursor -= 1
        elif key == "B":
            if self.digits[self.cursor] >= 9:
                raise ValueError(f"digit at field {self.cursor} already at 9")
            self.digits[self.cursor] += 1
        elif key == "C":
            if self.digits[self.cursor] <= 0:
                raise ValueError(f"digit at field {self.cursor} already at 0")
            self.digits[self.cursor] -= 1
        elif key == "E":
            self._confirm_entry()
        else:
            raise ValueError(f"entry screen: invalid key {key!r}")

    def _confirm_entry(self):
        screen = self.screen
        work_digits = self.digits[: screen.n_work_fields]
        work_val = _digits_to_value(screen.work_fields, work_digits)
        rest_val = 0
        if screen.has_rest:
            rest_digits = self.digits[screen.n_work_fields :]
            rest_val = _digits_to_value(screen.rest_fields, rest_digits)

        if self._variable_type is not None:
            # Intervals: Variable -- record this interval, retain
            # work/rest for the next interval of the same type, and go
            # back to the type chooser (not the entry screen).
            unit = self._variable_type
            self._variable_retained[unit] = (work_val, rest_val)
            self._variable_intervals.append({"work": {unit: work_val}, "rest_s": rest_val})
            self._variable_type = None
            self.state = _S_VARIABLE_TYPE_CHOOSER
        else:
            # Single or fixed interval: this screen's E always finishes
            # the whole workout.
            unit = screen.unit
            if screen.has_rest:
                kind = _FIXED_KIND_FOR_UNIT[unit]
                self.result = {
                    "machine": "all",
                    "kind": kind,
                    "work": {unit: work_val},
                    "rest_s": rest_val,
                    "notes": "",
                }
            else:
                kind = _SINGLE_KIND_FOR_UNIT[unit]
                self.result = {
                    "machine": "all",
                    "kind": kind,
                    "work": {unit: work_val},
                    "notes": "",
                }
            self.state = _S_DONE

    def _press_done(self, key):
        raise ValueError("workout already complete; no further presses valid")


def run(seq: str) -> dict:
    """Convenience wrapper: run a fresh PM5 over seq and return the
    resulting workout dict."""
    return PM5().run(seq)


def explain(seq: str) -> list:
    """Convenience wrapper: explain a fresh PM5's trace over seq."""
    return PM5().explain(seq)


# ---------------------------------------------------------------------------
# Gold examples the model above was derived from (see docstring). Kept here
# as data so tests can exercise them without duplicating literals.
# ---------------------------------------------------------------------------

GOLD_EXAMPLES = [
    (
        "B-D-A-E",
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 2000}, "notes": ""},
    ),
    (
        "B-D-A-3B-E",
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""},
    ),
    (
        "B-D-A-C-E",
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 1000}, "notes": ""},
    ),
    (
        "B-D-A-D-B-A-2C-E",
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 10000}, "notes": ""},
    ),
    (
        "B-D-A-B-A-3B-A-3B-A-3B-E",
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 3333}, "notes": ""},
    ),
    (
        "B-D-A-4B-A-6B-A-6B-A-6B-E",
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 6666}, "notes": ""},
    ),
    ("B-D-B-E", {"machine": "all", "kind": "single_time", "work": {"time_s": 1800}, "notes": ""}),
    (
        "B-D-B-D-B-A-3C-E",
        {"machine": "all", "kind": "single_time", "work": {"time_s": 3600}, "notes": ""},
    ),
    (
        "B-D-C-D-2B-E",
        {"machine": "all", "kind": "single_calorie", "work": {"calories": 250}, "notes": ""},
    ),
    (
        "B-2D-5A-2B-E",
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "notes": "",
        },
    ),
    (
        "B-2D-A-D-B-A-5C-4A-B-E",
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 1000},
            "rest_s": 60,
            "notes": "",
        },
    ),
    (
        "B-2D-3B-4A-2B-E",
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 180},
            "rest_s": 120,
            "notes": "",
        },
    ),
    (
        "B-2D-B-5A-3B-E",
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 60},
            "rest_s": 30,
            "notes": "",
        },
    ),
    (
        "B-2D-4C-4A-2B-E",
        {
            "machine": "all",
            "kind": "intervals_calorie",
            "work": {"calories": 20},
            "rest_s": 20,
            "notes": "",
        },
    ),
    (
        "B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E",
        {
            "machine": "all",
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 120},
                {"work": {"time_s": 120}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 120},
                {"work": {"time_s": 240}, "rest_s": 120},
                {"work": {"time_s": 300}, "rest_s": 120},
                {"work": {"time_s": 240}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 120},
                {"work": {"time_s": 120}, "rest_s": 120},
                {"work": {"time_s": 60}, "rest_s": 120},
            ],
            "notes": "",
        },
    ),
]
