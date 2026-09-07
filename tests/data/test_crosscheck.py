# Run from repo root: python -m unittest discover -s tests -t .

import os
import unittest

from pm5keys.data import crosscheck as crosscheck_email

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(TESTS_DIR)
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures", "email")
RAW_DIR = os.path.join(REPO_ROOT, "raw")


class CrosscheckEmailTest(unittest.TestCase):
    def test_all_available_pairs_match(self):
        """For every tests/fixtures/email/*.txt fixture that has a
        matching raw/YYYY-MM-DD.html page available locally, parse_text
        on the email body and parse_html on the raw page must agree on
        title, description, and groups. raw/ is gitignored, so on a
        fresh clone with no raw pages present, every fixture is skipped
        and the test still passes (nothing to assert against).
        """
        rows, any_mismatch = crosscheck_email.run_crosscheck(FIXTURES_DIR, RAW_DIR)

        self.assertGreater(len(rows), 0, "expected at least one email fixture")

        mismatches = [row for row in rows if row["status"] == "mismatch"]
        self.assertEqual(
            mismatches,
            [],
            f"email/web mismatch(es): {mismatches}",
        )
        self.assertFalse(any_mismatch)

        # At least sanity-check that not every row silently skipped due
        # to a misconfigured raw dir path -- if raw/ exists at all,
        # expect at least one non-skipped row.
        if os.path.isdir(RAW_DIR) and os.listdir(RAW_DIR):
            non_skipped = [row for row in rows if row["status"] != "skipped"]
            self.assertGreater(
                len(non_skipped),
                0,
                "raw/ has files but every fixture was skipped",
            )


if __name__ == "__main__":
    unittest.main()
