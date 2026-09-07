# Run from repo root: python -m unittest discover -s tests -t .

import unittest

from pm5keys.data import consistency as check_consistency


def _row(date, machines, title, description, pm5, pm5_expanded=None):
    return {
        "date": date,
        "machines": machines,
        "title": title,
        "description": description,
        "pm5": pm5,
        "pm5_expanded": pm5_expanded if pm5_expanded is not None else list(pm5.replace("-", "")),
        "pm34": None,
        "source_url": f"https://example.com/{date}",
    }


class LabelConflictsTest(unittest.TestCase):
    def test_same_description_different_pm5_is_a_conflict(self):
        rows = [
            _row("2022-01-01", "All Machines", "5 x 1000m", "Five 1000m pieces.", "B-2D-A"),
            _row("2022-02-01", "All Machines", "5 x 1000m", "Five 1000m pieces.", "B-2D-A"),
            _row("2022-03-01", "All Machines", "5 x 1000m", "Five 1000m pieces.", "B-2D-B"),
        ]
        conflicts = check_consistency.find_label_conflicts(rows)
        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict["machines"], "All Machines")
        self.assertEqual(len(conflict["variants"]), 2)
        pm5_values = {v["pm5"] for v in conflict["variants"]}
        self.assertEqual(pm5_values, {"B-2D-A", "B-2D-B"})
        # Variant with the higher count sorts first.
        self.assertEqual(conflict["variants"][0]["pm5"], "B-2D-A")
        self.assertEqual(conflict["variants"][0]["count"], 2)
        self.assertEqual(conflict["variants"][0]["date_range"], "2022-01-01..2022-02-01")
        self.assertEqual(conflict["variants"][1]["pm5"], "B-2D-B")
        self.assertEqual(conflict["variants"][1]["count"], 1)
        self.assertEqual(conflict["variants"][1]["date_range"], "2022-03-01")

    def test_whitespace_and_case_do_not_create_false_conflicts(self):
        rows = [
            _row("2022-01-01", "All Machines", "5 x 1000m", "Five  1000m pieces.", "B-2D-A"),
            _row("2022-02-01", "All Machines", "5 X 1000M", "five 1000m pieces.", "B-2D-A"),
            _row("2022-03-01", "All Machines", " 5 x 1000m ", "Five 1000m pieces.", "B-2D-A"),
        ]
        label_conflicts = check_consistency.find_label_conflicts(rows)
        title_conflicts = check_consistency.find_title_conflicts(rows)
        self.assertEqual(label_conflicts, [])
        self.assertEqual(title_conflicts, [])

    def test_different_machines_does_not_conflict(self):
        rows = [
            _row("2022-01-01", "All Machines", "5 x 1000m", "Five 1000m pieces.", "B-2D-A"),
            _row("2022-02-01", "BikeErg", "5 x 1000m", "Five 1000m pieces.", "B-2D-B"),
        ]
        conflicts = check_consistency.find_label_conflicts(rows)
        self.assertEqual(conflicts, [])


class TitleConflictsTest(unittest.TestCase):
    def test_same_title_different_description_and_pm5_is_a_1b_conflict_not_1(self):
        rows = [
            _row(
                "2022-01-01",
                "All Machines",
                "1000m",
                "One 1000m piece, all out.",
                "B-2D-A",
            ),
            _row(
                "2022-02-01",
                "All Machines",
                "1000m",
                "One 1000m time trial.",
                "B-2D-B",
            ),
        ]
        label_conflicts = check_consistency.find_label_conflicts(rows)
        title_conflicts = check_consistency.find_title_conflicts(rows)

        self.assertEqual(label_conflicts, [])  # descriptions differ, so no section-1 hit
        self.assertEqual(len(title_conflicts), 1)
        conflict = title_conflicts[0]
        self.assertEqual(conflict["title"], "1000m")
        self.assertEqual(conflict["machines"], "All Machines")
        self.assertEqual(len(conflict["variants"]), 2)
        pm5_values = {v["pm5"] for v in conflict["variants"]}
        self.assertEqual(pm5_values, {"B-2D-A", "B-2D-B"})


class DescriptionVariantsTest(unittest.TestCase):
    def test_same_pm5_different_description_is_a_section2_variant(self):
        rows = [
            _row("2022-01-01", "All Machines", "Steady State", "Row easy for 20 minutes.", "B-5D"),
            _row("2022-02-01", "All Machines", "Easy Row", "Take it slow for twenty.", "B-5D"),
            _row("2022-03-01", "All Machines", "Easy Row", "Take it slow for twenty.", "B-5D"),
        ]
        variants = check_consistency.find_description_variants(rows)
        self.assertEqual(len(variants), 1)
        variant = variants[0]
        self.assertEqual(variant["machines"], "All Machines")
        self.assertEqual(variant["pm5"], "B-5D")
        self.assertEqual(len(variant["descriptions"]), 2)
        # Higher count sorts first.
        self.assertEqual(variant["descriptions"][0]["count"], 2)
        self.assertEqual(variant["descriptions"][0]["description"], "Take it slow for twenty.")
        self.assertEqual(variant["descriptions"][1]["count"], 1)

    def test_identical_normalized_descriptions_are_not_a_variant(self):
        rows = [
            _row("2022-01-01", "All Machines", "Steady State", "Row  easy.", "B-5D"),
            _row("2022-02-01", "All Machines", "Steady State", "row easy.", "B-5D"),
        ]
        variants = check_consistency.find_description_variants(rows)
        self.assertEqual(variants, [])


class SequenceStatsTest(unittest.TestCase):
    def test_stats_computed_correctly(self):
        rows = [
            _row("2022-01-01", "All Machines", "A", "a", "B-2D-A", pm5_expanded=["B", "D", "D", "A"]),
            _row("2022-01-02", "All Machines", "B", "b", "B-3D-A", pm5_expanded=["B", "D", "D", "D", "A", "E"]),
            _row("2022-01-03", "BikeErg", "C", "c", "C-2A", pm5_expanded=["C", "A", "A", "E", "E", "E", "E", "E", "E", "E", "E"]),
        ]
        stats = check_consistency.sequence_stats(rows)

        self.assertEqual(stats["first_token_counts"], {"B": 2, "C": 1})
        self.assertEqual(stats["length_min"], 4)
        self.assertEqual(stats["length_median"], 6)
        self.assertEqual(stats["length_max"], 11)
        # Buckets of 5: 4 -> "0-4", 6 -> "5-9", 11 -> "10-14"
        self.assertEqual(
            stats["length_histogram"],
            [("0-4", 1), ("5-9", 1), ("10-14", 1)],
        )
        self.assertEqual(stats["machines_counts"], {"All Machines": 2, "BikeErg": 1})


class RenderMarkdownTest(unittest.TestCase):
    def test_render_includes_header_and_sections(self):
        rows = [
            _row("2022-01-01", "All Machines", "5 x 1000m", "Five 1000m pieces.", "B-2D-A"),
            _row("2022-02-01", "All Machines", "5 x 1000m", "Five 1000m pieces.", "B-2D-B"),
        ]
        label_conflicts = check_consistency.find_label_conflicts(rows)
        title_conflicts = check_consistency.find_title_conflicts(rows)
        description_variants = check_consistency.find_description_variants(rows)
        stats = check_consistency.sequence_stats(rows)

        markdown = check_consistency.render_markdown(
            "wod/dataset.jsonl",
            len(rows),
            label_conflicts,
            title_conflicts,
            description_variants,
            stats,
        )

        self.assertIn("generated, not hand-edited", markdown)
        self.assertIn("wod/dataset.jsonl", markdown)
        self.assertIn("2 rows", markdown)
        self.assertIn("1. Label conflicts", markdown)
        self.assertIn("1b. Title conflicts", markdown)
        self.assertIn("2. Same sequence, different descriptions", markdown)
        self.assertIn("3. Sanity tables", markdown)
        self.assertIn("5 x 1000m", markdown)
        self.assertIn("B-2D-A", markdown)
        self.assertIn("B-2D-B", markdown)


if __name__ == "__main__":
    unittest.main()
