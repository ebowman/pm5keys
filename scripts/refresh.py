#!/usr/bin/env python3
"""Weekly dataset refresh: fetch new WOD pages, rebuild the dataset, and
verify the PM5/PM3 model still agrees with the data.

Run from the repo root (this script only ever writes/reads paths given
via its CLI flags, all of which default to the repo layout):

    python scripts/refresh.py [--dry-run] [--raw raw] [--out data]
        [--since YYYY-MM-DD]

Pipeline (via the installed console scripts, so this stays in sync with
whatever `pip install -e .` puts on PATH):

    pm5keys-data fetch --since <date> --out <raw>
    pm5keys-data build --raw <raw> --out <out>
    pm5keys-data check
    pm5keys-data split
    python -m pm5keys.spec --coverage <out>/dataset_unique.jsonl
    python -m pm5keys.compile_keys --verify <out>/spec_parsed.jsonl
    python -m pm5keys.compile_keys --verify <out>/spec_parsed.jsonl --monitor pm3

`--since` defaults to the day after the max `date` currently in
`<out>/dataset.jsonl` -- i.e. an incremental refresh. On a fresh
checkout with no prior dataset.jsonl this naturally falls back to
fetching the whole public archive from its start.

Exit codes:
    0  refresh completed; no model contradictions found
    1  a pipeline subcommand failed, OR the verify step found
       MODEL_ERROR > 0, OR GOLD_MISMATCH exceeded the committed
       baseline (data/reports/verify_baseline.json) for either monitor

The verify summary and rebuild counts are always printed to stdout as
markdown, and additionally appended to $GITHUB_STEP_SUMMARY when that
env var is set (GitHub Actions' job-summary mechanism). Pass
--summary-file PATH to also write just that markdown block (nothing
else) to PATH, e.g. for use as a PR body.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_BASELINE_PATH = os.path.join("data", "reports", "verify_baseline.json")

_CATEGORIES = ("EXACT", "EQUIVALENT", "GOLD_VARIABLE", "GOLD_MISMATCH", "MODEL_ERROR")

_CATEGORY_LINE_RE = re.compile(r"^\s*(" + "|".join(_CATEGORIES) + r"):\s*(\d+)\s*$")


# ---------------------------------------------------------------------------
# --since computation
# ---------------------------------------------------------------------------


def _read_jsonl(path: str) -> list[dict]:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def compute_since(dataset_path: str) -> str:
    """Return the day after the max `date` field in `dataset_path`, as a
    YYYY-MM-DD string. If the file is missing or empty, fall back to
    pm5keys.data.fetch's own DEFAULT_SINCE (the archive's start), so a
    fresh checkout with no prior dataset.jsonl fetches the whole archive.
    """
    rows = _read_jsonl(dataset_path)
    if not rows:
        fetch_mod = importlib.import_module("pm5keys.data.fetch")
        return fetch_mod.DEFAULT_SINCE

    max_date = max(row["date"] for row in rows)
    next_day = date.fromisoformat(max_date) + timedelta(days=1)
    return next_day.isoformat()


# ---------------------------------------------------------------------------
# Verify-summary parsing
# ---------------------------------------------------------------------------


def parse_verify_summary(output: str) -> dict[str, int]:
    """Parse the "Per-category counts:" block printed by
    `python -m pm5keys.compile_keys --verify ...` (stdout) into a dict of
    {category: count} using the lower-cased category name as the key
    (e.g. {"exact": 108, "equivalent": 4, "gold_variable": 3,
    "gold_mismatch": 1, "model_error": 0}). Missing categories default to
    0. Raises ValueError if no recognised category lines are found at
    all (a sign the command's output format has changed or the command
    failed silently).
    """
    counts: dict[str, int] = {}
    for line in output.splitlines():
        match = _CATEGORY_LINE_RE.match(line)
        if match:
            category, value = match.group(1), match.group(2)
            counts[category.lower()] = int(value)

    if not counts:
        raise ValueError(
            "could not find any per-category verify counts in compile_keys "
            "--verify output -- output format may have changed:\n" + output
        )

    for category in _CATEGORIES:
        counts.setdefault(category.lower(), 0)

    return counts


# ---------------------------------------------------------------------------
# Baseline comparison
# ---------------------------------------------------------------------------


def load_baseline(path: str) -> dict[str, dict[str, int]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_against_baseline(
    monitor: str, counts: dict[str, int], baseline: dict[str, dict[str, int]]
) -> list[str]:
    """Compare `counts` (as returned by parse_verify_summary) for `monitor`
    ("pm5" or "pm3") against `baseline` (as returned by load_baseline).

    Returns a list of human-readable failure-reason strings (empty list
    means "ok"):
      - "<MONITOR>: MODEL_ERROR = N > 0" if model_error count is nonzero.
      - "<MONITOR>: GOLD_MISMATCH = N exceeds baseline B" if
        gold_mismatch exceeds the baseline's recorded count for that
        monitor. A monitor missing from baseline is treated as a
        baseline of 0 (i.e. any GOLD_MISMATCH is new and fails loudly).
    """
    failures = []
    model_error = counts.get("model_error", 0)
    if model_error > 0:
        failures.append(f"{monitor}: MODEL_ERROR = {model_error} > 0")

    gold_mismatch = counts.get("gold_mismatch", 0)
    baseline_mismatch = baseline.get(monitor, {}).get("gold_mismatch", 0)
    if gold_mismatch > baseline_mismatch:
        failures.append(
            f"{monitor}: GOLD_MISMATCH = {gold_mismatch} exceeds baseline {baseline_mismatch}"
        )

    return failures


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], run_fn=None) -> subprocess.CompletedProcess:
    # `run_fn` is resolved at call time (not as a default-argument value)
    # so that `mock.patch("subprocess.run", ...)` -- which replaces the
    # `subprocess` module's `run` attribute -- is actually observed here,
    # rather than being bypassed by a reference captured at import time.
    if run_fn is None:
        run_fn = subprocess.run
    print(f"+ {' '.join(cmd)}")
    result = run_fn(cmd, cwd=_REPO_ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"command failed (exit {result.returncode}): {' '.join(cmd)}")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--raw", default="raw", help="raw HTML directory (default: raw)")
    parser.add_argument("--out", default="data", help="dataset output directory (default: data)")
    parser.add_argument(
        "--since",
        default=None,
        help="first date to fetch (default: day after max date in <out>/dataset.jsonl)",
    )
    parser.add_argument(
        "--baseline",
        default=_DEFAULT_BASELINE_PATH,
        help=f"verify-baseline JSON path (default: {_DEFAULT_BASELINE_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="print the plan (since date, commands) and exit without running anything",
    )
    parser.add_argument(
        "--summary-file",
        default=None,
        help=(
            "path to write only the '## Dataset refresh summary' markdown "
            "block to (overwritten each run); stdout still gets the full "
            "log plus this summary"
        ),
    )
    return parser


def _dataset_row_count(path: str) -> int:
    return len(_read_jsonl(path))


def _since_is_future(since: str) -> bool:
    """True if `since` is already past today -- i.e. the dataset is fully
    up to date and there is nothing new to fetch. `pm5keys-data fetch`
    treats an empty date range as total failure (exit 1: "nothing
    fetched and nothing present"), so refresh.py must skip invoking it
    in this case rather than treating the skip as a pipeline error.
    """
    return date.fromisoformat(since) > date.today()


def _plan_commands(since: str, raw: str, out: str) -> list[list[str]]:
    """Build the pipeline command list. Every subcommand that has a path
    flag is given an explicit path rooted at `out`/`raw` -- never a bare
    subcommand relying on that tool's own CWD-relative default -- so
    that `--raw`/`--out` pointing somewhere other than the repo's
    committed `raw/`/`data/` (e.g. a scratch directory for testing)
    never silently reads or writes the real repo's `data/` tree.
    """
    dataset_path = os.path.join(out, "dataset.jsonl")
    unique_path = os.path.join(out, "dataset_unique.jsonl")
    train_path = os.path.join(out, "train.jsonl")
    eval_path = os.path.join(out, "eval.jsonl")
    conflicts_path = os.path.join(out, "reports", "conflicts.md")
    spec_parsed_path = os.path.join(out, "spec_parsed.jsonl")
    spec_unparsed_path = os.path.join(out, "reports", "spec_unparsed.md")
    compile_report_path = os.path.join(out, "reports", "compile_report.md")
    compile_report_pm3_path = os.path.join(out, "reports", "compile_report_pm3.md")
    return [
        ["pm5keys-data", "fetch", "--since", since, "--out", raw],
        ["pm5keys-data", "build", "--raw", raw, "--out", out],
        ["pm5keys-data", "check", "--dataset", dataset_path, "--out", conflicts_path],
        [
            "pm5keys-data",
            "split",
            "--unique",
            unique_path,
            "--train",
            train_path,
            "--eval",
            eval_path,
        ],
        [
            sys.executable,
            "-m",
            "pm5keys.spec",
            "--coverage",
            unique_path,
            "--parsed",
            spec_parsed_path,
            "--unparsed",
            spec_unparsed_path,
        ],
        [
            sys.executable,
            "-m",
            "pm5keys.compile_keys",
            "--verify",
            spec_parsed_path,
            "--out",
            compile_report_path,
            "--dataset",
            dataset_path,
        ],
        [
            sys.executable,
            "-m",
            "pm5keys.compile_keys",
            "--verify",
            spec_parsed_path,
            "--out",
            compile_report_pm3_path,
            "--dataset",
            dataset_path,
            "--monitor",
            "pm3",
        ],
    ]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)

    dataset_path = os.path.join(args.out, "dataset.jsonl")
    unique_path = os.path.join(args.out, "dataset_unique.jsonl")

    since = args.since or compute_since(dataset_path)
    commands = _plan_commands(since, args.raw, args.out)

    if args.dry_run:
        print(f"since: {since}")
        print("plan:")
        for cmd in commands:
            print(f"  {' '.join(cmd)}")
        return 0

    rows_before = _dataset_row_count(dataset_path)
    unique_before = _dataset_row_count(unique_path)

    fetch_skipped = _since_is_future(since)

    try:
        if fetch_skipped:
            print(
                f"+ (skipped) pm5keys-data fetch --since {since} --out {args.raw}: "
                f"since is after today, dataset is already up to date; fetched 0 new pages"
            )
        else:
            _run(commands[0])  # fetch
        _run(commands[1])  # build
        _run(commands[2])  # check
        _run(commands[3])  # split
        _run(commands[4])  # spec --coverage
        pm5_result = _run(commands[5])  # compile_keys --verify (pm5)
        pm3_result = _run(commands[6])  # compile_keys --verify --monitor pm3
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    rows_after = _dataset_row_count(dataset_path)
    unique_after = _dataset_row_count(unique_path)

    try:
        pm5_counts = parse_verify_summary(pm5_result.stdout)
        pm3_counts = parse_verify_summary(pm3_result.stdout)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    baseline = load_baseline(os.path.join(_REPO_ROOT, args.baseline))

    failures = check_against_baseline("pm5", pm5_counts, baseline) + check_against_baseline(
        "pm3", pm3_counts, baseline
    )

    doc_test_ok = True
    doc_test_output = ""
    doc_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_dataset_doc"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if doc_proc.returncode != 0:
        doc_test_ok = False
        doc_test_output = (doc_proc.stdout or "") + (doc_proc.stderr or "")
        print(doc_test_output, file=sys.stderr)

    summary_lines = [
        "## Dataset refresh summary",
        "",
        f"- since: `{since}`",
        f"- dataset.jsonl rows: {rows_before} -> {rows_after}",
        f"- dataset_unique.jsonl rows: {unique_before} -> {unique_after}",
        "",
        "### Verify counts",
        "",
        "| monitor | EXACT | EQUIVALENT | GOLD_VARIABLE | GOLD_MISMATCH | MODEL_ERROR |",
        "|---|---|---|---|---|---|",
        (
            "| pm5 | "
            f"{pm5_counts['exact']} | {pm5_counts['equivalent']} | "
            f"{pm5_counts['gold_variable']} | {pm5_counts['gold_mismatch']} | "
            f"{pm5_counts['model_error']} |"
        ),
        (
            "| pm3 | "
            f"{pm3_counts['exact']} | {pm3_counts['equivalent']} | "
            f"{pm3_counts['gold_variable']} | {pm3_counts['gold_mismatch']} | "
            f"{pm3_counts['model_error']} |"
        ),
        "",
    ]

    if failures:
        summary_lines.append("### FAILED: model contradicts new data")
        summary_lines.append("")
        for reason in failures:
            summary_lines.append(f"- {reason}")
        summary_lines.append("")

    if not doc_test_ok:
        summary_lines.append(
            "### docs/dataset.md counts are stale -- "
            "`python -m unittest tests.test_dataset_doc` failed. "
            "Update docs/dataset.md's Counts table by hand (not auto-edited by this script)."
        )
        summary_lines.append("")

    summary = "\n".join(summary_lines)
    print(summary)

    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as f:
            f.write(summary)
            f.write("\n")

    if args.summary_file:
        with open(args.summary_file, "w", encoding="utf-8") as f:
            f.write(summary)
            f.write("\n")

    if failures:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
