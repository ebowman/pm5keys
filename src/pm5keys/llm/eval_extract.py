#!/usr/bin/env python3
"""Eval harness for pm5keys.llm.extract_spec: run the extraction
pipeline (text -> WorkoutSpec -> compile_keys.compile -> pm5_model.run)
over an eval.jsonl-shaped file and check the result against gold via
pm5_model.run + compile_keys.same_workout.

Scope: RowErg only. Rows with machines == 'BikeErg' are excluded.

Few-shot pool: built from the package-data dataset (dataset_unique.jsonl)
via pm5keys.llm.extract.load_pool, but with every row whose (title,
description) pair also appears in the eval file EXCLUDED first -- this
is the "explicit pool with eval identities excluded" the pm5keys.llm
package docstring requires callers to build themselves.

CLI:
    python -m pm5keys.llm.eval_extract data/eval.jsonl [--limit N]
        [--backend auto] [--model M] [--k 25] [--no-cache]
        [--out data/reports/extract_report.md]
        Runs the eval, prints accuracy (overall and per-kind) to
        stdout, and writes a markdown report to --out.
"""

from __future__ import annotations

import argparse
import json
import os

from .. import compile_keys as ck
from .. import pm5_model as pm5
from .. import spec as spec_mod
from .backends import ExtractError
from .extract import DEFAULT_DATASET_PATH, extract_spec, load_pool

_LLM_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_ROOT = os.path.dirname(os.path.dirname(_LLM_DIR))
_REPO_ROOT = os.path.dirname(_PACKAGE_ROOT)

DEFAULT_OUT_PATH = os.path.join(_REPO_ROOT, "data", "reports", "extract_report.md")


def _row_identity(row: dict) -> tuple:
    return (row.get("title", ""), row.get("description", ""))


def _load_rows(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_pool_excluding(eval_rows: list, dataset_path: str = DEFAULT_DATASET_PATH) -> list:
    """Return the few-shot pool built from dataset_path, with any row
    whose (title, description) identity matches a row in eval_rows
    removed first."""
    with open(dataset_path, encoding="utf-8") as f:
        dataset_rows = [json.loads(line) for line in f if line.strip()]

    eval_identities = {_row_identity(r) for r in eval_rows}
    filtered_rows = [r for r in dataset_rows if _row_identity(r) not in eval_identities]
    return load_pool(rows=filtered_rows)


def _is_gold_variable_match(extracted: dict, sim_gold: dict) -> bool:
    """True if sim_gold is an intervals_variable expansion of the
    extracted fixed-interval spec with identical legs (gold used the
    Variable screen for a fixed workout)."""
    kind = extracted.get("kind", "")
    if not kind.startswith("intervals_") or kind == "intervals_variable":
        return False
    if sim_gold.get("kind") != "intervals_variable":
        return False
    count = extracted.get("count")
    ivs = sim_gold.get("intervals", [])
    expected_work = extracted.get("work")
    expected_rest = extracted.get("rest_s")
    if count is None or len(ivs) != count:
        return False
    return all(iv.get("work") == expected_work and iv.get("rest_s") == expected_rest for iv in ivs)


def _eval_row(
    row: dict, backend: str, model: str | None, k: int, cache_dir: str | None, pool: list
) -> dict:
    title = row.get("title", "")
    description = row.get("description", "")
    text = f"{title}. {description}"

    result = {
        "title": title,
        "text": text,
        "correct": False,
        "note": "",
        "extracted": None,
        "compiled": None,
        "rule_agrees": None,
        "error": None,
    }

    parse_text = f"{title}\n{description}"
    rule_spec = spec_mod.parse_spec(parse_text, row.get("machines"))

    try:
        extracted = extract_spec(
            text, backend=backend, model=model, k=k, cache_dir=cache_dir, pool=pool
        )
    except ExtractError as exc:
        result["error"] = str(exc)
        result["note"] = "extract-error"
        return result

    result["extracted"] = extracted

    if rule_spec is not None:
        rule_spec_rower = dict(rule_spec)
        rule_spec_rower["machine"] = "rower"
        result["rule_agrees"] = ck.same_workout(rule_spec_rower, extracted)
    else:
        result["rule_agrees"] = None

    try:
        compiled = ck.compile(extracted)
    except (NotImplementedError, ValueError) as exc:
        result["error"] = str(exc)
        result["note"] = "compile-error"
        return result

    result["compiled"] = compiled

    try:
        sim_compiled = pm5.run(compiled)
        sim_gold = pm5.run(row["pm5"])
    except Exception as exc:  # noqa: BLE001 -- model error, count incorrect
        result["error"] = str(exc)
        result["note"] = "model-error"
        return result

    if ck.same_workout(sim_compiled, sim_gold):
        result["correct"] = True
        return result

    if _is_gold_variable_match(extracted, sim_gold):
        result["correct"] = True
        result["note"] = "gold-variable"
        return result

    result["note"] = "mismatch"
    return result


def run_eval(
    path: str,
    limit: int | None,
    backend: str,
    model: str | None,
    k: int,
    cache_dir: str | None,
) -> tuple:
    rows = _load_rows(path)
    rows = [r for r in rows if r.get("machines") != "BikeErg"]
    if limit is not None:
        rows = rows[:limit]

    pool = build_pool_excluding(rows)

    results = [_eval_row(row, backend, model, k, cache_dir, pool) for row in rows]
    return rows, results


def _write_report(rows, results, backend, model, k, per_kind, n, n_correct, out_path) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    lines = [
        "# pm5keys.llm.eval_extract report",
        "",
        "RowErg only (rows with machines == BikeErg excluded).",
        "",
        f"backend: {backend}, model: {model or '(default)'}, k: {k}, n rows: {n}",
        "",
        f"Overall accuracy: {n_correct}/{n}" + (f" ({n_correct / n:.1%})" if n else ""),
        "",
        "## Per-kind accuracy",
        "",
        "| Kind | Correct | Total |",
        "|---|---|---|",
    ]
    for kind, (correct, total) in sorted(per_kind.items()):
        lines.append(f"| {kind} | {correct} | {total} |")

    lines.append("")
    lines.append("## Rows")
    lines.append("")
    lines.append("| Title | Kind | Correct | Exact-sequence-match | Note |")
    lines.append("|---|---|---|---|---|")
    for row, result in zip(rows, results):
        title = row["title"].replace("|", "\\|")
        kind = result["extracted"].get("kind") if result["extracted"] else "n/a"
        correct = "yes" if result["correct"] else "no"
        exact = "yes" if (result["compiled"] and result["compiled"] == row["pm5"]) else "no"
        note = result["note"] or ""
        lines.append(f"| {title} | {kind} | {correct} | {exact} | {note} |")

    lines.append("")
    lines.append("## First 20 mismatches")
    lines.append("")
    mismatches = [(row, result) for row, result in zip(rows, results) if not result["correct"]]
    for row, result in mismatches[:20]:
        lines.append(f"### {row['title']}")
        lines.append("")
        lines.append(f"- text: {result['text']}")
        lines.append(f"- extracted: `{json.dumps(result['extracted'])}`")
        lines.append(f"- compiled: `{result['compiled']}`")
        lines.append(f"- gold: `{row['pm5']}`")
        if result["error"]:
            lines.append(f"- error: {result['error']}")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval_path", metavar="EVAL_PATH", help="eval.jsonl-shaped file")
    parser.add_argument("--limit", type=int, default=None, help="limit eval to first N rows")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "none", "anthropic", "claude-cli"],
        help="which backend to use (default: auto)",
    )
    parser.add_argument("--model", default=None, help="model id/alias to use")
    parser.add_argument("--k", type=int, default=25, help="number of few-shot examples")
    parser.add_argument("--no-cache", action="store_true", help="disable response caching")
    parser.add_argument("--out", default=DEFAULT_OUT_PATH, help="output report path")
    args = parser.parse_args(argv)

    from .extract import _default_cache_dir

    cache_dir = None if args.no_cache else _default_cache_dir()

    rows, results = run_eval(
        args.eval_path, args.limit, args.backend, args.model, args.k, cache_dir
    )

    n = len(results)
    n_correct = sum(1 for r in results if r["correct"])

    per_kind: dict = {}
    for row, result in zip(rows, results):
        rule_spec = spec_mod.parse_spec(
            f"{row['title']}\n{row['description']}", row.get("machines")
        )
        kind = (
            result["extracted"].get("kind")
            if result["extracted"]
            else (rule_spec.get("kind") if rule_spec else "unknown")
        )
        bucket = per_kind.setdefault(kind, [0, 0])
        bucket[1] += 1
        if result["correct"]:
            bucket[0] += 1

    accuracy = n_correct / n if n else 0.0
    print(f"accuracy: {n_correct}/{n} ({accuracy:.1%})")
    for kind, (correct, total) in sorted(per_kind.items()):
        print(f"  {kind}: {correct}/{total}")

    _write_report(rows, results, args.backend, args.model, args.k, per_kind, n, n_correct, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
