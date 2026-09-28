# Run from repo root: python3 -m unittest discover -s tests -t .

import unittest

import pm5keys.spec as spec


class ValidateSpecTest(unittest.TestCase):
    def test_valid_single_distance(self):
        spec.validate_spec(
            {
                "machine": "rower",
                "kind": "single_distance",
                "work": {"distance_m": 2000},
                "notes": "",
            }
        )

    def test_valid_fixed_intervals(self):
        spec.validate_spec(
            {
                "machine": "all",
                "kind": "intervals_distance",
                "work": {"distance_m": 500},
                "rest_s": 120,
                "count": 8,
                "notes": "",
            }
        )

    def test_valid_intervals_variable(self):
        spec.validate_spec(
            {
                "machine": "all",
                "kind": "intervals_variable",
                "intervals": [
                    {"work": {"time_s": 60}, "rest_s": 120},
                    {"work": {"time_s": 120}, "rest_s": 0},
                ],
                "notes": "",
            }
        )

    def test_rejects_fixed_interval_count_one(self):
        with self.assertRaises(ValueError):
            spec.validate_spec(
                {
                    "machine": "all",
                    "kind": "intervals_distance",
                    "work": {"distance_m": 500},
                    "rest_s": 60,
                    "count": 1,
                    "notes": "",
                }
            )

    def test_rejects_variable_with_empty_intervals(self):
        with self.assertRaises(ValueError):
            spec.validate_spec(
                {
                    "machine": "all",
                    "kind": "intervals_variable",
                    "intervals": [],
                    "notes": "",
                }
            )

    def test_rejects_bad_machine(self):
        with self.assertRaises(ValueError):
            spec.validate_spec(
                {
                    "machine": "peloton",
                    "kind": "single_distance",
                    "work": {"distance_m": 2000},
                    "notes": "",
                }
            )

    def test_rejects_multiple_work_keys(self):
        with self.assertRaises(ValueError):
            spec.validate_spec(
                {
                    "machine": "all",
                    "kind": "single_distance",
                    "work": {"distance_m": 2000, "time_s": 600},
                    "notes": "",
                }
            )


class ParseSpecPatternTest(unittest.TestCase):
    """One test per pattern family enumerated in the bead brief, using
    real title+description text drawn originally from dataset_unique.jsonl."""

    def test_n_x_distance_comma_minutes_rest(self):
        # 'N x 500m, 2 minutes rest'
        text = "8 x 500m, 2 minutes rest\n8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)"
        s = spec.parse_spec(text, "RowErg and SkiErg")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 500})
        self.assertEqual(s["rest_s"], 120)
        self.assertEqual(s["count"], 8)
        self.assertEqual(s["machine"], "rower")

    def test_n_x_time_slash_easy_rest(self):
        # 'N x 1 min / 1 min easy' -- 'easy' means rest
        text = (
            "10 x 1 min / 1 min easy\n"
            "Ten 1 minute pieces. One minute at light pressure between "
            "each piece."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_time")
        self.assertEqual(s["work"], {"time_s": 60})
        self.assertEqual(s["rest_s"], 60)
        self.assertEqual(s["count"], 10)

    def test_n_x_mmss_work_slash_seconds_easy(self):
        # 'N x 2:30 / 30 seconds easy' (m:ss work)
        text = (
            "10 x 2:30 / 30 seconds easy\n"
            "10 work intervals of 2 minutes and 30 seconds, with 30 "
            "seconds recovery between each interval."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_time")
        self.assertEqual(s["work"], {"time_s": 150})
        self.assertEqual(s["rest_s"], 30)
        self.assertEqual(s["count"], 10)

    def test_n_x_seconds_work_seconds_rest(self):
        # 'N x 45s work, 45s rest'
        text = "20 x 45s work, 45s rest\n20 rounds of 45 seconds work followed by 45 seconds rest"
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_time")
        self.assertEqual(s["work"], {"time_s": 45})
        self.assertEqual(s["rest_s"], 45)
        self.assertEqual(s["count"], 20)

    def test_n_x_calories_with_minute_easy(self):
        # 'N X 25 Cals with 1 minute easy'
        text = (
            "12 X 25 Cals with 1 minute easy\n"
            "Twelve 25 Calorie pieces. One minute at light pressure "
            "between each piece."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_calorie")
        self.assertEqual(s["work"], {"calories": 25})
        self.assertEqual(s["rest_s"], 60)
        self.assertEqual(s["count"], 12)

    def test_minute_pyramid_slash_with_rest(self):
        # '1/3/5/3/1 minutes with 2 minutes rest'
        text = (
            "1/3/5/3/1 minutes with 2 minutes rest\n"
            "Intervals of 1 minute, 3 minutes, 5 minutes, 3 minutes and "
            "1 minute. 2 minutes light between the work intervals."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["time_s"] for iv in s["intervals"]]
        self.assertEqual(values, [60, 180, 300, 180, 60])
        rests = [iv["rest_s"] for iv in s["intervals"]]
        self.assertEqual(rests, [120, 120, 120, 120, 0])

    def test_comma_minute_pyramid_slash_easy(self):
        # '1 min, 2 min, 3 min, 4 min, 3 min, 2 min, 1 min pyramid / 1
        # min easy'
        text = (
            "1 min, 2 min, 3 min, 4 min, 3 min, 2 min, 1 min pyramid / "
            "1 min easy\n"
            "Seven intervals in a pyramid of 1-2-3-4-3-2-1 minutes, with "
            "one minute of rest in between each piece."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["time_s"] for iv in s["intervals"]]
        self.assertEqual(values, [60, 120, 180, 240, 180, 120, 60])

    def test_intervals_of_minute_slash_with_rest(self):
        # 'Intervals of 6/3/3/1/1/1 minutes with 2 minutes rest.'
        text = (
            "Intervals of 6/3/3/1/1/1 minutes with 2 minutes rest.\n"
            "6 timed intervals of 6/3/3/1/1/1 minutes with 2 minutes "
            "rest between each interval."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["time_s"] for iv in s["intervals"]]
        self.assertEqual(values, [360, 180, 180, 60, 60, 60])

    def test_distance_ladder_word_numbers_rest(self):
        # '2000/1500/1000/500m with three minutes rest' (word number rest)
        text = (
            "2000/1500/1000/500m with three minutes rest\n"
            "A 2000m interval, followed by a 1500m interval, then 1000m, "
            "then 500m. Three minutes light between intervals. "
            "(BikeErg: 4000/3000/2000/1000m)"
        )
        s = spec.parse_spec(text, "RowErg and SkiErg")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["distance_m"] for iv in s["intervals"]]
        self.assertEqual(values, [2000, 1500, 1000, 500])
        self.assertEqual(s["intervals"][0]["rest_s"], 180)

    def test_distance_ladder_with_m_suffix_on_each_segment(self):
        # '500m/1000m/500m/1000m/500m with two minutes rest.'
        text = (
            "500m/1000m/500m/1000m/500m with two minutes rest.\n"
            "Intervals of 500m, 1000m, 500m, 1000m, 500m with two "
            "minutes rest between each interval. (BikeErg: 1K, 2K, 1K, "
            "2K, 1K)"
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["distance_m"] for iv in s["intervals"]]
        self.assertEqual(values, [500, 1000, 500, 1000, 500])

    def test_calorie_ladder_slash_with_period_and_rest_between(self):
        # '10/20/30/40/50/60 Calories. 1 minute rest between intervals.'
        text = (
            "10/20/30/40/50/60 Calories.  1 minute rest between "
            "intervals.\n"
            "Intervals of 10, 20, 30, 40, 50 and 60 Calories, with one "
            "minute rest between."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["calories"] for iv in s["intervals"]]
        self.assertEqual(values, [10, 20, 30, 40, 50, 60])

    def test_calorie_ladder_dash_separated_descending(self):
        # '50 - 40 - 30 - 20 - 10 Cals with 2 minutes easy'
        text = (
            "50 - 40 - 30 - 20 - 10 Cals with 2 minutes easy\n"
            "Five calorie intervals. First interval - 50 cals. Second "
            "interval 40 cals. Then 30, 20 and 10. Two minutes at light "
            "pressure between each piece."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        values = [iv["work"]["calories"] for iv in s["intervals"]]
        self.assertEqual(values, [50, 40, 30, 20, 10])

    def test_single_distance_time_trial(self):
        # '5000m time trial'
        text = (
            "5000m time trial\n"
            "5000 meter time trial, going for your personal best. Enter "
            "your result in the Online Ranking and see where you stand "
            "with others of your age, gender and weight class. "
            "(BikeErg: 10,000m)"
        )
        s = spec.parse_spec(text, "RowErg and SkiErg")
        self.assertEqual(s["kind"], "single_distance")
        self.assertEqual(s["work"], {"distance_m": 5000})

    def test_single_time_minute_time_trial(self):
        # '30 minute time trial'
        text = "30 minute time trial\nDo a 30 minute time trial, going for your personal best."
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "single_time")
        self.assertEqual(s["work"], {"time_s": 1800})

    def test_single_calorie(self):
        # '250 Calories'
        text = "250 Calories\nDo 250 calories for time."
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "single_calorie")
        self.assertEqual(s["work"], {"calories": 250})

    def test_single_distance_bare_meters(self):
        # '2000m'
        text = "2000m\nDo 2000m as fast as you can (4000m for BikeErg)"
        s = spec.parse_spec(text, "RowErg and SkiErg")
        self.assertEqual(s["kind"], "single_distance")
        self.assertEqual(s["work"], {"distance_m": 2000})

    def test_variable_rest_chain(self):
        # '2000m/3 minutes rest/1000m/2 minutes rest/500m'
        text = (
            "2000m/3 minutes rest/1000m/2 minutes rest/500m\n"
            "A 2000m interval, followed by three minutes rest. Then "
            "1000m, followed by two minutes rest. Then 500m. "
            "(BikeErg: 4000/2000/1000m)"
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        intervals = s["intervals"]
        self.assertEqual(
            [iv["work"] for iv in intervals],
            [{"distance_m": 2000}, {"distance_m": 1000}, {"distance_m": 500}],
        )
        self.assertEqual([iv["rest_s"] for iv in intervals], [180, 120, 0])

    def test_variable_rest_comma_chain_mixed_units(self):
        # '3000m, 3 minutes rest, 10 minutes work'
        text = (
            "3000m, 3 minutes rest, 10 minutes work\n"
            "A 3000m work interval, followed by 3 minutes rest. Then a "
            "10 minute work interval."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        intervals = s["intervals"]
        self.assertEqual(intervals[0]["work"], {"distance_m": 3000})
        self.assertEqual(intervals[0]["rest_s"], 180)
        self.assertEqual(intervals[1]["work"], {"time_s": 600})
        self.assertEqual(intervals[1]["rest_s"], 0)

    def test_variable_rest_comma_chain_no_longer_truncated(self):
        # '3000m, 3 minutes rest, 10 minutes work, 2 minutes rest, 5
        # minutes work' -- must not silently truncate to the first two
        # legs.
        text = (
            "3000m, 3 minutes rest, 10 minutes work, 2 minutes rest, 5 "
            "minutes work\n"
            "A 3000m interval, then 3 minutes rest, then 10 minutes of "
            "work, then 2 minutes rest, then 5 minutes of work."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        intervals = s["intervals"]
        self.assertEqual(
            [iv["work"] for iv in intervals],
            [{"distance_m": 3000}, {"time_s": 600}, {"time_s": 300}],
        )
        self.assertEqual([iv["rest_s"] for iv in intervals], [180, 120, 0])

    def test_slash_variable_chain_with_time_leg(self):
        # '2000m/3 minutes rest/5 minutes/2 minutes rest/500m'
        text = (
            "2000m/3 minutes rest/5 minutes/2 minutes rest/500m\n"
            "A 2000m interval, followed by 3 minutes rest. Then 5 "
            "minutes of work, followed by 2 minutes rest. Then 500m."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        intervals = s["intervals"]
        self.assertEqual(
            [iv["work"] for iv in intervals],
            [{"distance_m": 2000}, {"time_s": 300}, {"distance_m": 500}],
        )
        self.assertEqual([iv["rest_s"] for iv in intervals], [180, 120, 0])

    def test_variable_chain_twelve_legs(self):
        # A long comma chain with qualifiers on every work leg and a
        # required 'rest' cue on every rest leg -- no leg-count cap.
        text = (
            "6 minutes easy, 1 minute rest, 1 minute hard, 1 minute "
            "rest, 1 minute hard, 1 minute rest, 1 minute hard, 1 "
            "minute rest, 1 minute hard, 1 minute rest, 1 minute hard, "
            "1 minute rest, 1 minute hard, 1 minute rest, 1 minute "
            "hard, 1 minute rest, 1 minute hard, 1 minute rest, 1 "
            "minute hard, 1 minute rest, 1 minute hard, 1 minute rest, "
            "3 minutes easy\n"
            "A 6 minute warm-up, then ten 1 minute hard efforts with 1 "
            "minute rest between each, then a 3 minute cool-down."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        intervals = s["intervals"]
        self.assertEqual(len(intervals), 12)
        expected_work = [{"time_s": 360}] + [{"time_s": 60}] * 10 + [{"time_s": 180}]
        expected_rest = [60] * 11 + [0]
        self.assertEqual([iv["work"] for iv in intervals], expected_work)
        self.assertEqual([iv["rest_s"] for iv in intervals], expected_rest)

    def test_equal_work_and_rest(self):
        # '1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and
        # rest.'
        text = (
            "1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and "
            "rest.\n"
            "Equal work and rest intervals that increase by 30 seconds "
            "each time, working up from 1 minute to 4 minutes."
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        for iv in s["intervals"][:-1]:
            self.assertEqual(iv["work"]["time_s"], iv["rest_s"])
        self.assertEqual(s["intervals"][-1]["rest_s"], 0)
        values = [iv["work"]["time_s"] for iv in s["intervals"]]
        self.assertEqual(values, [60, 90, 120, 150, 180, 210, 240])

    def test_title_omits_rest_20_seconds_variant(self):
        # '5 x 1000m' title with rest only in the description (20s
        # variant)
        text = "5 x 1000m\n5 x 1000m with 20 seconds rest"
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 1000})
        self.assertEqual(s["rest_s"], 20)
        self.assertEqual(s["count"], 5)

    def test_title_omits_rest_60_seconds_variant(self):
        # '5 x 1000m' title with rest only in the description (60s
        # variant)
        text = "5 x 1000m\n5 x 1000m with 60 seconds rest."
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["rest_s"], 60)

    def test_title_omits_rest_from_description_minutes(self):
        # '8 x 1000m' title with rest only in the description
        text = "8 x 1000m\n8 X 1000m with 2 minutes rest"
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["rest_s"], 120)
        self.assertEqual(s["count"], 8)

    def test_bikeerg_override_single_value_paren(self):
        # '(BikeErg: 1000m)'
        text = "8 x 500m, 2 minutes rest\n8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)"
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["machine"], "bikeerg")
        self.assertEqual(s["work"], {"distance_m": 1000})

    def test_bikeerg_override_positional_list(self):
        # '(BikeErg: 1K, 2K, 1K, 2K, 1K)' -- positional override onto a
        # variable-interval spec.
        text = (
            "500m/1000m/500m/1000m/500m with two minutes rest.\n"
            "Intervals of 500m, 1000m, 500m, 1000m, 500m with two "
            "minutes rest between each interval. (BikeErg: 1K, 2K, 1K, "
            "2K, 1K)"
        )
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["machine"], "bikeerg")
        values = [iv["work"]["distance_m"] for iv in s["intervals"]]
        self.assertEqual(values, [1000, 2000, 1000, 2000, 1000])

    def test_bikeerg_override_slash_list_descending_ladder(self):
        # '(BikeErg: 4000/3000/2000/1000m)' -- slash-separated positional
        # override where only the last part carries the unit; must not
        # collapse to a single repeated value.
        text = (
            "2000/1500/1000/500m with three minutes rest\n"
            "A 2000m interval, followed by a 1500m interval, then "
            "1000m, then 500m. Three minutes light between intervals. "
            "(BikeErg: 4000/3000/2000/1000m)"
        )
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["machine"], "bikeerg")
        values = [iv["work"]["distance_m"] for iv in s["intervals"]]
        self.assertEqual(values, [4000, 3000, 2000, 1000])

    def test_bikeerg_override_slash_list_variable_rest_chain(self):
        # '(BikeErg: 4000/2000/1000m)' on a variable-rest chain (mixed
        # work/rest slash segments in the base text).
        text = (
            "2000m/3 minutes rest/1000m/2 minutes rest/500m\n"
            "A 2000m interval, followed by three minutes rest. Then "
            "1000m, followed by two minutes rest. Then 500m. "
            "(BikeErg: 4000/2000/1000m)"
        )
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["machine"], "bikeerg")
        values = [iv["work"]["distance_m"] for iv in s["intervals"]]
        self.assertEqual(values, [4000, 2000, 1000])

    def test_bikeerg_malformed_override_returns_none(self):
        # A positional list with a part that isn't a distance at all
        # must never guess -- the whole spec is unparsed.
        text = (
            "8 x 500m, 2 minutes rest\n"
            "8 x 500m intervals with 2 minutes rest. "
            "(BikeErg: 1000m, banana, 2000m)"
        )
        self.assertIsNone(spec.parse_spec(text, "BikeErg"))

    def test_bikeerg_override_note_spelling(self):
        # 'Note: for BikeErg, distance is 1000 meters.'
        text = (
            "6 x 500m / 1 min easy\n"
            "Complete six 500 meter pieces. Continue at light pressure "
            "between each 500. Note: for BikeErg, distance is 1000 "
            "meters."
        )
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["work"], {"distance_m": 1000})

    def test_bikeerg_override_thousands_comma_not_a_list(self):
        # '(BikeErg: 10,000m)' -- comma is a thousands separator here,
        # not a positional-list separator.
        text = (
            "5000m time trial\n"
            "5000 meter time trial, going for your personal best. "
            "(BikeErg: 10,000m)"
        )
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["work"], {"distance_m": 10000})

    def test_bikeerg_override_does_not_clobber_time_leg(self):
        # A mixed distance+time intervals_variable spec: the override
        # must only touch the distance leg.
        text = (
            "3000m, 3 minutes rest, 10 minutes work\n"
            "A 3000m work interval, followed by 3 minutes rest. Then a "
            "10 minute work interval. (BikeErg: 6000m)"
        )
        s = spec.parse_spec(text, "BikeErg")
        self.assertEqual(s["intervals"][0]["work"], {"distance_m": 6000})
        self.assertEqual(s["intervals"][1]["work"], {"time_s": 600})

    def test_word_numbers_in_count_and_rest(self):
        s = spec.parse_spec("five x 500m with three minutes rest", "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 500})
        self.assertEqual(s["count"], 5)
        self.assertEqual(s["rest_s"], 180)

    def test_rowerg_and_skierg_maps_to_rower(self):
        s = spec.parse_spec("2000m", "RowErg and SkiErg")
        self.assertEqual(s["machine"], "rower")

    def test_all_machines_maps_to_all(self):
        s = spec.parse_spec("2000m", "All Machines")
        self.assertEqual(s["machine"], "all")

    def test_none_machines_maps_to_all(self):
        s = spec.parse_spec("2000m", None)
        self.assertEqual(s["machine"], "all")

    def test_unknown_machines_raises_value_error(self):
        self.assertRaises(ValueError, spec._map_machine, "SurfSki")


class ParseSpecNegativeTest(unittest.TestCase):
    def test_triple_tabata_unparsed(self):
        text = (
            "Triple Tabata\n"
            "8 sets of 20 seconds hard followed by 10 seconds easy. "
            "Rest for 4 minutes. Repeat the 8 sets. Rest for 4 minutes. "
            "Repeat the 8 sets."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_rate_changes_unparsed(self):
        text = (
            "4 x 6 minutes with rate changes.  2 minutes rest between "
            "intervals.\n"
            "4 x 6 minutes of work with two minutes rest between "
            "intervals. Each 6 minute interval is split into 3 minutes "
            "then 2 minutes then 1 minute at different stroke rates or "
            "cadence."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_empty_string_unparsed(self):
        self.assertIsNone(spec.parse_spec("", "All Machines"))
        self.assertIsNone(spec.parse_spec("   ", "All Machines"))

    def test_just_row_unparsed(self):
        self.assertIsNone(spec.parse_spec("just row", "All Machines"))

    def test_nested_rounds_unparsed(self):
        text = (
            "2 rounds of 16 x 20 seconds work and 10 seconds rest\n"
            "16 intervals of 20 seconds work, with 10 seconds rest. Then "
            "rest for 3 minutes. Repeat the 16 intervals of 20 seconds "
            "work and 10 seconds rest."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_split_distance_no_rest_unparsed(self):
        text = (
            "4,024m\n"
            "4,024m as fast as you can, split into three intervals "
            "1000m/2024m/1000m, but with no rest between the intervals "
            "(BikeErg: 8,048m)."
        )
        self.assertIsNone(spec.parse_spec(text, "RowErg and SkiErg"))

    def test_rounds_of_with_rest_before_between_unparsed(self):
        # No matcher captures "easy 90 seconds between each" -- the rest
        # clause word ("easy") precedes the duration and "between" (not
        # "rest"/"easy"/"light"/"recovery") follows it, so this must not
        # fall through to a guessed single_distance(500).
        text = "6 rounds of 500m, easy 90 seconds between each"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_two_pieces_with_rest_then_unparsed(self):
        # Two distinct work pieces chained by "with ... rest then" -- no
        # matcher represents this shape, must not guess single_distance
        # from the first number.
        text = "2000m with 3 minutes rest then 1000m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_nested_sets_of_x_with_off_unparsed(self):
        text = "3 sets of 4 x 250m with 45 seconds off"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_two_pieces_word_number_rest_between_never_guesses_single(self):
        # Either unparsed, or correctly parsed as a 2x2000m/300s fixed
        # interval set -- but never a single_distance guess.
        text = "two 2000m pieces with 5 minutes rest between"
        s = spec.parse_spec(text, "All Machines")
        if s is not None:
            self.assertEqual(s["kind"], "intervals_distance")
            self.assertEqual(s["work"], {"distance_m": 2000})
            self.assertEqual(s["count"], 2)
            self.assertEqual(s["rest_s"], 300)

    def test_five_x_500m_still_unparsed(self):
        self.assertIsNone(spec.parse_spec("5 x 500m", "All Machines"))

    def test_warmup_fixed_intervals_cooldown_unparsed(self):
        # pm5-7bk.2 bug: a fixed intervals_time match ("10 x 1 min hard
        # / 1 min light") must not silently drop the warm-up/cool-down
        # legs bracketing it.
        text = "7 min warm-up, 10 x 1 min hard / 1 min light, 3 min cool-down"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_warmup_then_intervals_then_cooldown_unparsed(self):
        text = "warm up 7 minutes, then 10 x 1:00 on / 1:00 off, then 3 minutes cool down"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_rest_leg_without_cue_unparsed(self):
        # '500m, 2 minutes, 500m' -- the middle (rest-position) leg has
        # no rest cue, so the whole chain must fail rather than guess.
        text = (
            "500m, 2 minutes, 500m\n"
            "A 500m interval, then 2 minutes, then another 500m."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_work_leg_says_rest_unparsed(self):
        # A work-position leg saying 'rest' is not a valid work leg --
        # the whole chain must fail.
        text = (
            "500m, 2 minutes rest, 500m rest\n"
            "A 500m interval, followed by 2 minutes rest, then 500m "
            "rest."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_trailing_junk_unparsed(self):
        # Trailing text after the chain on the same line is not
        # consumed by any leg, so the whole chain must fail rather than
        # silently drop it.
        text = "500m, 1 minute rest, 500m and then some"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_junk_unparsed(self):
        # Leading text before the chain on the same line is not
        # consumed by any leg, so the whole chain must fail.
        text = "then do 500m, 1 minute rest, 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_surrounded_by_warmup_cooldown_unparsed(self):
        # Leading warm-up and trailing cool-down text bracket the chain
        # on the same line -- the matcher must not drop them.
        text = "Warm up 10 minutes, then 500m, 1 minute rest, 500m, then cool down"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_parenthesized_by_n_x_unparsed(self):
        # A chain-shaped substring inside "N x (...)" is not itself a
        # full-line chain and must not be guessed at.
        text = "4 x (500m, 1 minute rest, 500m)"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_does_not_steal_n_x_with_rest(self):
        # Regression: "3 x 500m, 1 minute rest, 500m" starts with an N x
        # count prefix, so the leading '3 x 500m' is not itself a chain
        # leg -- the whole line must fail full consumption and fall
        # through to the N x WORK, REST matcher, same as before the
        # variable-chain matcher was generalised.
        text = "3 x 500m, 1 minute rest, 500m"
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 500})
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["rest_s"], 60)

    def test_variable_chain_multiline_bracketed_by_other_content_unparsed(self):
        # The chain fills one whole line, but sibling lines carry real,
        # distinct workout content (a warm-up sentence, a trailing "N x"
        # block) introducing numbers the chain doesn't account for --
        # full consumption must reject this, not silently drop the
        # other lines.
        text = "Warm up 10 minutes.\n500m, 1 minute rest, 500m\nThen 4 x 250m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_multiline_n_x_prefix_line_falls_through(self):
        # Regression: an "N x" count sits alone on its own line, with the
        # chain-shaped body on the next line. This must NOT be read as a
        # 2-leg variable chain -- it must fall through to the N x WORK,
        # REST matcher, same as the single-line "3 x 500m, 1 minute
        # rest, 500m" case.
        text = "3 x\n500m, 1 minute rest, 500m"
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 500})
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["rest_s"], 60)

    def test_variable_chain_multiline_trailing_leftover_unparsed(self):
        # The chain fills the first line, but a second line tacks on an
        # unrelated, unaccounted-for leg ("then 2000m") -- full
        # consumption must reject this rather than silently truncate to
        # just the first line's chain.
        text = "500m, 1 minute rest, 500m\nthen 2000m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_sibling_count_cue_rejected_even_if_numbers_match(self):
        # A sibling line has an "N x" count cue where N and a distance it
        # mentions both happen to already be numbers the chain uses --
        # the count cue itself (not the numbers) is what must reject the
        # variable-chain match. (Phrased so "3" and "x" aren't directly
        # adjacent to a work unit, e.g. literal "3 x 500m" on the sibling
        # line -- that exact phrasing is also a valid standalone "N x
        # WORK ... rest elsewhere" instruction that a different,
        # pre-existing fallback matcher legitimately picks up once the
        # chain matcher steps aside, which would make this an
        # end-to-end intervals_distance positive rather than a
        # variable-chain negative; see _match_n_x_work_then_fallback_rest.)
        text = "500m, 1 minute rest, 500m\n3 x easy warm up before the usual 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))
        clean = spec._strip_parenthetical_and_notes(text)
        self.assertIsNone(spec._match_variable_chain(clean))

    def test_variable_chain_sibling_bare_number_ignored(self):
        # A sibling line mentions a bare, unit-less number (a day/event
        # count, not a work/rest amount) -- full consumption must still
        # accept the chain since nothing unit-bearing or count-cued is
        # left over.
        text = "3000m, 3 minutes rest, 10 minutes work\nDay 2 of the challenge"
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        intervals = s["intervals"]
        self.assertEqual(
            [iv["work"] for iv in intervals],
            [{"distance_m": 3000}, {"time_s": 600}],
        )
        self.assertEqual([iv["rest_s"] for iv in intervals], [180, 0])

    def test_variable_chain_multiset_role_mismatch_unparsed(self):
        # The chain's only 60-second value is a REST leg. A sibling
        # mention of "1 minute" tagged as WORK ("hard") cannot draw from
        # that rest-only budget -- multiset entries are role-tagged for
        # time values (see the full-consumption comment), so this must
        # reject even though 60 is nominally "a chain number".
        text = "500m, 1 minute rest, 500m\nthen 1 minute hard"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_multiset_value_exceeded_unparsed(self):
        # The chain has exactly two 500m work legs. A description that
        # restates 500m a THIRD time exceeds that budget once the first
        # two mentions have already drawn it down to zero -- reject.
        # (A single extra bare mention with no other restatement, e.g.
        # "Finish with 500m", does NOT exceed a budget of two and is
        # correctly accepted; this test spends the whole budget first so
        # the third mention has nothing left to match.)
        text = (
            "500m, 1 minute rest, 500m\n"
            "Do 500m, then 1 minute rest, then 500m again, then finish "
            "with one more 500m."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_multiset_value_exceeded_distance_k_unparsed(self):
        # Same as above with 'k' distance units and a third restatement.
        text = (
            "1k, 1 minute rest, 1k\n"
            "Do 1k, then 1 minute rest, then 1k again, then finish with "
            "one more 1k."
        )
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_multiset_kind_mismatch_unparsed(self):
        # '500 calories' outside the span has the right VALUE (500) but
        # the wrong unit-kind (calories, not distance) -- kind mismatch
        # must reject, not silently match on the number alone.
        text = "500m, 1 minute rest, 500m\nthen 500 calories"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_repeat_cue_n_rounds_unparsed(self):
        text = "500m, 1 minute rest, 500m\n5 rounds"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_repeat_cue_twice_unparsed(self):
        text = "500m, 1 minute rest, 500m\nDo it twice"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_repeat_cue_leading_rounds_unparsed(self):
        text = "Row 2 rounds\n500m, 1 minute rest, 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_duplicate_lines_ambiguous_unparsed(self):
        # Two identical chain lines: ambiguous between "the same workout
        # restated" and "do it twice" (an outer-repeat this spec cannot
        # express) -- refusing is safer than guessing either way.
        text = "500m, 1 minute rest, 500m\n500m, 1 minute rest, 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_finish_with_unparsed(self):
        # "Finish with 500m" -- a lead-in word other than a bare article
        # right before the FIRST outside work mention means a tacked-on
        # extra piece, not a restatement, even though the in-order
        # subsequence check alone would have had room for one more 500m.
        text = "500m, 1 minute rest, 500m\nFinish with 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_then_unparsed(self):
        text = "1k, 1 minute rest, 1k\nthen 1k"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_then_cooldown_unparsed(self):
        text = "2000m/3 minutes rest/1000m/2 minutes rest/500m\nthen 2000m cool down"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_then_easy_unparsed(self):
        # '10 minutes easy' isn't unambiguously a rest mention ('easy'
        # is used for both work and rest elsewhere in this module), so
        # it's treated as the first outside WORK mention -- and it has
        # a 'then' right before it.
        text = "3000m, 3 minutes rest, 10 minutes work\nthen 10 minutes easy"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_comma_unparsed(self):
        # A whitelist, not a blacklist: any lead-in word other than a
        # bare article rejects, no matter how it's punctuated.
        text = "500m, 1 minute rest, 500m\nThen, 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_next_dash_unparsed(self):
        text = "500m, 1 minute rest, 500m\nNext - 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_then_another_unparsed(self):
        text = "500m, 1 minute rest, 500m\nThen another 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_afterwards_unparsed(self):
        text = "500m, 1 minute rest, 500m\nAfterwards 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_plus_unparsed(self):
        text = "500m, 1 minute rest, 500m\nPlus 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_and_another_unparsed(self):
        text = "500m, 1 minute rest, 500m\nand another 500m"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_leading_cue_rest_then_and_more_unparsed(self):
        # The rest mention ('1 minute rest') is skipped when hunting for
        # the first WORK mention, but the 'and' directly before '500m'
        # still isn't a bare article -- reject.
        text = "500m, 1 minute rest, 500m\nThen 1 minute rest and 500m more"
        self.assertIsNone(spec.parse_spec(text, "All Machines"))

    def test_variable_chain_rest_cued_lead_in_before_article_accepted(self):
        # A preceding rest mention (cued 'rest') plus its own connecting
        # words don't matter -- only what's directly adjacent to the
        # first WORK mention counts, and here that's a bare 'a'.
        text = (
            "3000m, 3 minutes rest, 10 minutes work\n"
            "Then 3 minutes rest before a 10 minute piece"
        )
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_variable")
        self.assertEqual(len(s["intervals"]), 2)


class ParseSpecLeftoverCueGuardSinglesTest(unittest.TestCase):
    """Framing/event text containing a rest-cue word (e.g. 'then',
    'between') in a *different sentence* from any number+unit work token
    must not trip the leftover-cue guard for singles -- the guard is
    sentence-scoped (see _leftover_cue_guard / _sentence_disqualifies_single
    in spec.py)."""

    def test_single_distance_time_trial_still_parses(self):
        s = spec.parse_spec("5000m time trial", "All Machines")
        self.assertEqual(s["kind"], "single_distance")
        self.assertEqual(s["work"], {"distance_m": 5000})

    def test_single_time_minutes_still_parses(self):
        s = spec.parse_spec("30 minutes", "All Machines")
        self.assertEqual(s["kind"], "single_time")
        self.assertEqual(s["work"], {"time_s": 1800})

    def test_single_calorie_still_parses(self):
        s = spec.parse_spec("250 Calories", "All Machines")
        self.assertEqual(s["kind"], "single_calorie")
        self.assertEqual(s["work"], {"calories": 250})

    def test_world_rowing_virtual_indoor_sprints_still_parses(self):
        # Contains a lone "between" ("...taking place between March
        # 6-10, 2024...") that is narrative framing, not a rest cue.
        text = (
            "1000m for the 2024 World Rowing Virtual Indoor Sprints\n"
            "Complete 1000m as fast as you can. (BikeErg:2000m) *The "
            "World Rowing Virtual Indoor Sprints are taking place "
            "between March 6-10, 2024. To take part you need to row "
            "1000m. More details can be found in the Challenges section "
            "of the Concept2 logbook."
        )
        s = spec.parse_spec(text, "RowErg and SkiErg")
        self.assertEqual(s["kind"], "single_distance")
        self.assertEqual(s["work"], {"distance_m": 1000})


class ParseSpecLeftoverCueGuardIntervalsTest(unittest.TestCase):
    """pm5-7bk.2: the leftover-cue guard also applies to fixed
    intervals_* and intervals_variable results, not just singles -- a
    warm-up/cool-down/'then' cue co-occurring with a number+unit work
    token in the same sentence signals an extra leg the interval match
    didn't capture and rejects the whole spec. It stays sentence-scoped
    (a bare cue word with no accompanying duration in the same sentence
    is not disqualifying), and it does not fire on the matched
    interval's own rest-word suffix (e.g. 'rest' in '8 x 500m, 2
    minutes rest' -- see _INTERVAL_LEFTOVER_CUE_WORDS_RE in spec.py)."""

    def test_fixed_interval_slash_still_parses_no_regression(self):
        s = spec.parse_spec("10 x 1 min / 1 min easy", "All Machines")
        self.assertEqual(s["kind"], "intervals_time")
        self.assertEqual(s["work"], {"time_s": 60})
        self.assertEqual(s["rest_s"], 60)
        self.assertEqual(s["count"], 10)

    def test_fixed_interval_with_rest_word_still_parses_no_regression(self):
        s = spec.parse_spec("8 x 500m, 2 minutes rest", "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 500})
        self.assertEqual(s["rest_s"], 120)
        self.assertEqual(s["count"], 8)

    def test_cue_word_without_accompanying_number_still_parses(self):
        # A cue word alone, with no number+unit token in the same
        # sentence, is not disqualifying -- the guard needs both.
        text = "8 x 500m, 2 minutes rest\nWarm up well first."
        s = spec.parse_spec(text, "All Machines")
        self.assertEqual(s["kind"], "intervals_distance")
        self.assertEqual(s["work"], {"distance_m": 500})
        self.assertEqual(s["rest_s"], 120)
        self.assertEqual(s["count"], 8)


class ParseSpecSentenceScopedCueGuardProbeTest(unittest.TestCase):
    """Reviewer's probe table for the sentence-scoped leftover-cue guard
    (fastmail-es5.16, second review pass): a rest/chaining cue word only
    disqualifies a single_* result when it occurs in the same sentence as
    a number+unit work token (date-context 'between' excluded), and two
    or more number+unit work tokens in one sentence disqualify a single
    regardless of cue words."""

    def test_500m_then_1000m_unparsed(self):
        self.assertIsNone(spec.parse_spec("500m then 1000m", "All Machines"))

    def test_1000m_rest_1000m_unparsed(self):
        self.assertIsNone(spec.parse_spec("1000m, rest, 1000m", "All Machines"))

    def test_30_minutes_on_30_minutes_off_unparsed(self):
        self.assertIsNone(spec.parse_spec("30 minutes on, 30 minutes off", "All Machines"))

    def test_5k_with_2k_warmup_unparsed(self):
        self.assertIsNone(spec.parse_spec("5k with a 2k warmup", "All Machines"))

    def test_2000m_followed_by_1000m_unparsed(self):
        self.assertIsNone(spec.parse_spec("2000m followed by 1000m", "All Machines"))

    def test_2000m_3_minutes_rest_1000m_unparsed_or_ladder(self):
        # Either unparsed, or a correct 2000m/3min-rest/1000m variable
        # ladder -- but never a single_distance guess.
        s = spec.parse_spec("2000m, 3 minutes rest, 1000m", "All Machines")
        if s is not None:
            self.assertNotEqual(s["kind"], "single_distance")

    def test_row_5000m_then_ski_5000m_unparsed(self):
        self.assertIsNone(spec.parse_spec("row 5000m, then ski 5000m", "All Machines"))

    def test_2000m_easy_may_stay_single(self):
        # "may stay a single" per the coordinator's probe: either outcome
        # is acceptable, but if a spec is returned it must be the correct
        # single_distance(2000), never a guessed interval/other kind.
        s = spec.parse_spec("2000m easy", "All Machines")
        if s is not None:
            self.assertEqual(s["kind"], "single_distance")
            self.assertEqual(s["work"], {"distance_m": 2000})

    def test_probe_already_passing_rounds_of_easy_between_unparsed(self):
        self.assertIsNone(
            spec.parse_spec(
                "6 rounds of 500m, easy 90 seconds between each",
                "All Machines",
            )
        )

    def test_probe_already_passing_rest_then_unparsed(self):
        self.assertIsNone(spec.parse_spec("2000m with 3 minutes rest then 1000m", "All Machines"))

    def test_probe_already_passing_nested_sets_unparsed(self):
        self.assertIsNone(spec.parse_spec("3 sets of 4 x 250m with 45 seconds off", "All Machines"))

    def test_probe_already_passing_5_x_500m_unparsed(self):
        self.assertIsNone(spec.parse_spec("5 x 500m", "All Machines"))


if __name__ == "__main__":
    unittest.main()
