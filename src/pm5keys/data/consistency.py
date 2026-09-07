#!/usr/bin/env python3
"""Consistency checks for the Concept2 WOD -> PM5 dataset.

Reads data/dataset.jsonl and writes data/reports/conflicts.md with three
sections:

    1. Label conflicts
       Rows are grouped by key = (norm(description), machines). A conflict
       is any key with more than one distinct pm5 sequence. For each
       conflict, the description, machines, and every pm5 variant are
       listed with its count, date range, and up to 6 sample dates.

       1b. Same sub-section, but keyed by (norm(title), machines) instead
       of description, since a title is the short form a user is likely to
       type. Titles are the common short label across variants that differ
       only in description text, so 1b conflicts are a superset lens on
       the same rows and typically include cases where 1 finds nothing
       (identical title, different description, different pm5).

    2. Same sequence, different descriptions (informational)
       Rows are grouped by key = (machines, pm5). Any key with more than
       one distinct norm(description) is listed with each description's
       count. This is informational, not necessarily an error -- it is
       common for the same key sequence to be described in more than one
       way across newsletters.

    3. Sanity tables
       Distribution of the first token of pm5, distribution of the
       pm5_expanded sequence length (min/median/max plus a histogram in
       buckets of 5), and a count of rows per machines label.

norm = casefold + collapse whitespace + strip, matching build_dataset._norm.

Four pure functions do the real work so they can be unit-tested without
touching the filesystem:

    find_label_conflicts(rows) -> list
    find_description_variants(rows) -> list
    sequence_stats(rows) -> dict
    render_markdown(dataset_path, row_count, label_conflicts,
                     title_conflicts, description_variants, stats) -> str

Usage::

    pm5keys-data check [--dataset data/dataset.jsonl] [--out data/reports/conflicts.md]

`--dataset` and `--out` default to paths relative to the current working
directory -- this module never writes next to its own file.

Exit code is always 0 -- this is a reporting tool, not a gate.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys


def _norm(text: str) -> str:
    """casefold + collapse whitespace + strip, for conflict keying."""
    return " ".join((text or "").split()).casefold().strip()


def _date_range(dates: list[str]) -> str:
    dates_sorted = sorted(dates)
    if not dates_sorted:
        return ""
    first, last = dates_sorted[0], dates_sorted[-1]
    if first == last:
        return first
    return f"{first}..{last}"


def _sample_dates(dates: list[str], limit: int = 6) -> list[str]:
    return sorted(dates)[:limit]


def _find_conflicts_by(rows: list[dict], text_field: str) -> list[dict]:
    """Group rows by (norm(rows[text_field]), machines) and return every
    group with more than one distinct pm5. Each result dict has:
      {text_field: <original text of first-seen row>, "machines": ...,
       "variants": [{"pm5": ..., "count": ..., "dates": [...],
                      "date_range": ...}, ...]}
    Variants are sorted by count desc, then by pm5 ascending.
    """
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []

    for row in rows:
        text = row.get(text_field) or ""
        machines = row.get("machines")
        key = (_norm(text), machines)

        if key not in groups:
            groups[key] = {
                "text": text,
                "machines": machines,
                "pm5_dates": {},  # pm5 -> list[date]
            }
            order.append(key)

        entry = groups[key]
        pm5 = row.get("pm5")
        entry["pm5_dates"].setdefault(pm5, []).append(row.get("date"))

    conflicts = []
    for key in order:
        entry = groups[key]
        pm5_dates = entry["pm5_dates"]
        if len(pm5_dates) <= 1:
            continue
        variants = []
        for pm5, dates in pm5_dates.items():
            variants.append(
                {
                    "pm5": pm5,
                    "count": len(dates),
                    "dates": _sample_dates(dates),
                    "date_range": _date_range(dates),
                }
            )
        variants.sort(key=lambda v: (-v["count"], v["pm5"] or ""))
        conflicts.append(
            {
                text_field: entry["text"],
                "machines": entry["machines"],
                "variants": variants,
            }
        )

    conflicts.sort(key=lambda c: (c["machines"] or "", c[text_field] or ""))
    return conflicts


def find_label_conflicts(rows: list[dict]) -> list:
    """Section 1: group by (norm(description), machines); return every
    group with more than one distinct pm5.
    """
    return _find_conflicts_by(rows, "description")


def find_title_conflicts(rows: list[dict]) -> list:
    """Section 1b: group by (norm(title), machines); return every group
    with more than one distinct pm5.
    """
    return _find_conflicts_by(rows, "title")


def find_description_variants(rows: list[dict]) -> list:
    """Section 2 (informational): group by (machines, pm5); return every
    group with more than one distinct norm(description). Each result:
      {"machines": ..., "pm5": ..., "descriptions": [{"description": ...,
       "count": ...}, ...]}
    Descriptions sorted by count desc, then description text ascending.
    """
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []

    for row in rows:
        machines = row.get("machines")
        pm5 = row.get("pm5")
        key = (machines, pm5)

        if key not in groups:
            groups[key] = {"machines": machines, "pm5": pm5, "desc_counts": {}}
            order.append(key)

        entry = groups[key]
        description = row.get("description") or ""
        norm_desc = _norm(description)
        bucket = entry["desc_counts"].setdefault(
            norm_desc, {"description": description, "count": 0}
        )
        bucket["count"] += 1

    variants = []
    for key in order:
        entry = groups[key]
        desc_counts = entry["desc_counts"]
        if len(desc_counts) <= 1:
            continue
        descriptions = sorted(desc_counts.values(), key=lambda d: (-d["count"], d["description"]))
        variants.append(
            {
                "machines": entry["machines"],
                "pm5": entry["pm5"],
                "descriptions": descriptions,
            }
        )

    variants.sort(key=lambda v: (v["machines"] or "", v["pm5"] or ""))
    return variants


def sequence_stats(rows: list[dict]) -> dict:
    """Section 3: sanity tables computed from pm5 / pm5_expanded / machines.

    Returns:
      {"first_token_counts": {token: count, ...} sorted desc by count,
       "length_min": int, "length_median": float, "length_max": int,
       "length_histogram": [(bucket_label, count), ...] in buckets of 5,
       "machines_counts": {machines: count, ...} sorted desc by count}
    """
    first_token_counts: dict[str, int] = {}
    lengths: list[int] = []
    machines_counts: dict[str, int] = {}

    for row in rows:
        pm5 = row.get("pm5") or ""
        first_token = pm5.split("-")[0] if pm5 else ""
        first_token_counts[first_token] = first_token_counts.get(first_token, 0) + 1

        expanded = row.get("pm5_expanded") or []
        lengths.append(len(expanded))

        machines = row.get("machines")
        machines_counts[machines] = machines_counts.get(machines, 0) + 1

    if lengths:
        length_min = min(lengths)
        length_max = max(lengths)
        length_median = statistics.median(lengths)
    else:
        length_min = 0
        length_max = 0
        length_median = 0

    histogram: dict[str, int] = {}
    for length in lengths:
        bucket_start = (length // 5) * 5
        bucket_end = bucket_start + 4
        label = f"{bucket_start}-{bucket_end}"
        histogram[label] = histogram.get(label, 0) + 1

    def _bucket_sort_key(item):
        label = item[0]
        start = int(label.split("-")[0])
        return start

    histogram_sorted = sorted(histogram.items(), key=_bucket_sort_key)

    first_token_sorted = dict(sorted(first_token_counts.items(), key=lambda kv: (-kv[1], kv[0])))
    machines_sorted = dict(sorted(machines_counts.items(), key=lambda kv: (-kv[1], kv[0] or "")))

    return {
        "first_token_counts": first_token_sorted,
        "length_min": length_min,
        "length_median": length_median,
        "length_max": length_max,
        "length_histogram": histogram_sorted,
        "machines_counts": machines_sorted,
    }


def _render_conflict_section(conflicts: list, text_field: str, heading: str) -> list[str]:
    lines = [f"## {heading}", ""]
    if not conflicts:
        lines.append("No conflicts found.")
        lines.append("")
        return lines

    for i, conflict in enumerate(conflicts, start=1):
        label = text_field.capitalize()
        lines.append(f"### {i}. {label}: {conflict[text_field]!r}")
        lines.append("")
        lines.append(f"- Machines: `{conflict['machines']}`")
        lines.append(f"- Distinct pm5 variants: {len(conflict['variants'])}")
        lines.append("")
        for variant in conflict["variants"]:
            lines.append(f"  - `{variant['pm5']}`")
            lines.append(f"    - count: {variant['count']}")
            lines.append(f"    - date range: {variant['date_range']}")
            lines.append(f"    - sample dates: {', '.join(variant['dates'])}")
        lines.append("")
    return lines


def render_markdown(
    dataset_path: str,
    row_count: int,
    label_conflicts: list,
    title_conflicts: list,
    description_variants: list,
    stats: dict,
) -> str:
    """Render the full conflicts.md document."""
    lines: list[str] = []
    lines.append("# Dataset consistency report")
    lines.append("")
    lines.append(
        f"This file is generated, not hand-edited. Dataset: `{dataset_path}` ({row_count} rows)."
    )
    lines.append("")
    lines.append(
        "Regenerate with: `pm5keys-data check "
        f"--dataset {dataset_path} --out data/reports/conflicts.md`"
    )
    lines.append("")

    lines.extend(
        _render_conflict_section(
            label_conflicts,
            "description",
            "1. Label conflicts (same description + machines, different pm5)",
        )
    )
    lines.extend(
        _render_conflict_section(
            title_conflicts,
            "title",
            "1b. Title conflicts (same title + machines, different pm5)",
        )
    )

    lines.append("## 2. Same sequence, different descriptions (informational)")
    lines.append("")
    if not description_variants:
        lines.append("No variants found.")
        lines.append("")
    else:
        for i, variant in enumerate(description_variants, start=1):
            lines.append(f"### {i}. Machines: `{variant['machines']}`, pm5: `{variant['pm5']}`")
            lines.append("")
            lines.append(f"- Distinct descriptions: {len(variant['descriptions'])}")
            lines.append("")
            for desc in variant["descriptions"]:
                lines.append(f"  - ({desc['count']}x) {desc['description']!r}")
            lines.append("")

    lines.append("## 3. Sanity tables")
    lines.append("")
    lines.append("### First token of pm5")
    lines.append("")
    lines.append("| token | count |")
    lines.append("| --- | --- |")
    for token, count in stats["first_token_counts"].items():
        lines.append(f"| `{token}` | {count} |")
    lines.append("")

    lines.append("### pm5_expanded sequence length")
    lines.append("")
    lines.append(
        f"min: {stats['length_min']}, median: {stats['length_median']}, max: {stats['length_max']}"
    )
    lines.append("")
    lines.append("| bucket | count |")
    lines.append("| --- | --- |")
    for label, count in stats["length_histogram"]:
        lines.append(f"| {label} | {count} |")
    lines.append("")

    lines.append("### Rows per machines label")
    lines.append("")
    lines.append("| machines | count |")
    lines.append("| --- | --- |")
    for machines, count in stats["machines_counts"].items():
        lines.append(f"| `{machines}` | {count} |")
    lines.append("")

    return "\n".join(lines) + "\n"


def _load_rows(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Check the WOD dataset for label/sequence conflicts"
    )
    parser.add_argument(
        "--dataset",
        default="data/dataset.jsonl",
        help="path to dataset.jsonl (default: data/dataset.jsonl)",
    )
    parser.add_argument(
        "--out",
        default="data/reports/conflicts.md",
        help="path to write the report (default: data/reports/conflicts.md)",
    )
    args = parser.parse_args(argv)

    rows = _load_rows(args.dataset)

    label_conflicts = find_label_conflicts(rows)
    title_conflicts = find_title_conflicts(rows)
    description_variants = find_description_variants(rows)
    stats = sequence_stats(rows)

    markdown = render_markdown(
        args.dataset,
        len(rows),
        label_conflicts,
        title_conflicts,
        description_variants,
        stats,
    )

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"rows read: {len(rows)}")
    print(f"section 1 (label) conflicts: {len(label_conflicts)}")
    print(f"section 1b (title) conflicts: {len(title_conflicts)}")
    print(f"section 2 description variants: {len(description_variants)}")
    print(f"wrote {args.out}")

    return 0


def main(argv: list[str] | None = None) -> int:
    return _run_cli(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
