#!/usr/bin/env python3
"""Cross-check WOD email bodies against the web-derived records for the
same date.

WHY: the user's stated source of truth is the Concept2 "Workout of the
Day" email, but the training-data pipeline (build.py) parses the public
web archive (raw/*.html) instead. This script proves the two agree for a
sample of dates by parsing the email fixture with parse.parse_text and
the matching raw HTML page with parse.parse_html, then comparing title,
description, and groups (machines, pm34, pm5) after whitespace
normalisation.

Inputs
------
<fixtures>/*.txt
    Verbatim plain-text WOD email bodies, one file per date
    (YYYY-MM-DD.txt), fetched via the imap MCP tools.
<fixtures>/index.json
    {date: folder} sidecar recording which mailbox folder (INBOX or
    Trash) each fixture came from.
<raw>/YYYY-MM-DD.html
    The matching raw web page, if present locally (raw pages are
    gitignored, so this directory may be a subset of, or entirely
    absent from, a fresh clone).

Outputs
-------
Prints a table to stdout and writes the report at `--out` with columns
date, folder, match (yes/no), diff summary. Exits 1 if any date that has
both an email fixture and a raw HTML page shows a mismatch. Dates with no
matching raw page are reported as SKIPPED (not a failure).

Usage::

    pm5keys-data crosscheck [--fixtures tests/fixtures/email] [--raw raw]
        [--out data/reports/email_crosscheck.md]

`--fixtures`, `--raw`, and `--out` default to paths relative to the
current working directory -- this module never writes next to its own
file.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from . import parse as parse_wod

DEFAULT_FIXTURES = os.path.join("tests", "fixtures", "email")
DEFAULT_RAW = "raw"
DEFAULT_OUT = os.path.join("data", "reports", "email_crosscheck.md")


def _normalise_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def _normalise_group(group: dict) -> tuple:
    return (
        _normalise_whitespace(group.get("machines") or ""),
        _normalise_whitespace(group.get("pm34") or ""),
        _normalise_whitespace(group.get("pm5") or ""),
    )


def _normalise_groups(groups: list) -> list:
    return [_normalise_group(g) for g in groups]


def compare_records(email_record: dict, web_record: dict) -> list:
    """Compare `email_record` (from parse_text) against `web_record`
    (from parse_html) for the same date. Returns a list of human-
    readable diff strings; empty list means the records match.
    """
    diffs = []

    email_title = _normalise_whitespace(email_record.get("title") or "")
    web_title = _normalise_whitespace(web_record.get("title") or "")
    if email_title != web_title:
        diffs.append(f"title: email={email_title!r} web={web_title!r}")

    email_desc = _normalise_whitespace(email_record.get("description") or "")
    web_desc = _normalise_whitespace(web_record.get("description") or "")
    if email_desc != web_desc:
        diffs.append(f"description: email={email_desc!r} web={web_desc!r}")

    email_groups = _normalise_groups(email_record.get("groups") or [])
    web_groups = _normalise_groups(web_record.get("groups") or [])
    if email_groups != web_groups:
        diffs.append(f"groups: email={email_groups!r} web={web_groups!r}")

    return diffs


def _date_from_filename(path: str) -> str:
    base = os.path.basename(path)
    name, _ext = os.path.splitext(base)
    return name


def load_index(fixtures_dir: str) -> dict:
    index_path = os.path.join(fixtures_dir, "index.json")
    if not os.path.exists(index_path):
        return {}
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_crosscheck(fixtures_dir: str = DEFAULT_FIXTURES, raw_dir: str = DEFAULT_RAW) -> tuple:
    """Run the cross-check over every `<fixtures_dir>/*.txt` fixture.

    Returns (rows, any_mismatch) where rows is a list of dicts with keys
    {date, folder, status, diff} and status is one of "match",
    "mismatch", "skipped" (no matching raw page for that date).
    """
    index = load_index(fixtures_dir)
    email_files = sorted(glob.glob(os.path.join(fixtures_dir, "*.txt")))

    rows = []
    any_mismatch = False

    for email_path in email_files:
        date = _date_from_filename(email_path)
        folder = index.get(date, "?")

        with open(email_path, "r", encoding="utf-8") as f:
            email_text = f.read()
        email_record = parse_wod.parse_text(email_text, date, source="email")

        raw_path = os.path.join(raw_dir, f"{date}.html")
        if not os.path.exists(raw_path):
            rows.append(
                {
                    "date": date,
                    "folder": folder,
                    "status": "skipped",
                    "diff": "no raw/ HTML page available locally",
                }
            )
            continue

        with open(raw_path, "r", encoding="utf-8", errors="replace") as f:
            web_html = f.read()
        web_record = parse_wod.parse_html(web_html, date, source="web")

        diffs = compare_records(email_record, web_record)
        if diffs:
            any_mismatch = True
            rows.append(
                {
                    "date": date,
                    "folder": folder,
                    "status": "mismatch",
                    "diff": "; ".join(diffs),
                }
            )
        else:
            rows.append(
                {
                    "date": date,
                    "folder": folder,
                    "status": "match",
                    "diff": "",
                }
            )

    return rows, any_mismatch


def _print_table(rows: list) -> None:
    header = f"{'date':<12} {'folder':<8} {'match':<8} diff"
    print(header)
    print("-" * len(header))
    for row in rows:
        match_col = {"match": "yes", "mismatch": "no", "skipped": "skip"}[row["status"]]
        print(f"{row['date']:<12} {row['folder']:<8} {match_col:<8} {row['diff']}")


def _write_report(rows: list, out_path: str) -> None:
    lines = [
        "# Email vs. web cross-check",
        "",
        "Compares the Concept2 WOD email body against the matching web-derived",
        "record (`raw/YYYY-MM-DD.html`) for a sample of dates, verifying",
        "title, description, and groups (machines, pm34, pm5) agree after",
        "whitespace normalisation.",
        "",
        "| date | folder | match | diff |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        match_col = {"match": "yes", "mismatch": "no", "skipped": "skip"}[row["status"]]
        diff = row["diff"].replace("|", "\\|") or "-"
        lines.append(f"| {row['date']} | {row['folder']} | {match_col} | {diff} |")
    lines.append("")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-check WOD email fixtures against web-derived records"
    )
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        help=f"directory of email fixtures (default: {DEFAULT_FIXTURES})",
    )
    parser.add_argument(
        "--raw",
        default=DEFAULT_RAW,
        help=f"directory of raw *.html pages (default: {DEFAULT_RAW})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"path to write the report (default: {DEFAULT_OUT})",
    )
    return parser


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    rows, any_mismatch = run_crosscheck(args.fixtures, args.raw)
    _print_table(rows)
    _write_report(rows, args.out)

    matched = sum(1 for r in rows if r["status"] == "match")
    mismatched = sum(1 for r in rows if r["status"] == "mismatch")
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    print(f"\nmatched {matched}, mismatched {mismatched}, skipped {skipped}, total {len(rows)}")

    return 1 if any_mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
