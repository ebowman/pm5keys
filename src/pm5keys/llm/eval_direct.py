#!/usr/bin/env python3
"""Comparison baseline: what happens if the LLM is asked to emit the
PM5 button-press key sequence directly, instead of a WorkoutSpec JSON
object (which is what pm5keys.llm.extract_spec does, and which
pm5keys.cli's pipeline is built on)?

The real pipeline (pm5keys.cli) never lets the LLM emit key presses --
pm5keys.spec or pm5keys.llm.extract_spec produce a WorkoutSpec, and
pm5keys.compile_keys deterministically compiles that spec into a PM5
sequence. This module measures the alternative: ask the LLM to emit
the PM5 sequence directly, and see how well it does compared to the
real (spec-based) pipeline run over the same rows.

Scope: RowErg only. Rows with machines == 'BikeErg' are excluded from
both the few-shot pool (--train, default data/train.jsonl) and the
eval set (--eval, default data/eval.jsonl).

Prompt: the package-data EVAL_PROMPT.md, filled in with {legend} (the
contents of docs/PM5_KEYS.md), {examples} (K few-shot 'Workout: <title>.
<description>' / 'PM5: <pm5>' pairs from non-BikeErg --train rows chosen
by pm5keys.llm.extract's difflib title-similarity ranking), and {text}
(the eval workout, phrased the same way as the examples, plus the
instruction to answer with the sequence only).

Scoring, per eval row:
  - exact: the extracted prediction's keyseq.canonical form equals the
    gold sequence's keyseq.canonical form.
  - semantic: pm5_model.run() on the prediction and on gold simulate to
    the same workout via compile_keys.same_workout. Any pm5_model.run
    ValueError on either side counts as False, never an exception.
  - unparsable: the model's answer, after stripping a 'PM5:' prefix,
    code fences, and surrounding whitespace, contains no token run
    that keyseq.validate accepts (or contains nothing at all).

For the same rows, the deterministic pipeline (spec.parse_spec +
compile_keys.compile, no LLM at all) is also scored exact/semantic
against gold, so the report and this module's stdout summary show the
LLM-direct numbers next to the real pipeline's numbers.

Responses are cached under $XDG_CACHE_HOME/pm5keys (or
~/.cache/pm5keys), keyed by sha256(backend_name + model + prompt), via
pm5keys.llm.extract's cache helpers, so reruns are free unless
--no-cache is given.

CLI:
    python -m pm5keys.llm.eval_direct [--eval data/eval.jsonl]
                                       [--train data/train.jsonl]
                                       [--limit N] [--backend auto]
                                       [--model M] [--k 30] [--no-cache]
                                       [--out data/reports/eval_report.md]
        Runs the comparison over every non-BikeErg row of --eval
        (optionally truncated to the first N rows by --limit), writes
        the report to --out, and prints the summary to stdout.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re

from .. import compile_keys as ck
from .. import keyseq
from .. import pm5_model as pm5
from .. import spec as spec_mod
from .extract import _default_cache_dir, _get_response, resolve_backend

_LLM_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_ROOT = os.path.dirname(os.path.dirname(_LLM_DIR))
_REPO_ROOT = os.path.dirname(_PACKAGE_ROOT)

PROMPT_PATH = os.path.join(_LLM_DIR, "EVAL_PROMPT.md")
LEGEND_PATH = os.path.join(_REPO_ROOT, "docs", "PM5_KEYS.md")
DEFAULT_EVAL_PATH = os.path.join(_REPO_ROOT, "data", "eval.jsonl")
DEFAULT_TRAIN_PATH = os.path.join(_REPO_ROOT, "data", "train.jsonl")
DEFAULT_OUT_PATH = os.path.join(_REPO_ROOT, "data", "reports", "eval_report.md")

DEFAULT_K = 30


# ---------------------------------------------------------------------------
# Few-shot pool and prompt assembly
# ---------------------------------------------------------------------------


def load_pool(train_path: str = DEFAULT_TRAIN_PATH) -> list:
    """Return the few-shot pool: rows from train_path with machines !=
    'BikeErg'. Each pool entry is a dict with 'title', 'description',
    and 'pm5' (the gold key sequence)."""
    pool = []
    with open(train_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    for row in rows:
        if row.get("machines") == "BikeErg":
            continue
        pool.append(
            {
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "pm5": row.get("pm5", ""),
            }
        )

    return pool


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def build_examples(title: str, pool: list, k: int = DEFAULT_K) -> list:
    """Return the k pool entries with the highest SequenceMatcher ratio
    between `title` and the entry's title."""
    scored = [(_similarity(title, entry["title"]), entry) for entry in pool]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _ratio, entry in scored[:k]]


def _format_examples(examples: list) -> str:
    blocks = []
    for entry in examples:
        blocks.append(f"Workout: {entry['title']}. {entry['description']}\nPM5: {entry['pm5']}")
    return "\n\n".join(blocks)


def _load_legend() -> str:
    with open(LEGEND_PATH, encoding="utf-8") as f:
        return f.read()


def _load_prompt_template() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def build_prompt(title: str, description: str, pool: list, k: int = DEFAULT_K) -> str:
    """Build the full EVAL_PROMPT.md-shaped prompt for one eval row."""
    template = _load_prompt_template()
    legend = _load_legend()
    examples = build_examples(title, pool, k=k)
    text = f"Workout: {title}. {description}"
    return template.format(
        legend=legend,
        examples=_format_examples(examples),
        text=text,
    )


# ---------------------------------------------------------------------------
# Answer extraction
# ---------------------------------------------------------------------------

# A single PM5 token: optional digit count then one uppercase letter A-E.
_TOKEN = r"\d*[A-E]"
# The longest run of '-'-joined tokens found anywhere in the answer.
_SEQUENCE_RUN_RE = re.compile(rf"{_TOKEN}(?:-{_TOKEN})*")


def extract_answer(response_text: str) -> str | None:
    """Extract a PM5 key-sequence candidate from a raw model answer.
    Strips a leading 'PM5:' label (case-insensitive), Markdown code
    fences, and surrounding whitespace/prose, then finds the first
    (and, in practice, longest available) run of '-'-joined
    [count]LETTER tokens. Returns the raw candidate substring, or None
    if no such run exists. Does not validate the candidate -- callers
    should run it through keyseq.validate/canonical themselves."""
    if response_text is None:
        return None

    text = response_text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    text = re.sub(r"^PM5:\s*", "", text, flags=re.IGNORECASE)
    text = text.strip()

    best = None
    for match in _SEQUENCE_RUN_RE.finditer(text):
        candidate = match.group(0)
        if best is None or len(candidate) > len(best):
            best = candidate

    return best


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _safe_run(seq: str):
    """Run pm5_model.run(seq), returning None on any ValueError (an
    invalid or unsimulatable sequence) instead of raising."""
    try:
        return pm5.run(seq)
    except ValueError:
        return None


def score_prediction(prediction_raw: str | None, gold: str) -> dict:
    """Score one LLM prediction against gold. Returns a dict with keys:
    unparsable (bool), exact (bool), semantic (bool), canonical (the
    predicted sequence's canonical form, or None if unparsable),
    sim_pred (pm5_model.run's dict for the prediction, or None),
    sim_gold (pm5_model.run's dict for gold, or None)."""
    result = {
        "unparsable": False,
        "exact": False,
        "semantic": False,
        "canonical": None,
        "sim_pred": None,
        "sim_gold": None,
    }

    gold_canonical = keyseq.canonical(gold)
    result["sim_gold"] = _safe_run(gold)

    if prediction_raw is None:
        result["unparsable"] = True
        return result

    try:
        keyseq.validate(prediction_raw)
    except ValueError:
        result["unparsable"] = True
        return result

    pred_canonical = keyseq.canonical(prediction_raw)
    result["canonical"] = pred_canonical

    result["exact"] = pred_canonical == gold_canonical

    sim_pred = _safe_run(pred_canonical)
    result["sim_pred"] = sim_pred
    if sim_pred is not None and result["sim_gold"] is not None:
        result["semantic"] = ck.same_workout(sim_pred, result["sim_gold"])

    return result


def score_pipeline_row(row: dict) -> dict:
    """Score the deterministic pipeline (spec.parse_spec +
    compile_keys.compile, no LLM) against gold for one eval row.
    Returns a dict with keys: exact (bool), semantic (bool), compiled
    (the compiled sequence, or None if parse/compile failed)."""
    result = {"exact": False, "semantic": False, "compiled": None}

    text = f"{row.get('title', '')}\n{row.get('description', '')}"
    parsed = spec_mod.parse_spec(text, None)
    if parsed is None:
        return result

    parsed = dict(parsed)
    parsed["machine"] = "rower"

    try:
        compiled = ck.compile(parsed)
    except (ValueError, NotImplementedError):
        return result

    result["compiled"] = compiled

    gold = row.get("pm5", "")
    result["exact"] = keyseq.canonical(compiled) == keyseq.canonical(gold)

    sim_compiled = _safe_run(compiled)
    sim_gold = _safe_run(gold)
    if sim_compiled is not None and sim_gold is not None:
        result["semantic"] = ck.same_workout(sim_compiled, sim_gold)

    return result


# ---------------------------------------------------------------------------
# Eval driver
# ---------------------------------------------------------------------------


def _load_rows(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if r.get("machines") != "BikeErg"]


def _eval_row(
    row: dict, backend, model: str | None, k: int, pool: list, cache_dir: str | None
) -> dict:
    title = row.get("title", "")
    description = row.get("description", "")
    gold = row.get("pm5", "")

    prompt = build_prompt(title, description, pool, k=k)
    response_text = _get_response(prompt, backend, model or "", cache_dir)
    prediction_raw = extract_answer(response_text)

    llm_score = score_prediction(prediction_raw, gold)
    pipeline_score = score_pipeline_row(row)

    return {
        "title": title,
        "description": description,
        "gold": gold,
        "response_text": response_text,
        "prediction_raw": prediction_raw,
        "llm": llm_score,
        "pipeline": pipeline_score,
    }


def run_eval(
    eval_path: str,
    train_path: str,
    limit: int | None,
    backend_name: str,
    model: str | None,
    k: int,
    cache_dir: str | None,
) -> list:
    rows = _load_rows(eval_path)
    if limit is not None:
        rows = rows[:limit]

    pool = load_pool(train_path)
    backend = resolve_backend(backend_name)

    return [_eval_row(row, backend, model, k, pool, cache_dir) for row in rows]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _pct(n: int, total: int) -> str:
    return f"{n / total:.1%}" if total else "n/a"


def summarize(results: list) -> dict:
    n = len(results)
    llm_exact = sum(1 for r in results if r["llm"]["exact"])
    llm_semantic = sum(1 for r in results if r["llm"]["semantic"])
    llm_unparsable = sum(1 for r in results if r["llm"]["unparsable"])
    pipeline_exact = sum(1 for r in results if r["pipeline"]["exact"])
    pipeline_semantic = sum(1 for r in results if r["pipeline"]["semantic"])
    return {
        "n": n,
        "llm_exact": llm_exact,
        "llm_semantic": llm_semantic,
        "llm_unparsable": llm_unparsable,
        "pipeline_exact": pipeline_exact,
        "pipeline_semantic": pipeline_semantic,
    }


def print_summary(summary: dict, backend_name: str, model: str | None, k: int) -> None:
    n = summary["n"]
    print(f"backend: {backend_name}, model: {model or '(default)'}, k: {k}, n rows: {n}")
    print(
        "LLM-direct: exact "
        f"{summary['llm_exact']}/{n} ({_pct(summary['llm_exact'], n)}), "
        f"semantic {summary['llm_semantic']}/{n} ({_pct(summary['llm_semantic'], n)}), "
        f"unparsable {summary['llm_unparsable']}/{n} ({_pct(summary['llm_unparsable'], n)})"
    )
    print(
        "Pipeline (deterministic): exact "
        f"{summary['pipeline_exact']}/{n} ({_pct(summary['pipeline_exact'], n)}), "
        f"semantic {summary['pipeline_semantic']}/{n} ({_pct(summary['pipeline_semantic'], n)})"
    )


def write_report(
    results: list,
    summary: dict,
    backend_name: str,
    model: str | None,
    k: int,
    out_path: str = DEFAULT_OUT_PATH,
) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n = summary["n"]
    lines = [
        "# eval_direct.py report -- LLM-direct key-sequence baseline",
        "",
        "Comparison baseline: the LLM is asked to emit the PM5 key",
        "sequence directly, instead of a WorkoutSpec JSON object. The real",
        "pipeline (pm5keys.cli) never lets the LLM emit key presses --",
        "this report exists to show the gap between that and asking it to.",
        "",
        "RowErg only (rows with machines == BikeErg excluded).",
        "",
        f"backend: {backend_name}, model: {model or '(default)'}, k: {k}, n rows: {n}",
        "",
        "## LLM-direct",
        "",
        f"- exact: {summary['llm_exact']}/{n} ({_pct(summary['llm_exact'], n)})",
        f"- semantic: {summary['llm_semantic']}/{n} ({_pct(summary['llm_semantic'], n)})",
        f"- unparsable: {summary['llm_unparsable']}/{n} ({_pct(summary['llm_unparsable'], n)})",
        "",
        "## Deterministic pipeline (spec.parse_spec + compile_keys.compile, no LLM)",
        "",
        f"- exact: {summary['pipeline_exact']}/{n} ({_pct(summary['pipeline_exact'], n)})",
        f"- semantic: {summary['pipeline_semantic']}/{n} ({_pct(summary['pipeline_semantic'], n)})",
        "",
        "## Rows",
        "",
        "| Title | Gold | LLM prediction | Exact? | Semantic? | Pipeline exact? |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        title = r["title"].replace("|", "\\|")
        gold = r["gold"].replace("|", "\\|")
        pred = (r["prediction_raw"] or "(unparsable)").replace("|", "\\|")
        exact = "yes" if r["llm"]["exact"] else "no"
        semantic = "yes" if r["llm"]["semantic"] else "no"
        pipeline_exact = "yes" if r["pipeline"]["exact"] else "no"
        lines.append(f"| {title} | {gold} | {pred} | {exact} | {semantic} | {pipeline_exact} |")

    lines.append("")
    lines.append("## LLM mismatches")
    lines.append("")
    mismatches = [r for r in results if not r["llm"]["exact"]]
    if not mismatches:
        lines.append("(none)")
    for r in mismatches:
        lines.append(f"### {r['title']}")
        lines.append("")
        lines.append(f"- description: {r['description']}")
        lines.append(f"- gold: `{r['gold']}`")
        lines.append(f"- predicted: `{r['prediction_raw']}`")
        lines.append(f"- unparsable: {r['llm']['unparsable']}")
        lines.append(f"- semantic match: {r['llm']['semantic']}")
        if r["llm"]["sim_pred"] is not None and r["llm"]["sim_gold"] is not None:
            lines.append(f"- simulated prediction: `{json.dumps(r['llm']['sim_pred'])}`")
            lines.append(f"- simulated gold: `{json.dumps(r['llm']['sim_gold'])}`")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", default=DEFAULT_EVAL_PATH, help="eval.jsonl-shaped file")
    parser.add_argument(
        "--train", default=DEFAULT_TRAIN_PATH, help="train.jsonl-shaped file (few-shot pool)"
    )
    parser.add_argument("--limit", type=int, default=None, help="limit eval to first N rows")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "none", "anthropic", "claude-cli"],
        help="which backend to use (default: auto)",
    )
    parser.add_argument("--model", default=None, help="model id/alias to use")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="number of few-shot examples")
    parser.add_argument("--no-cache", action="store_true", help="disable response caching")
    parser.add_argument("--out", default=DEFAULT_OUT_PATH, help="output report path")
    args = parser.parse_args(argv)

    cache_dir = None if args.no_cache else _default_cache_dir()

    results = run_eval(
        args.eval, args.train, args.limit, args.backend, args.model, args.k, cache_dir
    )
    summary = summarize(results)
    print_summary(summary, args.backend, args.model, args.k)
    write_report(results, summary, args.backend, args.model, args.k, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
