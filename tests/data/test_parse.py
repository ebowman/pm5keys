# Run from repo root: python -m unittest discover -s tests -t .

import os
import unittest

from pm5keys.data import parse as parse_wod

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
WEB_DIR = os.path.join(FIXTURES_DIR, "web")
EMAIL_DIR = os.path.join(FIXTURES_DIR, "email")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class HtmlToTextTest(unittest.TestCase):
    def test_drops_script_and_style(self):
        html = (
            "<html><head><style>body { color: red; }</style></head>"
            "<body><script>alert('hi');</script><p>Hello world</p></body></html>"
        )
        text = parse_wod.html_to_text(html)
        self.assertNotIn("color: red", text)
        self.assertNotIn("alert", text)
        self.assertIn("Hello world", text)


class ParseHtmlSingleGroupTest(unittest.TestCase):
    """2026-09-07 fixture: single 'All Machines' group."""

    @classmethod
    def setUpClass(cls):
        html = _read(os.path.join(WEB_DIR, "2026-09-07.html"))
        cls.record = parse_wod.parse_html(html, "2026-09-07")

    def test_title(self):
        self.assertEqual(
            self.record["title"],
            "1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest",
        )

    def test_description(self):
        self.assertEqual(
            self.record["description"],
            "An interval pyramid starting at 1 minute, increasing by 1 "
            "minute each interval to a maximum of 5 minutes and then back "
            "down again. 2 minutes rest between intervals.",
        )

    def test_single_group(self):
        self.assertEqual(len(self.record["groups"]), 1)
        group = self.record["groups"][0]
        self.assertEqual(group["machines"], "All Machines")
        self.assertEqual(
            group["pm5"],
            "B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E",
        )

    def test_honorboard_url(self):
        self.assertEqual(
            self.record["honorboard_url"],
            "https://log.concept2.com/wod/2026-09-07/rowerg",
        )

    def test_source_and_date(self):
        self.assertEqual(self.record["source"], "web")
        self.assertEqual(self.record["date"], "2026-09-07")

    def test_no_warnings(self):
        self.assertNotIn("warnings", self.record)


class ParseHtmlMultiGroupTest(unittest.TestCase):
    """2026-02-01 fixture: two groups (RowErg/SkiErg, BikeErg)."""

    @classmethod
    def setUpClass(cls):
        html = _read(os.path.join(WEB_DIR, "2026-02-01.html"))
        cls.record = parse_wod.parse_html(html, "2026-02-01")

    def test_title_and_description(self):
        self.assertEqual(self.record["title"], "8 x 500m, 2 minutes rest")
        self.assertEqual(
            self.record["description"],
            "8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)",
        )

    def test_groups(self):
        expected = [
            {
                "machines": "RowErg and SkiErg",
                "pm34": "B-D-C-4A-2B-E",
                "pm5": "B-2D-5A-2B-E",
            },
            {
                "machines": "BikeErg",
                "pm34": "B-D-C-D-B-A-5C-4A-2B-E",
                "pm5": "B-2D-A-D-B-A-5C-4A-2B-E",
            },
        ]
        self.assertEqual(self.record["groups"], expected)

    def test_honorboard_url(self):
        self.assertEqual(
            self.record["honorboard_url"],
            "https://log.concept2.com/wod/2026-02-01/rowerg",
        )


class ParseHtml2023FixtureTest(unittest.TestCase):
    def test_pm5(self):
        html = _read(os.path.join(WEB_DIR, "2023-06-15.html"))
        record = parse_wod.parse_html(html, "2023-06-15")
        self.assertEqual(len(record["groups"]), 1)
        self.assertEqual(
            record["groups"][0]["pm5"],
            "B-3D-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E",
        )


class ParseEmailMatchesWebTest(unittest.TestCase):
    """The email fixture for 2026-02-01 must yield the identical
    title/description/groups as the web fixture for the same date.
    """

    def test_email_matches_web(self):
        email_text = _read(os.path.join(EMAIL_DIR, "2026-02-01.txt"))
        email_record = parse_wod.parse_text(email_text, "2026-02-01", source="email")

        web_html = _read(os.path.join(WEB_DIR, "2026-02-01.html"))
        web_record = parse_wod.parse_html(web_html, "2026-02-01")

        self.assertEqual(email_record["title"], web_record["title"])
        self.assertEqual(email_record["description"], web_record["description"])
        self.assertEqual(email_record["groups"], web_record["groups"])
        self.assertEqual(email_record["source"], "email")
        self.assertEqual(web_record["source"], "web")

    def test_email_two_groups_exact(self):
        email_text = _read(os.path.join(EMAIL_DIR, "2026-02-01.txt"))
        record = parse_wod.parse_text(email_text, "2026-02-01", source="email")
        expected = [
            {
                "machines": "RowErg and SkiErg",
                "pm34": "B-D-C-4A-2B-E",
                "pm5": "B-2D-5A-2B-E",
            },
            {
                "machines": "BikeErg",
                "pm34": "B-D-C-D-B-A-5C-4A-2B-E",
                "pm5": "B-2D-A-D-B-A-5C-4A-2B-E",
            },
        ]
        self.assertEqual(record["groups"], expected)


class NoPmTextTest(unittest.TestCase):
    """Text with no PM lines at all must parse with groups == [] and no
    exception.
    """

    def test_no_pm_lines(self):
        text = (
            "View in Browser: https://example.com\n"
            "\n"
            "*****\n"
            "\n"
            "Rest Day\n"
            "\n"
            "Take today off, or go for an easy walk.\n"
            "\n"
            "******\n"
            "\n"
            "No button press sequence today.\n"
        )
        record = parse_wod.parse_text(text, "2026-03-01", source="email")
        self.assertEqual(record["groups"], [])
        self.assertEqual(record["title"], "Rest Day")
        self.assertEqual(
            record["description"],
            "Take today off, or go for an easy walk.",
        )
        self.assertNotIn("warnings", record)


class TitleDescriptionSyntheticTest(unittest.TestCase):
    """Synthetic text with a multi-line description, no markers (fallback
    path).
    """

    def test_multiline_description_no_markers(self):
        text = (
            "Some Title Here\n"
            "\n"
            "This is the first line of the description.\n"
            "This is the second line, still part of the same paragraph.\n"
            "\n"
            "This paragraph should not be included.\n"
        )
        record = parse_wod.parse_text(text, "2026-03-02", source="email")
        self.assertEqual(record["title"], "Some Title Here")
        self.assertEqual(
            record["description"],
            "This is the first line of the description. This is the "
            "second line, still part of the same paragraph.",
        )
        self.assertEqual(record["groups"], [])


class InvalidSequenceWarningTest(unittest.TestCase):
    def test_invalid_sequence_produces_warning(self):
        text = (
            "*****\n"
            "\n"
            "Bad Sequence Day\n"
            "\n"
            "A description.\n"
            "\n"
            "******\n"
            "\n"
            "All Machines\n"
            "PM3/PM4: B-D-Z-E\n"
            "PM5: B-2D-5A-2B-E\n"
        )
        record = parse_wod.parse_text(text, "2026-03-03", source="email")
        self.assertIn("warnings", record)
        self.assertTrue(any("pm34" in w for w in record["warnings"]))
        # Invalid raw string is still retained in the record.
        self.assertEqual(record["groups"][0]["pm34"], "B-D-Z-E")
        self.assertEqual(record["groups"][0]["pm5"], "B-2D-5A-2B-E")


if __name__ == "__main__":
    unittest.main()
