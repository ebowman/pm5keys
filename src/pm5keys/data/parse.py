#!/usr/bin/env python3
"""Parser for Concept2 Workout-of-the-Day pages and emails.

Turns a raw WOD web page (raw/YYYY-MM-DD.html) or the plain-text body
of the WOD email (same underlying template, rendered differently) into a
single structured record::

    {
        "date": "YYYY-MM-DD",
        "title": str,
        "description": str,
        "groups": [
            {"machines": str, "pm34": str | None, "pm5": str | None},
            ...
        ],
        "honorboard_url": str | None,
        "source": "web" | "email",
        "warnings": [str, ...],   # only present if non-empty
    }

Two entry points:

    parse_text(text, date, source="email") -> dict
        Parses the plain-text WOD email body (or any text already in that
        layout).

    parse_html(html, date, source="web") -> dict
        Converts HTML to text (see html_to_text) and delegates to
        parse_text.

Email text layout
------------------
The email body is delimited by a short marker line of five asterisks
('*****') opening the "story" section and six asterisks ('******')
closing it::

    View in Browser: ...

    *****

    <title>

    <description paragraph(s)>

    ******

    Honorboard...

    <group label>
      PM3/PM4: <sequence>
    PM5: <sequence>
    <group label>
      PM3/PM4: <sequence>
    PM5: <sequence>

    http://www.concept2.com/indoor-rowers/training/wod

Title = first non-empty line after the '*****' marker. Description = the
following non-empty paragraph(s) (up to the '******' marker), joined with
a single space and whitespace-normalised. If no '*****' marker is present
in the text (e.g. a hand-typed sample, or a template variant), we fall
back to: title = first non-empty line of the text, description = the
next paragraph.

Group labels are any non-empty line immediately preceding a line that
starts a 'PM3/PM4:', 'PM5:', or the combined 'PM3/PM4/PM5:' key (which
Concept2 uses on days when PM3/PM4 and PM5 share one button-press
sequence -- in that case the single sequence is copied into both `pm34`
and `pm5`). A leading 'wod_email.button_press_title...' template-noise
prefix is stripped from the label line before use. If a PM line has no
usable preceding label (e.g. the very first line of the section is
itself a PM line), the group defaults to the label 'All Machines'.

HTML structure (web page)
--------------------------
The web page template does NOT contain '*****' markers anywhere -- those
are an artifact of the plain-text email rendering only. Inspecting the
three sample fixtures (tests/fixtures/web/*.html) shows a stable structure
instead:

  * The page has two <h1> headings in a "feature" cell: the date, and a
    literal "Workout of the Day" sub-heading.
  * The very next "feature" cell (an <h2 class="sub"> heading followed by
    a <p>) holds the title and description: <h2 class="sub">TITLE</h2>
    <p>DESCRIPTION</p>.
  * After converting to text with html_to_text (see below), this
    "feature" block's heading text becomes the first line and its
    paragraph text becomes the following paragraph, in exactly the shape
    parse_text's no-marker fallback expects -- *except* that the
    "February 1, 2026" / "Workout of the Day" heading pair earlier in the
    page would otherwise be picked up first. To avoid that, parse_html
    strips everything up through the literal line "Workout of the Day"
    (which is present, verbatim, on every fixture and every raw page
    inspected) before delegating to parse_text, so the title/description
    fallback lands on the correct block.
  * The button-press legend paragraph ("Download ErgData ... Starting
    from the Main Menu, "A" corresponds to the top gray button on the
    right, ...") and the ErgData paragraph appear, verbatim, as ordinary
    text between the description and the group/PM lines. They never
    contain a 'PM3/PM4' or 'PM5' line immediately below them, so they are
    never mistaken for a group label by the "line immediately preceding
    a PM line" rule -- but to be safe, html_to_text emits them on their
    own line and parse_text's label search only ever looks one line
    back, so this paragraph is inert with respect to group parsing.
  * Group headings in HTML look like "<strong>RowErg and SkiErg</strong>:"
    (or "<strong>All Machines</strong>:" for single-group days), each
    immediately followed by "<strong>PM3/PM4</strong>: SEQ" and/or
    "<strong>PM5</strong>: SEQ" (or a combined
    "<strong>PM3/PM4/PM5</strong>: SEQ" on some pages). html_to_text
    renders these as plain lines "RowErg and SkiErg:", "PM3/PM4: SEQ",
    "PM5: SEQ", which parse_text's PM-line regex already handles (a
    trailing ':' on the label line is stripped).
  * honorboard_url: the <a href="https://log.concept2.com/wod/...">
    inside the "> Today's Honorboard" button; parse_text's generic
    log.concept2.com/wod/ URL search finds this directly in the
    converted text, since html_to_text preserves href targets that
    appear as visible link text is NOT relied upon -- instead
    html_to_text emits the href URL itself as text for <a> tags so the
    URL survives tag-stripping (Concept2's button text is "> Today's
    Honorboard", which does not contain the URL).

Sequence validation
--------------------
Every pm34/pm5 string is validated with keyseq.validate. If validation
fails, the raw (invalid) string is still kept in the record, and a
human-readable warning is appended to the record's top-level 'warnings'
list rather than raising.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from html.parser import HTMLParser

from .. import keyseq

# ---------------------------------------------------------------------------
# HTML -> text
# ---------------------------------------------------------------------------

_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "tr",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
}

_SKIP_TAGS = {"script", "style"}


class _WodHTMLParser(HTMLParser):
    """Minimal HTML-to-text converter.

    Emits a newline at block-element boundaries (see _BLOCK_TAGS) and
    skips the contents of <script>/<style> entirely. Entities are
    unescaped automatically by HTMLParser (convert_charrefs=True,
    the default). For <a> tags, the href target is emitted as text
    immediately before the link's own text, so URLs that are only ever
    present as an href (not as visible text) survive tag-stripping.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._chunks.append("\n" + href + "\n")
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        # e.g. <br/>
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def html_to_text(html: str) -> str:
    """Convert `html` to plain text: strip tags, unescape entities, emit
    newlines at block-element boundaries, and drop <script>/<style>
    contents entirely.
    """
    parser = _WodHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.get_text()


# ---------------------------------------------------------------------------
# Text parsing
# ---------------------------------------------------------------------------

_OPEN_MARKER = "*****"
_CLOSE_MARKER = "******"

_PM_LINE_RE = re.compile(r"^(PM3/PM4/PM5|PM3/PM4|PM5)\s*:\s*(.+)$")
_HONORBOARD_URL_RE = re.compile(r"https?://\S*log\.concept2\.com/wod/\S*")
_BUTTON_NOISE_PREFIX_RE = re.compile(r"^wod_email\.button_press_title\S*")


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _strip_label_noise(label: str) -> str:
    """Strip a leading 'wod_email.button_press_title...' template-noise
    token from a label line, and trailing ':' if present.
    """
    label = label.strip()
    label = _BUTTON_NOISE_PREFIX_RE.sub("", label)
    label = label.strip()
    if label.endswith(":"):
        label = label[:-1].strip()
    return label


def _extract_groups(lines: list[str]) -> list[dict]:
    """Scan `lines` for PM3/PM4, PM5, and PM3/PM4/PM5 lines, grouping
    consecutive PM lines that share the same preceding non-PM label line
    into one group. A new group starts whenever a label line appears, or
    whenever a PM key repeats (pm34 or pm5 already set) without an
    intervening label -- which also starts a fresh group, defaulting its
    label to 'All Machines'.
    """
    groups: list[dict] = []
    current: dict | None = None
    pending_label: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        m = _PM_LINE_RE.match(line)
        if m:
            key, seq = m.group(1), m.group(2).strip()
            need_new_group = (
                current is None
                or pending_label is not None
                or (key in ("PM3/PM4", "PM3/PM4/PM5") and current.get("pm34") is not None)
                or (key in ("PM5", "PM3/PM4/PM5") and current.get("pm5") is not None)
            )
            if need_new_group:
                label = _strip_label_noise(pending_label) if pending_label else "All Machines"
                if not label:
                    label = "All Machines"
                current = {"machines": label, "pm34": None, "pm5": None}
                groups.append(current)
                pending_label = None

            if key == "PM3/PM4":
                current["pm34"] = seq
            elif key == "PM5":
                current["pm5"] = seq
            else:  # PM3/PM4/PM5
                current["pm34"] = seq
                current["pm5"] = seq
            continue

        # Non-PM, non-empty line: candidate label for the *next* PM line.
        pending_label = line

    return groups


def _normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def _first_pm_line_index(lines: list[str]) -> int | None:
    for i, raw_line in enumerate(lines):
        if _PM_LINE_RE.match(raw_line.strip()):
            return i
    return None


def _extract_title_description(lines: list[str]) -> tuple[str, str]:
    """Title = first non-empty line; description = the following
    paragraph (consecutive non-empty lines up to the next blank line or
    end of the given slice), whitespace-normalised.
    """
    idx = 0
    n = len(lines)

    while idx < n and not lines[idx].strip():
        idx += 1
    if idx >= n:
        return "", ""

    title = lines[idx].strip()
    idx += 1

    while idx < n and not lines[idx].strip():
        idx += 1

    desc_parts = []
    while idx < n and lines[idx].strip():
        desc_parts.append(lines[idx].strip())
        idx += 1

    description = _normalise_whitespace(" ".join(desc_parts))
    return title, description


def parse_text(text: str, date: str, source: str = "email") -> dict:
    """Parse the plain-text WOD email body (or html_to_text output) into
    a structured record. See module docstring for the text layout and
    the no-marker fallback behaviour.
    """
    lines = _split_lines(text)

    open_idx = None
    close_idx = None
    for i, line in enumerate(lines):
        if line.strip() == _OPEN_MARKER:
            open_idx = i
            break
    if open_idx is not None:
        for i in range(open_idx + 1, len(lines)):
            if lines[i].strip() == _CLOSE_MARKER:
                close_idx = i
                break

    if open_idx is not None:
        title_desc_lines = (
            lines[open_idx + 1 : close_idx] if close_idx is not None else lines[open_idx + 1 :]
        )
        title, description = _extract_title_description(title_desc_lines)
        group_search_lines = lines[close_idx + 1 :] if close_idx is not None else []
    else:
        title, description = _extract_title_description(lines)
        # Fallback: search for groups in whatever follows the description
        # paragraph (i.e. the rest of the document), since there's no
        # '******' close marker to anchor on.
        pm_idx = _first_pm_line_index(lines)
        group_search_lines = lines if pm_idx is not None else []

    groups = _extract_groups(group_search_lines)

    honorboard_match = _HONORBOARD_URL_RE.search(text)
    honorboard_url = honorboard_match.group(0) if honorboard_match else None

    warnings: list[str] = []
    for group in groups:
        for key in ("pm34", "pm5"):
            seq = group[key]
            if seq is None:
                continue
            try:
                keyseq.validate(seq)
            except ValueError as exc:
                warnings.append(
                    f"{date}: invalid {key} sequence for group {group['machines']!r}: {exc}"
                )

    record = {
        "date": date,
        "title": title,
        "description": description,
        "groups": groups,
        "honorboard_url": honorboard_url,
        "source": source,
    }
    if warnings:
        record["warnings"] = warnings
    return record


def parse_html(html: str, date: str, source: str = "web") -> dict:
    """Convert `html` to text (see html_to_text) and delegate to
    parse_text. See module docstring ("HTML structure (web page)") for
    how the title/description block is located in the absence of
    '*****' markers.
    """
    text = html_to_text(html)

    # Locate the literal "Workout of the Day" sub-heading (<h1 class="sub">)
    # as a standalone line -- not the "Concept2 Workout of the Day" title-
    # bar text, nor the <title> tag, nor the mobile footer image alt text,
    # all of which also contain this substring. Once found, everything up
    # to and including that line is dropped so the fallback title/
    # description extraction in parse_text lands on the next "feature"
    # block (the real title/description), not on the date-heading pair
    # above it.
    lines = text.split("\n")
    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "Workout of the Day":
            heading_idx = i
            break
    if heading_idx is not None:
        text = "\n".join(lines[heading_idx + 1 :])

    return parse_text(text, date, source=source)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _date_from_filename(path: str) -> str:
    base = os.path.basename(path)
    name, _ext = os.path.splitext(base)
    return name


def _iter_html_files(target: str) -> list[str]:
    if os.path.isdir(target):
        return sorted(glob.glob(os.path.join(target, "*.html")))
    return [target]


def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Parse Concept2 WOD web pages into structured records"
    )
    parser.add_argument("target", help="a directory of *.html files, or a single .html file")
    parser.add_argument(
        "--json", metavar="OUT.jsonl", help="write one JSON record per line to this file"
    )
    parser.add_argument("--show", metavar="DATE", help="print the single record for DATE as JSON")
    args = parser.parse_args(argv)

    files = _iter_html_files(args.target)

    records = []
    failed = []
    warnings_count = 0

    for path in files:
        date = _date_from_filename(path)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                html = f.read()
            record = parse_html(html, date)
        except Exception as exc:  # noqa: BLE001 - CLI-level catch-all by design
            failed.append((os.path.basename(path), str(exc)))
            continue
        records.append(record)
        if record.get("warnings"):
            warnings_count += 1

    with_groups = [r for r in records if r["groups"]]
    no_groups = [r for r in records if not r["groups"]]

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    if args.show:
        match = next((r for r in records if r["date"] == args.show), None)
        if match is None:
            print(f"no record for date {args.show}", file=sys.stderr)
        else:
            print(json.dumps(match, indent=2))

    print(f"parsed {len(records)}, with_groups {len(with_groups)}, no_groups {len(no_groups)}")
    if no_groups:
        shown = [r["date"] for r in no_groups[:20]]
        print(f"  no_groups dates (up to 20): {', '.join(shown)}")
    print(f"warnings {warnings_count}")
    print(f"failed {len(failed)}")
    for filename, msg in failed:
        print(f"  FAILED {filename}: {msg}")

    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    return _run_cli(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
