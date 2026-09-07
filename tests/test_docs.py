# Run from repo root: python3 -m unittest discover -s tests -t .

"""Extracts every '| <text> | <sequence> |' Examples-table row from
docs/notation.md and docs/pm5-model.md and asserts
compile(parse_spec(text)) == sequence for each -- giving the docs'
worked examples teeth (a doc change that breaks an example fails this
test, not just a human reviewer).

Convention: only markdown table rows whose header row is exactly
'| Text | PM5 |' are treated as examples; other tables (menu tree,
field layouts, evidence table, etc.) use different headers and are
correctly ignored.
"""

from __future__ import annotations

import os
import re
import unittest

from pm5keys import compile_keys as ck
from pm5keys.spec import parse_spec

_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
_EXAMPLE_DOCS = ["notation.md", "pm5-model.md"]

_HEADER_RE = re.compile(r"^\|\s*Text\s*\|\s*PM5\s*\|\s*$")
_SEPARATOR_RE = re.compile(r"^\|\s*-+\s*\|\s*-+\s*\|\s*$")
_ROW_RE = re.compile(r"^\|(.+)\|(.+)\|$")


def _extract_examples(path: str) -> list:
    """Return a list of (text, sequence, doc_path, line_no) tuples for
    every row of every '| Text | PM5 |' table in the file at path."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    examples = []
    in_table = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if _HEADER_RE.match(stripped):
            in_table = True
            continue
        if in_table and _SEPARATOR_RE.match(stripped):
            continue
        if in_table:
            m = _ROW_RE.match(stripped)
            if m:
                text = m.group(1).strip()
                seq = m.group(2).strip()
                # Strip surrounding backticks, if any, from the sequence cell.
                seq = seq.strip("`")
                examples.append((text, seq, path, i + 1))
                continue
            # A non-matching, non-blank line ends the table.
            in_table = False
    return examples


def _all_examples() -> list:
    examples = []
    for name in _EXAMPLE_DOCS:
        path = os.path.abspath(os.path.join(_DOCS_DIR, name))
        examples.extend(_extract_examples(path))
    return examples


class DocExamplesCompileTest(unittest.TestCase):
    def test_docs_have_examples(self):
        examples = _all_examples()
        self.assertGreaterEqual(
            len(examples), 3, "expected at least 3 worked examples across the docs"
        )

    def test_every_example_compiles_to_its_quoted_sequence(self):
        examples = _all_examples()
        self.assertTrue(examples, "no examples extracted from docs -- check the table convention")
        for text, expected_seq, path, line_no in examples:
            with self.subTest(text=text, doc=os.path.basename(path), line=line_no):
                spec = parse_spec(text, None)
                self.assertIsNotNone(
                    spec,
                    f"{os.path.basename(path)}:{line_no}: parse_spec could not parse {text!r}",
                )
                spec = dict(spec)
                got = ck.compile(spec)
                self.assertEqual(
                    got,
                    expected_seq,
                    f"{os.path.basename(path)}:{line_no}: {text!r} compiled to {got!r}, "
                    f"doc claims {expected_seq!r}",
                )


if __name__ == "__main__":
    unittest.main()
