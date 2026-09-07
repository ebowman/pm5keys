# Run from repo root: python3 -m unittest discover -s tests -t .

import unittest

from pm5keys import pm5_model as pm5


class RunGoldSequencesTest(unittest.TestCase):
    """Exercises pm5_model.run() against >= 8 of the gold sequences quoted
    in the fastmail-es5.11 brief / reproduced in pm5_model.GOLD_EXAMPLES."""

    def test_all_gold_examples(self):
        self.assertGreaterEqual(len(pm5.GOLD_EXAMPLES), 8)
        for seq, expected in pm5.GOLD_EXAMPLES:
            with self.subTest(seq=seq):
                self.assertEqual(pm5.run(seq), expected)

    def test_single_distance_default_2000(self):
        got = pm5.run("B-D-A-E")
        self.assertEqual(got["kind"], "single_distance")
        self.assertEqual(got["work"], {"distance_m": 2000})

    def test_single_distance_10000(self):
        got = pm5.run("B-D-A-D-B-A-2C-E")
        self.assertEqual(got["work"], {"distance_m": 10000})

    def test_single_time_default_3000(self):
        got = pm5.run("B-D-B-E")
        self.assertEqual(got["kind"], "single_time")
        self.assertEqual(got["work"], {"time_s": 1800})

    def test_single_time_6000(self):
        got = pm5.run("B-D-B-D-B-A-3C-E")
        self.assertEqual(got["work"], {"time_s": 3600})

    def test_single_calorie_250(self):
        got = pm5.run("B-D-C-D-2B-E")
        self.assertEqual(got["kind"], "single_calorie")
        self.assertEqual(got["work"], {"calories": 250})

    def test_intervals_distance_500_r120(self):
        got = pm5.run("B-2D-5A-2B-E")
        self.assertEqual(got["kind"], "intervals_distance")
        self.assertEqual(got["work"], {"distance_m": 500})
        self.assertEqual(got["rest_s"], 120)

    def test_intervals_time_180_r120(self):
        got = pm5.run("B-2D-3B-4A-2B-E")
        self.assertEqual(got["kind"], "intervals_time")
        self.assertEqual(got["work"], {"time_s": 180})
        self.assertEqual(got["rest_s"], 120)

    def test_intervals_calorie_20_r20(self):
        got = pm5.run("B-2D-4C-4A-2B-E")
        self.assertEqual(got["kind"], "intervals_calorie")
        self.assertEqual(got["work"], {"calories": 20})
        self.assertEqual(got["rest_s"], 20)

    def test_variable_pyramid_1_3_5_3_1(self):
        got = pm5.run("B-4D-4A-2B-E-D-2B-E-D-2B-E-D-2C-E-D-2C-2E")
        self.assertEqual(got["kind"], "intervals_variable")
        works = [iv["work"]["time_s"] for iv in got["intervals"]]
        self.assertEqual(works, [60, 180, 300, 180, 60])
        # every rest is retained at 120s (including the final one, since
        # nothing in the sequence ever edits the rest field back down)
        for iv in got["intervals"]:
            self.assertEqual(iv["rest_s"], 120)

    def test_variable_calorie_ladder_retained_type_reselect(self):
        # 50-40-30-20-10 Cals with 2 minutes easy: every interval after
        # the first is just "B-C-E" (reselect Calorie, -1 on 10s, confirm)
        # -- this specifically exercises the "type letter must be
        # re-pressed every interval" rule.
        seq = "B-3D-B-3A-2B-E-B-C-E-B-C-E-B-C-E-B-C-2E"
        got = pm5.run(seq)
        works = [iv["work"]["calories"] for iv in got["intervals"]]
        self.assertEqual(works, [50, 40, 30, 20, 10])
        for iv in got["intervals"]:
            self.assertEqual(iv["rest_s"], 120)

    def test_variable_mixed_distance_then_time(self):
        seq = "B-3D-C-D-3B-A-5C-4A-3B-E-2D-B-A-C-2E"
        got = pm5.run(seq)
        self.assertEqual(
            [iv["work"] for iv in got["intervals"]],
            [{"distance_m": 3000}, {"time_s": 600}],
        )
        self.assertEqual(got["intervals"][0]["rest_s"], 180)


class ImpossiblePressesTest(unittest.TestCase):
    def test_unknown_letter_key_rejected_by_keyseq(self):
        with self.assertRaises(ValueError):
            pm5.run("F")

    def test_press_before_main_menu_select_workout(self):
        machine = pm5.PM5()
        with self.assertRaises(ValueError):
            machine.press("A")  # only B is valid at the Main Menu

    def test_cursor_past_left_end(self):
        machine = pm5.PM5()
        for key in "BDA":  # -> Single Distance entry screen, cursor idx1
            machine.press(key)
        machine.press("D")  # idx1 -> idx0
        with self.assertRaises(ValueError):
            machine.press("D")  # idx0: cannot go further left

    def test_cursor_past_right_end(self):
        machine = pm5.PM5()
        for key in "BDA":  # -> Single Distance entry screen, cursor idx1
            machine.press(key)
        for _ in range(3):
            machine.press("A")  # idx1 -> idx2 -> idx3 -> idx4 (rightmost)
        with self.assertRaises(ValueError):
            machine.press("A")

    def test_digit_below_zero_at_true_floor(self):
        machine = pm5.PM5()
        for key in "BDAD":  # Single Distance, cursor -> idx0 (10000s, value 0)
            machine.press(key)
        with self.assertRaises(ValueError):
            machine.press("C")

    def test_digit_above_nine(self):
        machine = pm5.PM5()
        for key in "BDA":
            machine.press(key)
        for _ in range(7):
            machine.press("B")  # 1000s digit 2 -> 9
        with self.assertRaises(ValueError):
            machine.press("B")

    def test_variable_type_chooser_rejects_a(self):
        machine = pm5.PM5()
        for key in "BDDD":  # -> Intervals: Variable type chooser
            machine.press(key)
        with self.assertRaises(ValueError):
            machine.press("A")

    def test_variable_finish_before_any_interval_rejected(self):
        machine = pm5.PM5()
        for key in "BDDD":
            machine.press(key)
        with self.assertRaises(ValueError):
            machine.press("E")

    def test_press_after_done_rejected(self):
        machine = pm5.PM5()
        machine.run("B-D-A-E")
        with self.assertRaises(ValueError):
            machine.press("E")

    def test_run_incomplete_sequence_raises(self):
        with self.assertRaises(ValueError):
            pm5.run("B-D-A")  # never reaches E


class ExplainTest(unittest.TestCase):
    def test_explain_returns_trace_tuples(self):
        trace = pm5.explain("B-D-A-E")
        self.assertEqual(len(trace), 4)
        for entry in trace:
            self.assertEqual(len(entry), 3)
            press, screen, action = entry
            self.assertIn(press, "ABCDE")
            self.assertIsInstance(screen, str)
            self.assertIsInstance(action, str)

    def test_explain_is_human_readable_not_internal_state_names(self):
        # No internal state tokens (e.g. 'main', 'entry', 'select_workout',
        # 'digit[', 'cursor ->') should leak into screen/action text.
        trace = pm5.explain("B-2D-5A-2B-E")
        forbidden = ("main ->", "entry ->", "select_workout", "digit[", "cursor ->", "chooser (")
        for press, screen, action in trace:
            for token in forbidden:
                self.assertNotIn(token, screen)
                self.assertNotIn(token, action)

    def test_explain_menu_picks_name_the_item(self):
        trace = pm5.explain("B-2D-5A-2B-E")
        by_press_screen = {(p, s): a for p, s, a in trace}
        self.assertEqual(by_press_screen[("B", "Main Menu")], "Select Workout")
        self.assertEqual(by_press_screen[("D", "Select Workout")], "New Workout")
        self.assertEqual(by_press_screen[("D", "New Workout")], "Intervals")

    def test_explain_entry_screen_name_and_cursor_moves(self):
        # 8 x 500m, 2 minutes rest: B-2D-5A-2B-E
        trace = pm5.explain("B-2D-5A-2B-E")
        presses = list(trace)
        # First A on the Intervals chooser selects Intervals: Distance.
        self.assertEqual(presses[3], ("A", "Intervals", "Distance"))
        # Remaining A's are cursor moves on the entry screen, named by
        # destination field.
        self.assertEqual(
            presses[4],
            ("A", "Intervals: Distance", "cursor right to distance 10s digit"),
        )
        self.assertEqual(
            presses[7],
            ("A", "Intervals: Distance", "cursor right to rest minutes"),
        )
        # B presses increment the rest-minutes field.
        self.assertEqual(
            presses[8],
            ("B", "Intervals: Distance", "rest minutes +1 (now 1)"),
        )
        self.assertEqual(
            presses[9],
            ("B", "Intervals: Distance", "rest minutes +1 (now 2)"),
        )
        # Final E confirms.
        self.assertEqual(presses[10], ("E", "Intervals: Distance", "confirm"))

    def test_explain_variable_type_chooser_finish(self):
        # 1/2/3/4/5 minutes with 2 minutes rest.
        trace = pm5.explain("B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-2E")
        # Second-to-last press is E confirming the last interval; the
        # final E on the type chooser finishes the whole workout.
        self.assertEqual(trace[-1], ("E", "Intervals: Variable", "finish workout"))
        self.assertEqual(trace[-2], ("E", "Intervals: Time", "confirm"))


if __name__ == "__main__":
    unittest.main()
