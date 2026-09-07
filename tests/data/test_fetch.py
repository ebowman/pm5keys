# Run from repo root: python -m unittest discover -s tests -t .

import os
import tempfile
import unittest
import urllib.error
from unittest import mock

from pm5keys.data import fetch as fetch_wod


class IterDatesTest(unittest.TestCase):
    def test_inclusive_bounds(self):
        result = fetch_wod.iter_dates("2022-07-01", "2022-07-03")
        self.assertEqual(result, ["2022-07-01", "2022-07-02", "2022-07-03"])

    def test_single_day(self):
        result = fetch_wod.iter_dates("2022-07-01", "2022-07-01")
        self.assertEqual(result, ["2022-07-01"])

    def test_since_after_until_returns_empty(self):
        result = fetch_wod.iter_dates("2022-07-05", "2022-07-01")
        self.assertEqual(result, [])


class RunFetchTest(unittest.TestCase):
    def _noop_sleep(self, _seconds):
        pass

    def test_skip_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = os.path.join(tmpdir, "2022-07-01.html")
            with open(existing_path, "w", encoding="utf-8") as f:
                f.write("already here")

            fetch_fn = mock.Mock()

            result = fetch_wod.run_fetch(
                dates=["2022-07-01"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            fetch_fn.assert_not_called()
            self.assertEqual(result["present"], 1)
            self.assertEqual(result["fetched"], 0)
            with open(existing_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "already here")

    def test_force_refetch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = os.path.join(tmpdir, "2022-07-01.html")
            with open(existing_path, "w", encoding="utf-8") as f:
                f.write("stale content")

            fetch_fn = mock.Mock(return_value=(200, b"fresh content"))

            result = fetch_wod.run_fetch(
                dates=["2022-07-01"],
                out_dir=tmpdir,
                force=True,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            fetch_fn.assert_called_once()
            self.assertEqual(result["fetched"], 1)
            self.assertEqual(result["present"], 0)
            with open(existing_path, "rb") as f:
                self.assertEqual(f.read(), b"fresh content")

    def test_successful_fetch_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fetch_fn = mock.Mock(return_value=(200, b"<html>PM5</html>"))

            result = fetch_wod.run_fetch(
                dates=["2022-07-15"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            self.assertEqual(result["fetched"], 1)
            out_path = os.path.join(tmpdir, "2022-07-15.html")
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "rb") as f:
                self.assertEqual(f.read(), b"<html>PM5</html>")

    def test_http_500_retried_three_times_then_recorded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            error = urllib.error.HTTPError(
                url="http://example.com",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=None,
            )
            fetch_fn = mock.Mock(side_effect=error)
            sleep_fn = mock.Mock()

            result = fetch_wod.run_fetch(
                dates=["2022-06-15"],
                out_dir=tmpdir,
                force=False,
                delay=0.5,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=sleep_fn,
            )

            self.assertEqual(result["fetched"], 0)
            self.assertEqual(result["missing_count"], 1)
            # 1 initial attempt + 3 retries = 4 calls total.
            self.assertEqual(fetch_fn.call_count, 4)

            sleep_calls = [call.args[0] for call in sleep_fn.call_args_list]
            self.assertIn(1, sleep_calls)
            self.assertIn(2, sleep_calls)
            self.assertIn(4, sleep_calls)

            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(missing_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("2022-06-15 500", content)

    def test_http_500_succeeds_on_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            error = urllib.error.HTTPError(
                url="http://example.com",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=None,
            )
            fetch_fn = mock.Mock(side_effect=[error, (200, b"<html>PM5 recovered</html>")])

            result = fetch_wod.run_fetch(
                dates=["2022-07-17"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            self.assertEqual(result["fetched"], 1)
            self.assertEqual(fetch_fn.call_count, 2)
            out_path = os.path.join(tmpdir, "2022-07-17.html")
            with open(out_path, "rb") as f:
                self.assertEqual(f.read(), b"<html>PM5 recovered</html>")

    def test_http_404_not_retried(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            error = urllib.error.HTTPError(
                url="http://example.com",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            )
            fetch_fn = mock.Mock(side_effect=error)

            result = fetch_wod.run_fetch(
                dates=["2022-06-15"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            self.assertEqual(result["fetched"], 0)
            self.assertEqual(result["missing_count"], 1)
            # No retry on 4xx HTTPError.
            fetch_fn.assert_called_once()

            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(missing_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("2022-06-15 404", content)

    def test_network_error_retried_three_times_then_recorded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            error = urllib.error.URLError("connection refused")
            fetch_fn = mock.Mock(side_effect=error)
            sleep_fn = mock.Mock()

            result = fetch_wod.run_fetch(
                dates=["2022-07-15"],
                out_dir=tmpdir,
                force=False,
                delay=0.5,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=sleep_fn,
            )

            # 1 initial attempt + 3 retries = 4 calls total.
            self.assertEqual(fetch_fn.call_count, 4)
            self.assertEqual(result["fetched"], 0)
            self.assertEqual(result["missing_count"], 1)

            # Backoff sleeps of 1, 2, 4 should have occurred.
            sleep_calls = [call.args[0] for call in sleep_fn.call_args_list]
            self.assertIn(1, sleep_calls)
            self.assertIn(2, sleep_calls)
            self.assertIn(4, sleep_calls)

            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(missing_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("2022-07-15 ERR", content)
            self.assertIn("connection refused", content)

    def test_network_error_succeeds_on_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            error = urllib.error.URLError("temporary failure")
            fetch_fn = mock.Mock(side_effect=[error, error, (200, b"<html>PM5 recovered</html>")])

            result = fetch_wod.run_fetch(
                dates=["2022-07-16"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            self.assertEqual(result["fetched"], 1)
            self.assertEqual(fetch_fn.call_count, 3)
            out_path = os.path.join(tmpdir, "2022-07-16.html")
            with open(out_path, "rb") as f:
                self.assertEqual(f.read(), b"<html>PM5 recovered</html>")

    def test_missing_dedupe_no_duplicate_when_still_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(missing_path, "w", encoding="utf-8") as f:
                f.write("2022-06-15 500\n")

            error = urllib.error.HTTPError(
                url="http://example.com",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=None,
            )
            fetch_fn = mock.Mock(side_effect=error)

            fetch_wod.run_fetch(
                dates=["2022-06-15"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            with open(missing_path, "r", encoding="utf-8") as f:
                lines = [l for l in f.read().splitlines() if l.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0], "2022-06-15 500")

    def test_missing_dedupe_removed_when_now_successful(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(missing_path, "w", encoding="utf-8") as f:
                f.write("2022-07-15 500\n")

            fetch_fn = mock.Mock(return_value=(200, b"<html>PM5</html>"))

            fetch_wod.run_fetch(
                dates=["2022-07-15"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=None,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            with open(missing_path, "r", encoding="utf-8") as f:
                lines = [l for l in f.read().splitlines() if l.strip()]
            self.assertEqual(lines, [])

    def test_limit_stops_after_n_attempted_fetches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fetch_fn = mock.Mock(return_value=(200, b"<html>PM5</html>"))

            result = fetch_wod.run_fetch(
                dates=["2022-07-01", "2022-07-02", "2022-07-03"],
                out_dir=tmpdir,
                force=False,
                delay=0,
                limit=2,
                fetch_fn=fetch_fn,
                sleep_fn=self._noop_sleep,
            )

            self.assertEqual(result["attempted"], 2)
            self.assertEqual(result["fetched"], 2)
            self.assertEqual(fetch_fn.call_count, 2)


class LoadWriteMissingTest(unittest.TestCase):
    def test_round_trip_sorted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "missing.txt")
            data = {"2022-07-03": "500", "2022-07-01": "ERR timeout"}
            fetch_wod.write_missing(path, data)

            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(lines, ["2022-07-01 ERR timeout", "2022-07-03 500"])

            loaded = fetch_wod.load_missing(path)
            self.assertEqual(loaded, data)

    def test_missing_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "does-not-exist.txt")
            self.assertEqual(fetch_wod.load_missing(path), {})


class MainExitCodeTest(unittest.TestCase):
    """Regression tests for main()'s exit code: 0 if at least one page was
    fetched this run OR anything is already present on disk; 1 only on
    total failure (nothing fetched and nothing present). These call main()
    directly with fetch_wod._real_fetch_fn mocked so no network is touched.
    """

    def test_exit_0_when_some_present_and_rest_permanently_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-populate one date as already present on disk.
            present_path = os.path.join(tmpdir, "2022-07-08.html")
            with open(present_path, "w", encoding="utf-8") as f:
                f.write("already fetched")

            error = urllib.error.HTTPError(
                url="http://example.com",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=None,
            )

            with (
                mock.patch.object(fetch_wod, "_real_fetch_fn", side_effect=error),
                mock.patch.object(fetch_wod.time, "sleep", return_value=None),
            ):
                rc = fetch_wod.main(
                    [
                        "--since",
                        "2022-07-01",
                        "--until",
                        "2022-07-08",
                        "--out",
                        tmpdir,
                        "--delay",
                        "0",
                    ]
                )

            self.assertEqual(rc, 0)

    def test_exit_1_when_nothing_present_and_everything_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            error = urllib.error.HTTPError(
                url="http://example.com",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=None,
            )

            with (
                mock.patch.object(fetch_wod, "_real_fetch_fn", side_effect=error),
                mock.patch.object(fetch_wod.time, "sleep", return_value=None),
            ):
                rc = fetch_wod.main(
                    [
                        "--since",
                        "2022-07-01",
                        "--until",
                        "2022-07-03",
                        "--out",
                        tmpdir,
                        "--delay",
                        "0",
                    ]
                )

            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
