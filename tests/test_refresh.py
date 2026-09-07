# Run from repo root: python -m unittest discover -s tests -t .

"""Unit tests for scripts/refresh.py.

scripts/ is a standalone script directory, not part of the pm5keys
package, so this module loads scripts/refresh.py directly via
importlib rather than a normal package import.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import tempfile
import unittest
from unittest import mock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REFRESH_PATH = os.path.join(_REPO_ROOT, "scripts", "refresh.py")

_spec = importlib.util.spec_from_file_location("refresh", _REFRESH_PATH)
refresh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refresh)


def _write_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------------------------
# compute_since
# ---------------------------------------------------------------------------


class ComputeSinceTest(unittest.TestCase):
    def test_day_after_max_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dataset.jsonl")
            _write_jsonl(
                path,
                [
                    {"date": "2026-09-05"},
                    {"date": "2026-09-07"},
                    {"date": "2026-09-06"},
                ],
            )
            self.assertEqual(refresh.compute_since(path), "2026-09-08")

    def test_missing_file_falls_back_to_fetch_default_since(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "does_not_exist.jsonl")
            fetch_mod = importlib.import_module("pm5keys.data.fetch")
            self.assertEqual(refresh.compute_since(path), fetch_mod.DEFAULT_SINCE)

    def test_empty_file_falls_back_to_fetch_default_since(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dataset.jsonl")
            with open(path, "w", encoding="utf-8"):
                pass
            fetch_mod = importlib.import_module("pm5keys.data.fetch")
            self.assertEqual(refresh.compute_since(path), fetch_mod.DEFAULT_SINCE)

    def test_single_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dataset.jsonl")
            _write_jsonl(path, [{"date": "2026-01-01"}])
            self.assertEqual(refresh.compute_since(path), "2026-01-02")


# ---------------------------------------------------------------------------
# parse_verify_summary
# ---------------------------------------------------------------------------


class ParseVerifySummaryTest(unittest.TestCase):
    def test_parses_all_categories(self):
        output = (
            "Per-category counts:\n"
            "  EXACT: 108\n"
            "  EQUIVALENT: 4\n"
            "  GOLD_VARIABLE: 3\n"
            "  GOLD_MISMATCH: 1\n"
            "  MODEL_ERROR: 0\n"
            "  TOTAL: 116\n"
        )
        counts = refresh.parse_verify_summary(output)
        self.assertEqual(
            counts,
            {
                "exact": 108,
                "equivalent": 4,
                "gold_variable": 3,
                "gold_mismatch": 1,
                "model_error": 0,
            },
        )

    def test_missing_categories_default_to_zero(self):
        output = "Per-category counts:\n  EXACT: 5\n  TOTAL: 5\n"
        counts = refresh.parse_verify_summary(output)
        self.assertEqual(counts["exact"], 5)
        self.assertEqual(counts["model_error"], 0)
        self.assertEqual(counts["gold_mismatch"], 0)

    def test_ignores_skipped_line_and_pm3_extra_output(self):
        output = (
            "Per-category counts:\n"
            "  EXACT: 103\n"
            "  EQUIVALENT: 4\n"
            "  GOLD_VARIABLE: 3\n"
            "  GOLD_MISMATCH: 1\n"
            "  MODEL_ERROR: 0\n"
            "  TOTAL: 111\n"
            "  SKIPPED (null pm34, e.g. calorie workouts): 5\n"
        )
        counts = refresh.parse_verify_summary(output)
        self.assertEqual(counts["exact"], 103)
        self.assertEqual(counts["gold_mismatch"], 1)

    def test_no_recognised_lines_raises_value_error(self):
        with self.assertRaises(ValueError):
            refresh.parse_verify_summary("some unrelated output\nwith no counts at all\n")

    def test_empty_output_raises_value_error(self):
        with self.assertRaises(ValueError):
            refresh.parse_verify_summary("")


# ---------------------------------------------------------------------------
# baseline comparison
# ---------------------------------------------------------------------------


class CheckAgainstBaselineTest(unittest.TestCase):
    def setUp(self):
        self.baseline = {"pm5": {"gold_mismatch": 1}, "pm3": {"gold_mismatch": 1}}

    def test_within_baseline_passes(self):
        counts = {"gold_mismatch": 1, "model_error": 0}
        failures = refresh.check_against_baseline("pm5", counts, self.baseline)
        self.assertEqual(failures, [])

    def test_below_baseline_passes(self):
        counts = {"gold_mismatch": 0, "model_error": 0}
        failures = refresh.check_against_baseline("pm5", counts, self.baseline)
        self.assertEqual(failures, [])

    def test_exceeding_baseline_fails(self):
        counts = {"gold_mismatch": 2, "model_error": 0}
        failures = refresh.check_against_baseline("pm5", counts, self.baseline)
        self.assertEqual(len(failures), 1)
        self.assertIn("GOLD_MISMATCH", failures[0])
        self.assertIn("2", failures[0])
        self.assertIn("1", failures[0])

    def test_model_error_always_fails(self):
        counts = {"gold_mismatch": 1, "model_error": 1}
        failures = refresh.check_against_baseline("pm5", counts, self.baseline)
        self.assertEqual(len(failures), 1)
        self.assertIn("MODEL_ERROR", failures[0])

    def test_both_model_error_and_gold_mismatch_exceeded_reports_both(self):
        counts = {"gold_mismatch": 5, "model_error": 2}
        failures = refresh.check_against_baseline("pm5", counts, self.baseline)
        self.assertEqual(len(failures), 2)

    def test_monitor_missing_from_baseline_treated_as_zero(self):
        counts = {"gold_mismatch": 1, "model_error": 0}
        failures = refresh.check_against_baseline("pm4", counts, self.baseline)
        self.assertEqual(len(failures), 1)
        self.assertIn("GOLD_MISMATCH", failures[0])


# ---------------------------------------------------------------------------
# _since_is_future
# ---------------------------------------------------------------------------


class SinceIsFutureTest(unittest.TestCase):
    def test_future_date_is_future(self):
        with mock.patch.object(refresh, "date") as mock_date:
            mock_date.today.return_value = datetime.date(2026, 9, 7)
            mock_date.fromisoformat.side_effect = datetime.date.fromisoformat
            self.assertTrue(refresh._since_is_future("2026-09-08"))

    def test_past_date_is_not_future(self):
        with mock.patch.object(refresh, "date") as mock_date:
            mock_date.today.return_value = datetime.date(2026, 9, 7)
            mock_date.fromisoformat.side_effect = datetime.date.fromisoformat
            self.assertFalse(refresh._since_is_future("2026-09-01"))


# ---------------------------------------------------------------------------
# main(): mocked subprocess end-to-end
# ---------------------------------------------------------------------------


def _ok_result(stdout: str = "") -> mock.Mock:
    result = mock.Mock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = ""
    return result


_PM5_VERIFY_OUTPUT = (
    "Per-category counts:\n"
    "  EXACT: 108\n"
    "  EQUIVALENT: 4\n"
    "  GOLD_VARIABLE: 3\n"
    "  GOLD_MISMATCH: 1\n"
    "  MODEL_ERROR: 0\n"
    "  TOTAL: 116\n"
)

_PM3_VERIFY_OUTPUT = (
    "Per-category counts:\n"
    "  EXACT: 103\n"
    "  EQUIVALENT: 4\n"
    "  GOLD_VARIABLE: 3\n"
    "  GOLD_MISMATCH: 1\n"
    "  MODEL_ERROR: 0\n"
    "  TOTAL: 111\n"
    "  SKIPPED (null pm34, e.g. calorie workouts): 5\n"
)


class MainMockedSubprocessTest(unittest.TestCase):
    def _make_dirs(self, tmpdir):
        raw_dir = os.path.join(tmpdir, "raw")
        out_dir = os.path.join(tmpdir, "data")
        os.makedirs(raw_dir)
        os.makedirs(out_dir)
        dataset_path = os.path.join(out_dir, "dataset.jsonl")
        unique_path = os.path.join(out_dir, "dataset_unique.jsonl")
        _write_jsonl(dataset_path, [{"date": "2026-09-06"}, {"date": "2026-09-07"}])
        _write_jsonl(unique_path, [{"title": "x"}])
        baseline_path = os.path.join(out_dir, "reports")
        os.makedirs(baseline_path)
        with open(os.path.join(baseline_path, "verify_baseline.json"), "w", encoding="utf-8") as f:
            json.dump({"pm5": {"gold_mismatch": 1}, "pm3": {"gold_mismatch": 1}}, f)
        return raw_dir, out_dir

    def test_main_returns_zero_when_within_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir, out_dir = self._make_dirs(tmpdir)
            baseline_arg = os.path.join(out_dir, "reports", "verify_baseline.json")

            responses = [
                _ok_result(),  # build
                _ok_result(),  # check
                _ok_result(),  # split
                _ok_result(),  # spec --coverage
                _ok_result(_PM5_VERIFY_OUTPUT),  # compile_keys --verify (pm5)
                _ok_result(_PM3_VERIFY_OUTPUT),  # compile_keys --verify --monitor pm3
                _ok_result(),  # tests.test_dataset_doc
            ]

            with (
                mock.patch.object(refresh, "_since_is_future", return_value=True),
                mock.patch("subprocess.run", side_effect=responses),
            ):
                exit_code = refresh.main(
                    [
                        "--raw",
                        raw_dir,
                        "--out",
                        out_dir,
                        "--since",
                        "2026-09-08",
                        "--baseline",
                        baseline_arg,
                    ]
                )

            self.assertEqual(exit_code, 0)

    def test_main_returns_one_when_gold_mismatch_exceeds_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir, out_dir = self._make_dirs(tmpdir)
            baseline_arg = os.path.join(out_dir, "reports", "verify_baseline.json")

            bad_pm5_output = _PM5_VERIFY_OUTPUT.replace("GOLD_MISMATCH: 1", "GOLD_MISMATCH: 2")

            responses = [
                _ok_result(),  # build
                _ok_result(),  # check
                _ok_result(),  # split
                _ok_result(),  # spec --coverage
                _ok_result(bad_pm5_output),  # compile_keys --verify (pm5)
                _ok_result(_PM3_VERIFY_OUTPUT),  # compile_keys --verify --monitor pm3
                _ok_result(),  # tests.test_dataset_doc
            ]

            with (
                mock.patch.object(refresh, "_since_is_future", return_value=True),
                mock.patch("subprocess.run", side_effect=responses),
            ):
                exit_code = refresh.main(
                    [
                        "--raw",
                        raw_dir,
                        "--out",
                        out_dir,
                        "--since",
                        "2026-09-08",
                        "--baseline",
                        baseline_arg,
                    ]
                )

            self.assertEqual(exit_code, 1)

    def test_main_returns_one_when_model_error_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir, out_dir = self._make_dirs(tmpdir)
            baseline_arg = os.path.join(out_dir, "reports", "verify_baseline.json")

            bad_pm3_output = _PM3_VERIFY_OUTPUT.replace("MODEL_ERROR: 0", "MODEL_ERROR: 1")

            responses = [
                _ok_result(),  # build
                _ok_result(),  # check
                _ok_result(),  # split
                _ok_result(),  # spec --coverage
                _ok_result(_PM5_VERIFY_OUTPUT),  # compile_keys --verify (pm5)
                _ok_result(bad_pm3_output),  # compile_keys --verify --monitor pm3
                _ok_result(),  # tests.test_dataset_doc
            ]

            with (
                mock.patch.object(refresh, "_since_is_future", return_value=True),
                mock.patch("subprocess.run", side_effect=responses),
            ):
                exit_code = refresh.main(
                    [
                        "--raw",
                        raw_dir,
                        "--out",
                        out_dir,
                        "--since",
                        "2026-09-08",
                        "--baseline",
                        baseline_arg,
                    ]
                )

            self.assertEqual(exit_code, 1)

    def test_main_returns_one_when_a_pipeline_command_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir, out_dir = self._make_dirs(tmpdir)
            baseline_arg = os.path.join(out_dir, "reports", "verify_baseline.json")

            failed_build = mock.Mock()
            failed_build.returncode = 1
            failed_build.stdout = ""
            failed_build.stderr = "boom"

            with (
                mock.patch.object(refresh, "_since_is_future", return_value=True),
                mock.patch("subprocess.run", return_value=failed_build),
            ):
                exit_code = refresh.main(
                    [
                        "--raw",
                        raw_dir,
                        "--out",
                        out_dir,
                        "--since",
                        "2026-09-08",
                        "--baseline",
                        baseline_arg,
                    ]
                )

            self.assertEqual(exit_code, 1)

    def test_dry_run_does_not_invoke_subprocess(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir, out_dir = self._make_dirs(tmpdir)
            baseline_arg = os.path.join(out_dir, "reports", "verify_baseline.json")

            with mock.patch("subprocess.run") as mock_run:
                exit_code = refresh.main(
                    [
                        "--raw",
                        raw_dir,
                        "--out",
                        out_dir,
                        "--since",
                        "2026-09-08",
                        "--baseline",
                        baseline_arg,
                        "--dry-run",
                    ]
                )
                mock_run.assert_not_called()

            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
