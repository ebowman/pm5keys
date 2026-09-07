# Run from repo root: python -m unittest discover -s tests -t .

"""Guards against personal identifiers / PII leaking into the tree.

Walks the repository (excluding .git, .venv, raw, build, dist, and any
*.egg-info directory) and fails if any file contains, case-insensitively:
  - 'boboco'
  - '/Users/' (a local filesystem path)
  - an e-mail address ending in '.ie'
  - a Campaign Monitor tracking-link shape, e.g.
    'workoutoftheday.cmail19.com/t/...'

It also fails if any file under tests/fixtures contains 'cmail' (a
Campaign Monitor tracking-domain fragment), since fixtures should use
the redacted 'workoutoftheday.example' placeholder instead.

Actual private tokens (subscriber IDs, etc.) are intentionally NOT
hard-coded here, since naming them in this file would itself leak them
into the tree/history. Instead, a maintainer can list additional
forbidden substrings -- one per line, blank lines and '#'-comments
ignored -- in an optional, gitignored `.pii-patterns.local` file at the
repo root. If present, those substrings are checked case-insensitively
across the whole tree in addition to the built-in patterns above.

Offending matches are reported as file:line so they're easy to locate.
"""

import os
import re
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
LOCAL_PATTERNS_FILE = os.path.join(REPO_ROOT, ".pii-patterns.local")

EXCLUDED_DIRS = {".git", ".venv", "raw", "build", "dist"}


def _is_excluded_dir(name):
    return name in EXCLUDED_DIRS or name.endswith(".egg-info")


# Case-insensitive substrings that must never appear anywhere in the tree.
# Note: 'ebowman' is intentionally excluded -- it's the public GitHub
# handle and legitimately appears in pyproject.toml project URLs, etc.
FORBIDDEN_SUBSTRINGS = [
    "boboco",
    "/users/",
]

# Case-insensitive e-mail address ending in '.ie'.
EMAIL_IE_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.ie\b", re.IGNORECASE)

# Case-insensitive Campaign Monitor tracking-link shape, e.g.
# 'workoutoftheday.cmail19.com/t/...'. Matches the link shape rather
# than any specific subscriber token.
CMAIL_LINK_RE = re.compile(r"workoutoftheday\.cmail\d*\.com/t/", re.IGNORECASE)

# Fixture-only forbidden substring.
FIXTURES_FORBIDDEN_SUBSTRING = "cmail"


def _load_local_patterns():
    """Load extra forbidden substrings from .pii-patterns.local, if present.

    One substring per line; blank lines and lines starting with '#' are
    ignored. Matching is case-insensitive, same as the built-ins.
    """
    if not os.path.isfile(LOCAL_PATTERNS_FILE):
        return []

    patterns = []
    with open(LOCAL_PATTERNS_FILE, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            patterns.append(stripped)
    return patterns


def _iter_repo_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if not _is_excluded_dir(d)]
        for filename in filenames:
            yield os.path.join(dirpath, filename)


def _is_fixtures_file(path):
    rel = os.path.relpath(path, REPO_ROOT)
    parts = rel.split(os.sep)
    return "tests" in parts and "fixtures" in parts


def _read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="strict") as fh:
            return fh.readlines()
    except (UnicodeDecodeError, OSError):
        # Binary or unreadable file -- skip it, nothing textual to scan.
        return None


def _scan_file(path, extra_patterns):
    """Return a list of 'relpath:lineno: matched-text' offense strings."""
    lines = _read_lines(path)
    if lines is None:
        return []

    offenses = []
    rel = os.path.relpath(path, REPO_ROOT)
    is_fixture = _is_fixtures_file(path)

    for lineno, line in enumerate(lines, start=1):
        lowered = line.lower()

        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in lowered:
                offenses.append(f"{rel}:{lineno}: contains {needle!r}")

        for needle in extra_patterns:
            if needle.lower() in lowered:
                offenses.append(
                    f"{rel}:{lineno}: contains forbidden pattern from .pii-patterns.local"
                )

        email_match = EMAIL_IE_RE.search(line)
        if email_match:
            offenses.append(f"{rel}:{lineno}: contains .ie e-mail address {email_match.group(0)!r}")

        if CMAIL_LINK_RE.search(line):
            offenses.append(f"{rel}:{lineno}: contains a Campaign Monitor tracking link")

        if is_fixture and FIXTURES_FORBIDDEN_SUBSTRING in lowered:
            offenses.append(f"{rel}:{lineno}: fixture contains {FIXTURES_FORBIDDEN_SUBSTRING!r}")

    return offenses


class NoPiiTest(unittest.TestCase):
    def test_no_personal_identifiers_in_tree(self):
        extra_patterns = _load_local_patterns()

        all_offenses = []
        for path in _iter_repo_files():
            # Never scan ourselves: this file legitimately names the
            # forbidden substrings/patterns as string literals above.
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue
            # Never scan the local patterns file itself -- it holds the
            # private tokens we're checking *for*, not scrubbing.
            if os.path.abspath(path) == os.path.abspath(LOCAL_PATTERNS_FILE):
                continue
            all_offenses.extend(_scan_file(path, extra_patterns))

        self.assertEqual(
            all_offenses,
            [],
            "found personal identifier(s):\n" + "\n".join(all_offenses),
        )


if __name__ == "__main__":
    unittest.main()
