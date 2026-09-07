# Run from repo root: python3 -m unittest discover -s tests -t .

import unittest

from pm5keys import compile_keys as ck
from pm5keys import keyseq
from pm5keys import pm5_model as pm5

# >= 12 gold (spec, sequence) pairs covering every WorkoutSpec kind,
# reproduced from the fastmail-es5.11 brief / spec_parsed.jsonl.
GOLD_COMPILE_CASES = [
    (
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 2000}, "notes": ""},
        "B-D-A-E",
    ),
    (
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""},
        "B-D-A-3B-E",
    ),
    (
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 10000}, "notes": ""},
        "B-D-A-D-B-A-2C-E",
    ),
    (
        {"machine": "all", "kind": "single_time", "work": {"time_s": 1800}, "notes": ""},
        "B-D-B-E",
    ),
    (
        {"machine": "all", "kind": "single_time", "work": {"time_s": 3600}, "notes": ""},
        "B-D-B-D-B-A-3C-E",
    ),
    (
        {"machine": "all", "kind": "single_calorie", "work": {"calories": 250}, "notes": ""},
        "B-D-C-D-2B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "count": 8,
            "notes": "",
        },
        "B-2D-5A-2B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 1000},
            "rest_s": 60,
            "count": 5,
            "notes": "",
        },
        "B-2D-A-D-B-A-5C-4A-B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 180},
            "rest_s": 120,
            "count": 10,
            "notes": "",
        },
        "B-2D-3B-4A-2B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 60},
            "rest_s": 30,
            "count": 10,
            "notes": "",
        },
        "B-2D-B-5A-3B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_calorie",
            "work": {"calories": 20},
            "rest_s": 20,
            "count": 5,
            "notes": "",
        },
        "B-2D-4C-4A-2B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_calorie",
            "work": {"calories": 10},
            "rest_s": 30,
            "count": 5,
            "notes": "",
        },
        "B-2D-5C-4A-3B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 120},
                {"work": {"time_s": 300}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 120},
                {"work": {"time_s": 60}, "rest_s": 0},
            ],
            "notes": "",
        },
        "B-4D-4A-2B-E-D-2B-E-D-2B-E-D-2C-E-D-2C-2E",
    ),
]


class CompileGoldCasesTest(unittest.TestCase):
    def test_reproduces_gold_exactly(self):
        self.assertGreaterEqual(len(GOLD_COMPILE_CASES), 12)
        kinds_seen = set()
        for spec, expected_seq in GOLD_COMPILE_CASES:
            with self.subTest(spec=spec):
                got = ck.compile(spec)
                self.assertEqual(got, keyseq.canonical(expected_seq))
                kinds_seen.add(spec["kind"])
        # every WorkoutSpec kind is covered
        self.assertEqual(
            kinds_seen,
            {
                "single_distance",
                "single_time",
                "single_calorie",
                "intervals_distance",
                "intervals_time",
                "intervals_calorie",
                "intervals_variable",
            },
        )


class CompileErrorPathsTest(unittest.TestCase):
    def test_unknown_kind_raises_not_implemented(self):
        spec = {"kind": "bogus_kind", "work": {"distance_m": 100}, "notes": ""}
        with self.assertRaises(NotImplementedError):
            ck.compile(spec)

    def test_distance_too_large_raises_value_error(self):
        spec = {"kind": "single_distance", "work": {"distance_m": 100000}, "notes": ""}
        with self.assertRaises(ValueError):
            ck.compile(spec)

    def test_rest_too_large_raises_value_error(self):
        spec = {
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 6000,
            "count": 4,
            "notes": "",
        }
        with self.assertRaises(ValueError):
            ck.compile(spec)

    def test_variable_last_interval_rest_ignored(self):
        # The last interval's rest_s is never compiled/emitted -- confirm
        # compile() does not raise even when it's an out-of-range value,
        # and that same_workout() ignores it.
        spec = {
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 60},
                {"work": {"time_s": 120}, "rest_s": 999999},
            ],
            "notes": "",
        }
        seq = ck.compile(spec)  # should not raise despite rest_s 999999 on the last interval
        result = pm5.run(seq)
        self.assertEqual(
            [iv["work"] for iv in result["intervals"]],
            [{"time_s": 60}, {"time_s": 120}],
        )


class SameWorkoutTest(unittest.TestCase):
    def test_ignores_count_and_machine_and_notes(self):
        a = {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "count": 8,
            "notes": "",
        }
        b = {
            "machine": "bikeerg",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "count": 4,
            "notes": "for time",
        }
        self.assertTrue(ck.same_workout(a, b))

    def test_ignores_last_interval_rest_for_variable(self):
        a = {
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 0},
            ],
        }
        b = {
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 240},
            ],
        }
        self.assertTrue(ck.same_workout(a, b))

    def test_detects_real_mismatch(self):
        a = {"kind": "single_distance", "work": {"distance_m": 2000}}
        b = {"kind": "single_distance", "work": {"distance_m": 5000}}
        self.assertFalse(ck.same_workout(a, b))

    def test_detects_non_last_interval_rest_mismatch(self):
        a = {
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 0},
            ],
        }
        b = {
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 60},
                {"work": {"time_s": 180}, "rest_s": 0},
            ],
        }
        self.assertFalse(ck.same_workout(a, b))


class PyramidTypoCaseTest(unittest.TestCase):
    """The documented GOLD_MISMATCH row: '5 min, 10 min, 15 min, 10 min,
    5 min pyramid / 2 min easy' -- gold's last interval ends 'D-5B-2E',
    encoding 15:00 (900s), not the spec's 5:00 (300s); a Concept2 typo."""

    SPEC = {
        "kind": "intervals_variable",
        "intervals": [
            {"work": {"time_s": 300}, "rest_s": 120},
            {"work": {"time_s": 600}, "rest_s": 120},
            {"work": {"time_s": 900}, "rest_s": 120},
            {"work": {"time_s": 600}, "rest_s": 120},
            {"work": {"time_s": 300}, "rest_s": 0},
        ],
        "notes": "",
    }
    GOLD_SEQ = "B-4D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-D-5B-2E"

    def test_compile_last_interval_sets_300s_correctly(self):
        # The last interval's retained work value going into this segment
        # is 600s (10:00, from the previous "10 min" leg); the canonical
        # sweep strategy moves left to the changed 10min digit (1 -> 0),
        # then right to the changed min digit (0 -> 5), landing on
        # "...-2D-C-A-5B-2E" (not the ...-5C-2E text hypothesised before
        # implementation -- verified here against the actual compiler
        # output/simulator round-trip instead).
        compiled = ck.compile(self.SPEC)
        self.assertTrue(compiled.endswith("2D-C-A-5B-2E"), compiled)
        sim_compiled = pm5.run(compiled)
        self.assertEqual(sim_compiled["intervals"][-1]["work"], {"time_s": 300})

    def test_gold_last_interval_is_900s_not_300s(self):
        sim_gold = pm5.run(self.GOLD_SEQ)
        self.assertEqual(sim_gold["intervals"][-1]["work"], {"time_s": 900})
        self.assertNotEqual(sim_gold["intervals"][-1]["work"], self.SPEC["intervals"][-1]["work"])

    def test_gold_is_not_same_workout_as_spec(self):
        sim_gold = pm5.run(self.GOLD_SEQ)
        self.assertFalse(ck.same_workout(sim_gold, self.SPEC))


# (spec, expected pm34 sequence) pairs for every WorkoutSpec kind PM3/PM4
# supports, reproduced from the fastmail-808.12 brief / data/dataset.jsonl's
# 'pm34' column.
PM3_GOLD_COMPILE_CASES = [
    (
        {"machine": "all", "kind": "single_distance", "work": {"distance_m": 2000}, "notes": ""},
        "B-D-A-E",
    ),
    (
        {"machine": "all", "kind": "single_time", "work": {"time_s": 3600}, "notes": ""},
        "B-D-B-D-B-A-3C-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "notes": "",
        },
        "B-D-C-4A-2B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_time",
            "work": {"time_s": 180},
            "rest_s": 120,
            "notes": "",
        },
        "B-2D-2B-4A-2B-E",
    ),
    (
        {
            "machine": "all",
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 120},
                {"work": {"time_s": 120}, "rest_s": 120},
                {"work": {"time_s": 180}, "rest_s": 0},
            ],
            "notes": "",
        },
        "B-D-E-D-4A-2B-E-D-B-E-D-B-2E",
    ),
]


class CompilePm3Test(unittest.TestCase):
    """compile(spec, monitor='pm3') for every kind PM3/PM4 supports;
    calorie kinds must raise NotImplementedError instead."""

    def test_reproduces_pm34_gold_for_every_supported_kind(self):
        kinds_seen = set()
        for spec, expected_seq in PM3_GOLD_COMPILE_CASES:
            with self.subTest(spec=spec):
                got = ck.compile(spec, monitor="pm3")
                self.assertEqual(got, keyseq.canonical(expected_seq))
                kinds_seen.add(spec["kind"])
        self.assertEqual(
            kinds_seen,
            {
                "single_distance",
                "single_time",
                "intervals_distance",
                "intervals_time",
                "intervals_variable",
            },
        )

    def test_pm4_alias_matches_pm3(self):
        for spec, _expected_seq in PM3_GOLD_COMPILE_CASES:
            with self.subTest(spec=spec):
                self.assertEqual(ck.compile(spec, monitor="pm4"), ck.compile(spec, monitor="pm3"))

    def test_single_calorie_raises_on_pm3(self):
        spec = {"machine": "all", "kind": "single_calorie", "work": {"calories": 250}, "notes": ""}
        with self.assertRaises(NotImplementedError):
            ck.compile(spec, monitor="pm3")
        with self.assertRaises(NotImplementedError):
            ck.compile(spec, monitor="pm4")

    def test_intervals_calorie_raises_on_pm3(self):
        spec = {
            "machine": "all",
            "kind": "intervals_calorie",
            "work": {"calories": 20},
            "rest_s": 20,
            "notes": "",
        }
        with self.assertRaises(NotImplementedError):
            ck.compile(spec, monitor="pm3")

    def test_calorie_workouts_still_compile_on_pm5(self):
        # Same specs must still compile fine when monitor='pm5' (default).
        spec = {"machine": "all", "kind": "single_calorie", "work": {"calories": 250}, "notes": ""}
        self.assertEqual(ck.compile(spec), "B-D-C-D-2B-E")

    def test_explain_uses_pm3_monitor(self):
        spec = {
            "machine": "all",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "notes": "",
        }
        trace = ck.explain(spec, monitor="pm3")
        screens = {screen for _press, screen, _action in trace}
        self.assertIn("Intervals: Distance", screens)
        # PM3/PM4 has no separate "Intervals" submenu screen.
        self.assertNotIn("Intervals", screens)


class Pm3RoundTripTest(unittest.TestCase):
    """Property test: for every non-calorie row in data/spec_parsed.jsonl,
    same_workout(run(compile(spec, 'pm3'), 'pm3'), spec) must hold -- i.e.
    compile() and run() are inverses of each other on PM3/PM4, exactly as
    they already are on PM5. Skips (rather than fails) if the data files
    aren't present, since they're data assets, not code under test."""

    def test_round_trip_over_all_non_calorie_spec_rows(self):
        import json
        import os

        spec_path = os.path.join(os.path.dirname(__file__), "..", "data", "spec_parsed.jsonl")
        if not os.path.exists(spec_path):
            self.skipTest("data/spec_parsed.jsonl not present")

        with open(spec_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]

        checked = 0
        for row in rows:
            spec = row["spec"]
            if spec.get("kind") in ("single_calorie", "intervals_calorie"):
                continue
            with self.subTest(title=row["title"], machines=row["machines"]):
                compiled = ck.compile(spec, monitor="pm3")
                ran = pm5.run(compiled, monitor="pm3")
                self.assertTrue(
                    ck.same_workout(ran, spec),
                    f"round-trip mismatch for {row['title']!r}: "
                    f"compiled={compiled!r} ran={ran!r} spec={spec!r}",
                )
                checked += 1
        self.assertGreater(checked, 0, "no non-calorie rows found to round-trip")


if __name__ == "__main__":
    unittest.main()
