# Run from repo root: python3 -m unittest discover -s tests -t .

"""Exercises pm5_model.PM5(monitor='pm3') / pm5_model.run(..., monitor='pm3')
against the PM3/PM4 anchor sequences quoted in the fastmail-808.12 brief
(reproduced directly from data/dataset.jsonl's 'pm34' gold column -- see
docs/pm3-model.md). 'pm4' is exercised as a pure spelling alias of 'pm3'
throughout (PM5(monitor='pm4') must behave identically to
PM5(monitor='pm3')).
"""

import unittest

from pm5keys import pm5_model as pm5

# (pm34 sequence, expected WorkoutSpec-shaped result) pairs, reproduced
# from the brief's anchors / data/dataset.jsonl.
PM34_ANCHORS = [
    (
        "B-D-C-4A-2B-E",  # 8 x 500m, 2 minutes rest
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "notes": "",
        },
    ),
    (
        "B-D-4C-A-5B-4A-4B-A-5B-E",  # 12 x 250m / 45 sec easy
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 250},
            "rest_s": 45,
            "notes": "",
        },
    ),
    (
        "B-2D-2B-4A-2B-E",  # 4 x 3 min / 2 min easy
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 180},
            "rest_s": 120,
            "notes": "",
        },
    ),
    (
        "B-3D-B-A-B-4A-2B-E",  # 3 x 12 minutes with 2 minutes rest
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 720},
            "rest_s": 120,
            "notes": "",
        },
    ),
    (
        "B-D-A-E",  # 2000m single distance
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 2000}, "notes": ""},
    ),
    (
        "B-D-B-D-B-A-3C-E",  # 60 minutes single time
        {"machine": "all", "kind": "single_time", "work": {"time_s": 3600}, "notes": ""},
    ),
    (
        # 1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest (variable time)
        "B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E",
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
    (
        # 10/20/30/40/50/60 Calories, 1 minute rest (variable calorie legs
        # ARE supported on PM3/PM4, even though fixed/single calorie
        # workouts are not).
        "B-D-E-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E",
        {
            "machine": "all",
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"calories": 10}, "rest_s": 60},
                {"work": {"calories": 20}, "rest_s": 60},
                {"work": {"calories": 30}, "rest_s": 60},
                {"work": {"calories": 40}, "rest_s": 60},
                {"work": {"calories": 50}, "rest_s": 60},
                {"work": {"calories": 60}, "rest_s": 60},
            ],
            "notes": "",
        },
    ),
]


class Pm34AnchorTest(unittest.TestCase):
    def test_all_anchors_on_pm3(self):
        for seq, expected in PM34_ANCHORS:
            with self.subTest(seq=seq):
                self.assertEqual(pm5.run(seq, monitor="pm3"), expected)

    def test_pm4_is_an_alias_of_pm3(self):
        for seq, expected in PM34_ANCHORS:
            with self.subTest(seq=seq):
                self.assertEqual(pm5.run(seq, monitor="pm4"), expected)
                self.assertEqual(
                    pm5.PM5(monitor="pm4").run(seq),
                    pm5.PM5(monitor="pm3").run(seq),
                )

    def test_monitor_defaults_to_pm5(self):
        # run()/explain()/PM5() must still default to 'pm5' -- backwards
        # compatibility for every pre-R12 caller.
        got = pm5.run("B-D-A-E")
        self.assertEqual(got["kind"], "single_distance")
        self.assertEqual(pm5.PM5().monitor, "pm5")

    def test_unknown_monitor_raises(self):
        with self.assertRaises(ValueError):
            pm5.PM5(monitor="pm2")
        with self.assertRaises(ValueError):
            pm5.run("B-D-A-E", monitor="not-a-monitor")


class Pm3NoCalorieMenuTest(unittest.TestCase):
    """PM3/PM4's New Workout chooser has no calorie screens at all --
    pressing the PM5 calorie-selecting letter (C, which is Intervals:
    Distance on PM3/PM4) does not "accidentally" reach a calorie screen,
    and pressing the letters that don't exist on PM3/PM4's chooser must
    raise."""

    def test_pm5_single_calorie_letter_reaches_a_different_screen_on_pm3(self):
        # On PM5, 'C' at the New Workout chooser selects Single Calorie;
        # on PM3/PM4, 'C' selects Intervals: Distance instead -- pressing
        # it must not silently land on a (nonexistent) calorie screen.
        machine = pm5.PM5(monitor="pm3")
        machine.press("B")  # Select Workout
        machine.press("D")  # New Workout
        machine.press("C")  # PM3/PM4: Intervals: Distance (NOT Calorie)
        self.assertEqual(machine.state, pm5._S_ENTRY)
        self.assertIs(machine.screen, pm5.INTERVALS_DISTANCE)

    def test_pm5_intervals_calorie_path_is_invalid_on_pm3(self):
        # On PM5, Intervals: Calorie is reached via B-D-D-C (Intervals
        # submenu -> Calorie). PM3/PM4 has no Intervals submenu at all,
        # so the second 'D' (which would open the submenu on PM5) instead
        # opens Intervals: Time directly -- the *third* press ('C') then
        # lands mid-entry-screen and is a valid cursor move, not a
        # calorie-screen selection. To exercise the "calorie screen
        # unreachable" property directly, drive PM3/PM4's own chooser
        # letters and confirm none of A-E ever produces a Single Calorie
        # or Intervals: Calorie screen.
        for key in "ABCDE":
            machine = pm5.PM5(monitor="pm3")
            machine.press("B")
            machine.press("D")
            try:
                machine.press(key)
            except ValueError:
                continue
            if machine.state == pm5._S_ENTRY:
                self.assertNotIn(
                    machine.screen,
                    (pm5.SINGLE_CALORIE, pm5.INTERVALS_CALORIE),
                    f"key {key!r} unexpectedly reached a calorie screen on pm3",
                )

    def test_variable_calorie_legs_still_reachable_on_pm3(self):
        # Intervals: Variable's per-interval type chooser (B=Calorie,
        # C=Distance, D=Time) is identical on both monitor families --
        # variable-calorie *legs* are supported even though a fixed or
        # single calorie *workout* is not.
        machine = pm5.PM5(monitor="pm3")
        machine.press("B")  # Select Workout
        machine.press("D")  # New Workout
        machine.press("E")  # PM3/PM4: Intervals: Variable
        self.assertEqual(machine.state, pm5._S_VARIABLE_TYPE_CHOOSER)
        machine.press("B")  # Calorie leg
        self.assertEqual(machine.state, pm5._S_ENTRY)
        self.assertIs(machine.screen, pm5.INTERVALS_CALORIE)


if __name__ == "__main__":
    unittest.main()
