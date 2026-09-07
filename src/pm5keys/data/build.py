#!/usr/bin/env python3
"""Build the Concept2 WOD -> PM5 key-sequence training dataset.

Reads every raw WOD web page (wod/raw/*.html), parses each one with
parse_wod.parse_html (imported directly -- no shelling out), and flattens
the resulting records into one row per (page, machine group) that carries
a usable PM5 sequence. Writes three committed files:

    wod/dataset.jsonl
        One row per (date, machines group) with a valid pm5 sequence:
        {date, machines, title, description, pm5, pm5_expanded, pm34,
         source_url}.
        `pm5` is stored as `keyseq.canonical(pm5)` -- canonical form is
        identical to the raw notation for every row seen in the current
        corpus (this is verified by build_rows, which prints any row
        where they differ rather than silently normalising it away).
        `pm34` keeps the original group's pm34 string only if it passes
        keyseq.validate; free-text notes (e.g. "The PM3 and PM4 monitors
        do not support interval calorie workouts") are *not* sequences,
        so they are nulled out here rather than emitted as bogus
        sequences -- the row itself is still kept (pm5 is what matters).
        Rows are sorted by date, then by the group's original order
        within that page.

    wod/dataset_rejects.jsonl
        One row per (date, machines group) that was *not* emitted to
        dataset.jsonl, because its pm5 was missing or failed
        keyseq.validate. Includes the original group dict and a
        `reason` string. Expected to be empty for the current corpus
        (every group has a valid pm5), but the file is always written
        (even if empty) so the path exists and can be exercised by
        tests.

    wod/dataset_unique.jsonl
        Rows from dataset.jsonl deduplicated by key
        (norm(title), norm(description), machines, pm5), where
        norm = casefold + collapse-whitespace + strip. Fields:
        {title, description, machines, pm5, pm5_expanded, pm34, count,
         dates, first_date, last_date}. `pm34` is the first non-null
         pm34 seen for the key, or null if none was seen. `title` and
        `description` keep the first-seen row's original (non-normalised)
        text. `dates` is sorted ascending. Sorted by count desc, then by
        first_date.

Two pure functions do the real work so they can be unit-tested without
touching the filesystem or network:

    build_rows(records) -> (rows, rejects)
    dedupe(rows) -> unique_rows

Usage::

    pm5keys-data build [--raw raw] [--out data]

`--raw` and `--out` default to `raw/` and `data/` relative to the
current working directory -- this module never writes next to its own
file.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from .. import keyseq
from . import parse as parse_wod

SOURCE_URL_TEMPLATE = "https://utilities.concept2.com/wod-email/newsletter/{date}/en/us"


def _norm(text: str) -> str:
    """casefold + collapse whitespace + strip, for dedupe keying."""
    return " ".join(text.split()).casefold().strip()


def build_rows(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Flatten parsed WOD records into per-group rows.

    Returns (rows, rejects):
      * rows: one dict per (record, group) that has a pm5 sequence which
        passes keyseq.validate. Sorted by date, then by the group's
        original order within the record.
      * rejects: one dict per (record, group) whose pm5 is missing or
        fails keyseq.validate. Each has the original `group` dict plus a
        `reason` string. Also carries `date` and `title` for context.

    Any row whose keyseq.canonical(pm5) differs from the raw pm5 string
    is printed to stdout (prefixed "canonical differs:") so it's visible
    in the CLI stats rather than silently normalised away. The count of
    such rows is available via build_rows.canonical_diff_count after the
    call (module-level counter reset at the start of each call).
    """
    rows: list[dict] = []
    rejects: list[dict] = []
    canonical_diff_count = 0

    for record in records:
        date = record.get("date")
        title = record.get("title", "")
        description = record.get("description", "")
        groups = record.get("groups") or []

        for group in groups:
            machines = group.get("machines")
            pm5_raw = group.get("pm5")
            pm34_raw = group.get("pm34")

            if pm5_raw is None:
                rejects.append(
                    {
                        "date": date,
                        "title": title,
                        "group": group,
                        "reason": "missing pm5",
                    }
                )
                continue

            try:
                keyseq.validate(pm5_raw)
            except ValueError as exc:
                rejects.append(
                    {
                        "date": date,
                        "title": title,
                        "group": group,
                        "reason": f"invalid pm5: {exc}",
                    }
                )
                continue

            pm5_canonical = keyseq.canonical(pm5_raw)
            if pm5_canonical != pm5_raw:
                canonical_diff_count += 1
                print(f"canonical differs: {date} {machines!r}: raw={pm5_raw!r} canonical={pm5_canonical!r}")

            pm34 = pm34_raw
            if pm34 is not None:
                try:
                    keyseq.validate(pm34)
                except ValueError:
                    pm34 = None

            row = {
                "date": date,
                "machines": machines,
                "title": title,
                "description": description,
                "pm5": pm5_canonical,
                "pm5_expanded": keyseq.expand(pm5_canonical),
                "pm34": pm34,
                "source_url": SOURCE_URL_TEMPLATE.format(date=date),
            }
            rows.append(row)

    rows.sort(key=lambda r: (r["date"] or "", ))
    # Stable sort preserves original group order within a date since
    # `rows` was already built in (record, group) order and Python's
    # sort is stable -- re-sorting only by date keeps groups in their
    # original relative order for a given date.

    build_rows.canonical_diff_count = canonical_diff_count
    return rows, rejects


build_rows.canonical_diff_count = 0


def dedupe(rows: list[dict]) -> list[dict]:
    """Deduplicate `rows` by (norm(title), norm(description), machines,
    pm5). Returns one row per distinct key, sorted by count desc, then
    by first_date ascending.
    """
    buckets: dict[tuple, dict] = {}
    order: list[tuple] = []

    for row in rows:
        key = (
            _norm(row["title"]),
            _norm(row["description"]),
            row["machines"],
            row["pm5"],
        )
        date = row["date"]

        if key not in buckets:
            buckets[key] = {
                "title": row["title"],
                "description": row["description"],
                "machines": row["machines"],
                "pm5": row["pm5"],
                "pm5_expanded": row["pm5_expanded"],
                "pm34": row["pm34"],
                "count": 0,
                "dates": [],
            }
            order.append(key)

        entry = buckets[key]
        entry["count"] += 1
        entry["dates"].append(date)
        if entry["pm34"] is None and row["pm34"] is not None:
            entry["pm34"] = row["pm34"]

    unique_rows = []
    for key in order:
        entry = buckets[key]
        entry["dates"] = sorted(entry["dates"])
        entry["first_date"] = entry["dates"][0]
        entry["last_date"] = entry["dates"][-1]
        unique_rows.append(entry)

    unique_rows.sort(key=lambda r: (-r["count"], r["first_date"]))
    return unique_rows


def _iter_html_files(raw_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(raw_dir, "*.html")))


def _date_from_filename(path: str) -> str:
    base = os.path.basename(path)
    name, _ext = os.path.splitext(base)
    return name


def _parse_all(raw_dir: str) -> tuple[list[dict], list[tuple[str, str]]]:
    records = []
    failed = []
    for path in _iter_html_files(raw_dir):
        date = _date_from_filename(path)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            record = parse_wod.parse_html(html, date)
        except Exception as exc:  # noqa: BLE001 - CLI-level catch-all by design
            failed.append((os.path.basename(path), str(exc)))
            continue
        records.append(record)
    return records, failed


def _write_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Build the Concept2 WOD -> PM5 key-sequence dataset"
    )
    parser.add_argument("--raw", default="raw", help="directory of raw *.html pages (default: raw)")
    parser.add_argument("--out", default="data", help="output directory for the dataset files (default: data)")
    args = parser.parse_args(argv)

    records, failed = _parse_all(args.raw)
    if failed:
        for filename, msg in failed:
            print(f"  FAILED {filename}: {msg}", file=sys.stderr)

    groups_seen = sum(len(r.get("groups") or []) for r in records)

    rows, rejects = build_rows(records)
    unique_rows = dedupe(rows)

    os.makedirs(args.out, exist_ok=True)
    _write_jsonl(os.path.join(args.out, "dataset.jsonl"), rows)
    _write_jsonl(os.path.join(args.out, "dataset_rejects.jsonl"), rejects)
    _write_jsonl(os.path.join(args.out, "dataset_unique.jsonl"), unique_rows)

    machines_counts: dict[str, int] = {}
    for row in rows:
        machines_counts[row["machines"]] = machines_counts.get(row["machines"], 0) + 1

    distinct_titles = len({row["title"] for row in rows})
    pm34_nulled = sum(
        1
        for record in records
        for group in (record.get("groups") or [])
        if group.get("pm34") is not None
        and not _is_valid_seq(group.get("pm34"))
    )
    canonical_diff_count = build_rows.canonical_diff_count

    print(f"pages parsed: {len(records)}")
    print(f"groups seen: {groups_seen}")
    print(f"rows emitted: {len(rows)}")
    print(f"rows rejected: {len(rejects)}")
    print(f"unique workouts: {len(unique_rows)}")
    print(f"distinct titles: {distinct_titles}")
    print("distinct machines:")
    for machines, count in sorted(machines_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {machines}: {count}")
    print(f"pm34 nulled count: {pm34_nulled}")
    print(f"rows where canonical != raw: {canonical_diff_count}")

    return 0 if not failed else 1


def _is_valid_seq(seq: str) -> bool:
    try:
        keyseq.validate(seq)
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    return _run_cli(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
