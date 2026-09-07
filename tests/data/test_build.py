# Run from repo root: python -m unittest discover -s tests -t .

import unittest

from pm5keys import keyseq
from pm5keys.data import build as build_dataset


def _record(date, title, description, groups):
    return {
        "date": date,
        "title": title,
        "description": description,
        "groups": groups,
        "honorboard_url": None,
        "source": "web",
    }


class BuildRowsTest(unittest.TestCase):
    def test_valid_pm5_and_pm34_kept(self):
        records = [
            _record(
                "2026-01-01",
                "Steady State",
                "Row easy.",
                [{"machines": "All Machines", "pm34": "B-2D-5A", "pm5": "B-2D-5A"}],
            )
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rejects, [])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["date"], "2026-01-01")
        self.assertEqual(row["machines"], "All Machines")
        self.assertEqual(row["title"], "Steady State")
        self.assertEqual(row["description"], "Row easy.")
        self.assertEqual(row["pm5"], keyseq.canonical("B-2D-5A"))
        self.assertEqual(row["pm5_expanded"], keyseq.expand("B-2D-5A"))
        self.assertEqual(row["pm34"], "B-2D-5A")
        self.assertEqual(
            row["source_url"],
            "https://utilities.concept2.com/wod-email/newsletter/2026-01-01/en/us",
        )

    def test_free_text_pm34_nulled_but_row_kept(self):
        records = [
            _record(
                "2026-01-02",
                "Interval Cals",
                "Calorie intervals.",
                [
                    {
                        "machines": "All Machines",
                        "pm34": "The PM3 and PM4 monitors do not support interval calorie workouts",
                        "pm5": "5A-5B",
                    }
                ],
            )
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rejects, [])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["pm34"])
        self.assertEqual(rows[0]["pm5"], keyseq.canonical("5A-5B"))

    def test_missing_pm5_rejected(self):
        records = [
            _record(
                "2026-01-03",
                "No PM5",
                "Some description.",
                [{"machines": "All Machines", "pm34": "B-2D", "pm5": None}],
            )
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rows, [])
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["reason"], "missing pm5")
        self.assertEqual(rejects[0]["date"], "2026-01-03")
        self.assertEqual(
            rejects[0]["group"],
            {"machines": "All Machines", "pm34": "B-2D", "pm5": None},
        )

    def test_invalid_pm5_rejected(self):
        records = [
            _record(
                "2026-01-04",
                "Bad Sequence",
                "Some description.",
                [{"machines": "All Machines", "pm34": None, "pm5": "B-Z"}],
            )
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rows, [])
        self.assertEqual(len(rejects), 1)
        self.assertIn("invalid pm5", rejects[0]["reason"])
        self.assertEqual(rejects[0]["group"]["pm5"], "B-Z")

    def test_multiple_groups_preserve_order_within_date(self):
        records = [
            _record(
                "2026-01-05",
                "Two Groups",
                "Description.",
                [
                    {"machines": "RowErg and SkiErg", "pm34": "A", "pm5": "A"},
                    {"machines": "BikeErg", "pm34": "B", "pm5": "B"},
                ],
            )
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rejects, [])
        self.assertEqual([r["machines"] for r in rows], ["RowErg and SkiErg", "BikeErg"])

    def test_rows_sorted_by_date(self):
        records = [
            _record(
                "2026-01-10",
                "Later",
                "Desc.",
                [{"machines": "All Machines", "pm34": None, "pm5": "A"}],
            ),
            _record(
                "2026-01-01",
                "Earlier",
                "Desc.",
                [{"machines": "All Machines", "pm34": None, "pm5": "B"}],
            ),
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rejects, [])
        self.assertEqual([r["date"] for r in rows], ["2026-01-01", "2026-01-10"])


class DedupeTest(unittest.TestCase):
    def test_merges_rows_differing_only_in_whitespace_and_case(self):
        rows = [
            {
                "date": "2026-02-01",
                "machines": "All Machines",
                "title": "Steady State",
                "description": "Row  easy.",
                "pm5": "A",
                "pm5_expanded": ["A"],
                "pm34": None,
                "source_url": "u1",
            },
            {
                "date": "2026-02-05",
                "machines": "All Machines",
                "title": "steady state",
                "description": "row easy.",
                "pm5": "A",
                "pm5_expanded": ["A"],
                "pm34": "A",
                "source_url": "u2",
            },
        ]
        unique_rows = build_dataset.dedupe(rows)
        self.assertEqual(len(unique_rows), 1)
        entry = unique_rows[0]
        self.assertEqual(entry["count"], 2)
        self.assertEqual(entry["dates"], ["2026-02-01", "2026-02-05"])
        self.assertEqual(entry["first_date"], "2026-02-01")
        self.assertEqual(entry["last_date"], "2026-02-05")
        # first-seen original text is kept, not the second row's variant
        self.assertEqual(entry["title"], "Steady State")
        self.assertEqual(entry["description"], "Row  easy.")
        # first non-null pm34 seen across the merged rows
        self.assertEqual(entry["pm34"], "A")

    def test_distinct_machines_or_pm5_not_merged(self):
        rows = [
            {
                "date": "2026-03-01",
                "machines": "All Machines",
                "title": "X",
                "description": "Y",
                "pm5": "A",
                "pm5_expanded": ["A"],
                "pm34": None,
                "source_url": "u1",
            },
            {
                "date": "2026-03-02",
                "machines": "BikeErg",
                "title": "X",
                "description": "Y",
                "pm5": "A",
                "pm5_expanded": ["A"],
                "pm34": None,
                "source_url": "u2",
            },
            {
                "date": "2026-03-03",
                "machines": "All Machines",
                "title": "X",
                "description": "Y",
                "pm5": "B",
                "pm5_expanded": ["B"],
                "pm34": None,
                "source_url": "u3",
            },
        ]
        unique_rows = build_dataset.dedupe(rows)
        self.assertEqual(len(unique_rows), 3)

    def test_sorted_by_count_desc_then_first_date(self):
        rows = [
            {
                "date": "2026-04-01",
                "machines": "All Machines",
                "title": "Once",
                "description": "d1",
                "pm5": "A",
                "pm5_expanded": ["A"],
                "pm34": None,
                "source_url": "u1",
            },
            {
                "date": "2026-04-02",
                "machines": "All Machines",
                "title": "Twice-a",
                "description": "d2",
                "pm5": "B",
                "pm5_expanded": ["B"],
                "pm34": None,
                "source_url": "u2",
            },
            {
                "date": "2026-04-09",
                "machines": "All Machines",
                "title": "Twice-a",
                "description": "d2",
                "pm5": "B",
                "pm5_expanded": ["B"],
                "pm34": None,
                "source_url": "u3",
            },
        ]
        unique_rows = build_dataset.dedupe(rows)
        self.assertEqual(len(unique_rows), 2)
        self.assertEqual(unique_rows[0]["title"], "Twice-a")
        self.assertEqual(unique_rows[0]["count"], 2)
        self.assertEqual(unique_rows[1]["title"], "Once")
        self.assertEqual(unique_rows[1]["count"], 1)


class NoNetworkNoRawDependenceTest(unittest.TestCase):
    def test_build_rows_and_dedupe_are_pure_in_memory(self):
        # This test intentionally never touches wod/raw or the network:
        # build_rows/dedupe operate purely on in-memory record/row lists.
        records = [
            _record(
                "2026-05-01",
                "Pure",
                "In memory only.",
                [{"machines": "All Machines", "pm34": None, "pm5": "2A-B"}],
            )
        ]
        rows, rejects = build_dataset.build_rows(records)
        self.assertEqual(rejects, [])
        unique_rows = build_dataset.dedupe(rows)
        self.assertEqual(len(unique_rows), 1)
        self.assertEqual(unique_rows[0]["count"], 1)


if __name__ == "__main__":
    unittest.main()
