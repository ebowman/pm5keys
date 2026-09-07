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
