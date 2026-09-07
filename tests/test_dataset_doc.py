# Run from repo root: python3 -m unittest discover -s tests -t .

"""Guards docs/dataset.md's "Counts" table against drift from the data.

Parses the fixed `| metric | value |` markdown table in
docs/dataset.md's "## Counts" section and asserts each value equals a
number freshly computed from data/*.jsonl at test time -- so a dataset
refresh that isn't followed by a docs/dataset.md update fails this
test instead of silently going stale. See CONTRIBUTING.md.
"""

from __future__ import annotations

import json
import os
import re
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")
_DOC_PATH = os.path.join(_REPO_ROOT, "docs", "dataset.md")

_COUNTS_ROW_RE = re.compile(r"^\|\s*(?P<metric>[^|]+?)\s*\|\s*(?P<value>[^|]+?)\s*\|$")
_SEPARATOR_RE = re.compile(r"^\|\s*-+\s*\|\s*-+\s*\|$")


def _load_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _parse_markdown_tables(path: str) -> list:
    """Return a list of tables, each a list of {metric: value} dicts, for
    every `| metric | value |`-shaped two-column table in `path`. A table
    starts at any header row of the exact form '| <text> | <text> |'
    followed immediately by a '|---|---|'-shaped separator row, and ends
    at the first line that doesn't match the '| a | b |' row shape.
    """
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    tables = []
    i = 0
    while i < len(lines):
        header = lines[i].rstrip("\n")
        header_match = _COUNTS_ROW_RE.match(header)
        if header_match and i + 1 < len(lines) and _SEPARATOR_RE.match(lines[i + 1].rstrip("\n")):
            rows = {}
            j = i + 2
            while j < len(lines):
                row_line = lines[j].rstrip("\n")
                row_match = _COUNTS_ROW_RE.match(row_line)
                if not row_match:
                    break
                rows[row_match.group("metric")] = row_match.group("value")
                j += 1
            tables.append(rows)
            i = j
        else:
            i += 1
    return tables


def _find_counts_table(tables: list) -> dict:
    """Return the first parsed table whose keys are exactly the metric
    names this test checks (i.e. the "## Counts" summary table, not the
    per-machines breakdown table or any other two-column table in the
    doc)."""
    expected_metrics = {
        "dataset rows",
        "dataset_unique rows",
        "dataset_rejects rows",
        "train rows",
        "eval rows",
        "pages fetched (distinct source_url)",
        "first date",
        "last date",
        "distinct machines labels",
        "distinct titles",
        "pm34-null rows",
    }
    for table in tables:
        if expected_metrics.issubset(table.keys()):
            return table
    raise AssertionError(
        "Could not find the '## Counts' metrics table in docs/dataset.md "
        "(expected a '| metric | value |' table containing all of: "
        + ", ".join(sorted(expected_metrics))
    )


class DatasetDocCountsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = _load_jsonl(os.path.join(_DATA_DIR, "dataset.jsonl"))
        cls.unique = _load_jsonl(os.path.join(_DATA_DIR, "dataset_unique.jsonl"))
        cls.rejects = _load_jsonl(os.path.join(_DATA_DIR, "dataset_rejects.jsonl"))
        cls.train = _load_jsonl(os.path.join(_DATA_DIR, "train.jsonl"))
        cls.eval_ = _load_jsonl(os.path.join(_DATA_DIR, "eval.jsonl"))

        tables = _parse_markdown_tables(_DOC_PATH)
        cls.counts_table = _find_counts_table(tables)

    def _table_value(self, metric: str) -> str:
        self.assertIn(
            metric,
            self.counts_table,
            f"docs/dataset.md Counts table is missing the '{metric}' row",
        )
        return self.counts_table[metric]

    def test_dataset_rows(self):
        self.assertEqual(self._table_value("dataset rows"), str(len(self.dataset)))

    def test_dataset_unique_rows(self):
        self.assertEqual(self._table_value("dataset_unique rows"), str(len(self.unique)))

    def test_dataset_rejects_rows(self):
        self.assertEqual(self._table_value("dataset_rejects rows"), str(len(self.rejects)))

    def test_train_rows(self):
        self.assertEqual(self._table_value("train rows"), str(len(self.train)))

    def test_eval_rows(self):
        self.assertEqual(self._table_value("eval rows"), str(len(self.eval_)))

    def test_pages_fetched(self):
        pages = {row["source_url"] for row in self.dataset}
        self.assertEqual(self._table_value("pages fetched (distinct source_url)"), str(len(pages)))

    def test_first_and_last_date(self):
        dates = [row["date"] for row in self.dataset]
        self.assertEqual(self._table_value("first date"), min(dates))
        self.assertEqual(self._table_value("last date"), max(dates))

    def test_distinct_machines_labels(self):
        machines = {row["machines"] for row in self.dataset}
        self.assertEqual(self._table_value("distinct machines labels"), str(len(machines)))

    def test_distinct_titles(self):
        titles = {row["title"] for row in self.dataset}
        self.assertEqual(self._table_value("distinct titles"), str(len(titles)))

    def test_pm34_null_rows(self):
        pm34_null = sum(1 for row in self.dataset if row.get("pm34") is None)
        self.assertEqual(self._table_value("pm34-null rows"), str(pm34_null))

    def test_machines_breakdown_table(self):
        """The per-machines breakdown table (machines -> row count) must
        also match the data, and its row counts must sum to the total
        dataset row count."""
        tables = _parse_markdown_tables(_DOC_PATH)
        breakdown = None
        for table in tables:
            if table is self.counts_table:
                continue
            if set(table.keys()) == {row["machines"] for row in self.dataset}:
                breakdown = table
                break
        self.assertIsNotNone(
            breakdown,
            "Could not find the per-machines breakdown table in docs/dataset.md",
        )

        from collections import Counter

        actual = Counter(row["machines"] for row in self.dataset)
        for label, count in actual.items():
            self.assertEqual(
                breakdown[label],
                str(count),
                f"docs/dataset.md machines breakdown for '{label}' is stale",
            )
        self.assertEqual(sum(int(v) for v in breakdown.values()), len(self.dataset))


if __name__ == "__main__":
    unittest.main()
