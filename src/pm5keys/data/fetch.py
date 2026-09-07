#!/usr/bin/env python3
"""Downloader for the public Concept2 Workout-of-the-Day archive.

Fetches https://utilities.concept2.com/wod-email/newsletter/YYYY-MM-DD/en/us
for each date in a range and writes the HTML body to <out>/YYYY-MM-DD.html.
No auth required; python3 stdlib only.

Run: pm5keys-data fetch [options] (or: python -m pm5keys.data fetch [options])

`--out` defaults to `raw/` relative to the current working directory --
this module never writes next to its own file.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

DEFAULT_OUT = "raw"
DEFAULT_SINCE = "2022-07-01"
DEFAULT_DELAY = 0.5
DEFAULT_TIMEOUT = 30
USER_AGENT = "wod-fetch/1.0 (+personal research)"
URL_TEMPLATE = "https://utilities.concept2.com/wod-email/newsletter/{date}/en/us"

RETRY_BACKOFFS = (1, 2, 4)


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------


def iter_dates(since: str, until: str) -> list[str]:
    """Return the list of YYYY-MM-DD date strings from `since` to `until`
    inclusive. Returns an empty list if since > until.
    """
    since_d = date.fromisoformat(since)
    until_d = date.fromisoformat(until)

    if since_d > until_d:
        return []

    dates = []
    current = since_d
    while current <= until_d:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def fetch_one(url: str, opener) -> tuple[int, bytes]:
    """Perform a single GET of `url` using `opener` (an object exposing
    urlopen(request, timeout=...), e.g. the urllib.request module itself,
    or a custom opener/mock with the same signature). Returns
    (status_code, body_bytes) on success (HTTP 200 only reaches the caller
    as "success" — any HTTPError propagates as an exception here so callers
    can distinguish HTTP-level failures from network failures). Raises
    urllib.error.HTTPError on non-2xx responses, and urllib.error.URLError
    (or socket/timeout errors) on network failures.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        status = response.getcode()
        body = response.read()
        return status, body


# ---------------------------------------------------------------------------
# missing.txt handling
# ---------------------------------------------------------------------------


def load_missing(path: str) -> dict:
    """Load missing.txt into a dict of {date: reason_suffix}. Lines are of
    the form '<date> <reason...>'. Missing/empty file yields {}.
    """
    missing = {}
    if not os.path.exists(path):
        return missing
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2:
                missing[parts[0]] = parts[1]
            else:
                missing[parts[0]] = ""
    return missing


def write_missing(path: str, missing: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for d in sorted(missing.keys()):
            reason = missing[d]
            if reason:
                f.write(f"{d} {reason}\n")
            else:
                f.write(f"{d}\n")


# ---------------------------------------------------------------------------
# Main fetch loop
# ---------------------------------------------------------------------------


def _fetch_with_retries(url: str, fetch_fn, delay: float, sleep_fn):
    """Call fetch_fn(url) -> (status, bytes).

    On HTTPError with a 4xx status, sleep `delay` and return
    ("http_error", str(status_code)) immediately (no retry).

    On HTTPError with a 5xx status, or on URLError/other network error,
    retry up to 3 times with backoff 1s, 2s, 4s (via sleep_fn); each
    attempt (including the first) is followed by a `delay` sleep on success
    or on a terminal (4xx) HTTPError. If all retries are exhausted for a
    5xx, return ("http_error", str(status_code)) using the last seen
    status. If all retries are exhausted for a network error, return
    ("net_error", short_reason). On success, return ("ok", body).
    """
    last_reason = ""
    last_5xx_status = None
    for attempt, backoff in enumerate((0,) + RETRY_BACKOFFS):
        if backoff:
            sleep_fn(backoff)
        try:
            _status, body = fetch_fn(url)
            sleep_fn(delay)
            return "ok", body
        except urllib.error.HTTPError as exc:
            if 500 <= exc.code < 600:
                last_5xx_status = str(exc.code)
                continue
            sleep_fn(delay)
            return "http_error", str(exc.code)
        except urllib.error.URLError as exc:
            last_reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            continue

    if last_5xx_status is not None:
        sleep_fn(delay)
        return "http_error", last_5xx_status

    return "net_error", last_reason[:120]


def run_fetch(
    dates: list[str],
    out_dir: str,
    force: bool,
    delay: float,
    limit: int | None,
    fetch_fn,
    sleep_fn=None,
) -> dict:
    """Core loop, network-free except via `fetch_fn(url) -> (status, bytes)`
    which may raise urllib.error.HTTPError or urllib.error.URLError (or any
    OSError-derived network error).

    Returns a dict with keys: fetched, present, missing_count, attempted.

    For each date:
      - if <out>/<date>.html exists and not force: count as present, skip
        (no network call, no sleep), and remove any stale missing.txt entry
        for that date.
      - else: attempt fetch via _fetch_with_retries.
          - on success: write bytes to <out>/<date>.html, count as fetched,
            remove any missing.txt entry for that date.
          - on HTTPError: record '<date> <status>' in missing dict, continue
            (no retry).
          - on URLError/other network error: retry up to 3 times with
            backoff 1s, 2s, 4s (via sleep_fn, so tests can no-op it); if all
            retries fail, record '<date> ERR <short reason>' in missing
            dict.
        Sleep `delay` (via sleep_fn) between network requests -- i.e. after
        every attempted network call (each try, including retries).

    `limit`, if not None, stops the loop after `limit` attempted fetches
    (dates that were NOT simply "present" skips).
    """
    if sleep_fn is None:  # resolved at call time so tests can patch time.sleep
        sleep_fn = time.sleep
    os.makedirs(out_dir, exist_ok=True)
    missing_path = os.path.join(out_dir, "missing.txt")
    missing = load_missing(missing_path)

    fetched = 0
    present = 0
    attempted = 0

    for d in dates:
        html_path = os.path.join(out_dir, f"{d}.html")

        if os.path.exists(html_path) and not force:
            present += 1
            if d in missing:
                del missing[d]
            continue

        if limit is not None and attempted >= limit:
            break

        attempted += 1
        url = URL_TEMPLATE.format(date=d)

        outcome, payload = _fetch_with_retries(url, fetch_fn, delay, sleep_fn)

        if outcome == "ok":
            with open(html_path, "wb") as f:
                f.write(payload)
            fetched += 1
            if d in missing:
                del missing[d]
        elif outcome == "http_error":
            missing[d] = payload
        else:  # net_error
            missing[d] = f"ERR {payload}"

    write_missing(missing_path, missing)

    return {
        "fetched": fetched,
        "present": present,
        "missing_count": len(missing),
        "attempted": attempted,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the Concept2 Workout-of-the-Day archive by date"
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=f"first date (YYYY-MM-DD), inclusive (default: {DEFAULT_SINCE})",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="last date (YYYY-MM-DD), inclusive (default: today)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="refetch even if the .html file already exists",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"seconds to sleep between network requests (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="stop after N attempted fetches (for testing)",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"output directory (default: {DEFAULT_OUT})",
    )
    return parser


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _real_fetch_fn(url: str) -> tuple[int, bytes]:
    return fetch_one(url, urllib.request)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    until = args.until or date.today().isoformat()

    dates = iter_dates(args.since, until)

    result = run_fetch(
        dates=dates,
        out_dir=args.out,
        force=args.force,
        delay=args.delay,
        limit=args.limit,
        fetch_fn=_real_fetch_fn,
    )

    summary_line = (
        f"fetched {result['fetched']}, present {result['present']}, "
        f"missing {result['missing_count']}"
    )
    print(summary_line)

    # Exit 0 if at least one page was fetched this run OR anything is
    # already present on disk (e.g. an idempotent rerun where everything
    # remaining in missing.txt is a permanent failure like an archive-start
    # floor). Exit 1 only on total failure: nothing fetched and nothing
    # present.
    if result["fetched"] == 0 and result["present"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
