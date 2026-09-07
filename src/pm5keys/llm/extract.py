#!/usr/bin/env python3
"""LLM fallback: turn free-form Concept2 RowErg workout text into a
WorkoutSpec JSON dict (never a PM5 key sequence -- pm5keys.compile_keys
handles WorkoutSpec -> keys separately).

Scope: RowErg only. Every spec this module produces has
`"machine": "rower"` forced, regardless of what the source text says or
what pm5keys.spec's rule parser would have inferred. Any BikeErg
parenthetical in the text (e.g. "(BikeErg: 2000m)") is ignored -- it
never affects the extracted spec.

extract_spec(text, backend=None, model=None, k=25, cache_dir=None)
builds a prompt from the package-data EXTRACT_PROMPT.md (schema +
few-shot examples selected from the few-shot pool by title similarity +
the query text), asks the resolved backend to complete it, parses the
JSON result, forces machine="rower", validates it against
pm5keys.spec's schema, and retries once (with the validation error
appended to the prompt) if the first answer doesn't parse or validate.

Few-shot pool: unlike the original wod/llm_extract.py (which drew its
pool from a dedicated wod/train.jsonl split), this module's default
pool is built from the package-data dataset src/pm5keys/data/
dataset_unique.jsonl, filtered to rows with machines != 'BikeErg' that
pm5keys.spec.parse_spec can parse. Because dataset_unique.jsonl is the
*full* dataset (not a train/eval split), the default pool necessarily
includes rows that also appear in any eval set (e.g. data/eval.jsonl).
Callers that need to keep eval identities out of the few-shot pool
(e.g. the eval scripts in this subpackage) MUST pass an explicit `pool`
argument built to exclude those rows -- extract_spec() itself does not
know about, and cannot exclude, any particular eval split.

backend may be:
    - None: resolved via resolve_backend('auto').
    - a string ('auto', 'none', 'anthropic', 'claude-cli'): resolved
      via resolve_backend(name).
    - a Backend instance: used as-is.

CLI:
    python3 -m pm5keys.llm.extract "<text>" [--backend auto] [--model M]
                                    [--k 25] [--no-cache]
        Extract a single piece of text and print the resulting
        WorkoutSpec JSON, or exit 2 and print the error to stderr.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import sys

from .. import spec as spec_mod
from .backends import Backend, ExtractError, resolve_backend

_LLM_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_LLM_DIR), "data")

PROMPT_PATH = os.path.join(_LLM_DIR, "EXTRACT_PROMPT.md")
DEFAULT_DATASET_PATH = os.path.join(_DATA_DIR, "dataset_unique.jsonl")

# Five hand-written free-form examples with correct specs, used to seed
# the few-shot pool alongside the dataset-derived examples.
HANDWRITTEN_EXAMPLES = [
    (
        "four hard 500s with 90 seconds off",
        {
            "machine": "rower",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 90,
            "count": 4,
            "notes": "hard",
        },
    ),
    (
        "a steady 5k",
        {
            "machine": "rower",
            "kind": "single_distance",
            "work": {"distance_m": 5000},
            "notes": "steady",
        },
    ),
    (
        "a 20 minute piece",
        {
            "machine": "rower",
            "kind": "single_time",
            "work": {"time_s": 1200},
            "notes": "",
        },
    ),
    (
        "pyramid 1-2-3-2-1 minutes, a minute off between",
        {
            "machine": "rower",
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 60}, "rest_s": 60},
                {"work": {"time_s": 120}, "rest_s": 60},
                {"work": {"time_s": 180}, "rest_s": 60},
                {"work": {"time_s": 120}, "rest_s": 60},
                {"work": {"time_s": 60}, "rest_s": 0},
            ],
            "notes": "pyramid",
        },
    ),
    (
        "30 seconds on, 30 off, ten times",
        {
            "machine": "rower",
            "kind": "intervals_time",
            "work": {"time_s": 30},
            "rest_s": 30,
            "count": 10,
            "notes": "",
        },
    ),
    (
        "2 rounds of 8 x 30 seconds on, 30 seconds off, with 2 minutes between rounds",
        {
            "machine": "rower",
            "kind": "intervals_variable",
            "intervals": [
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 120},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 30},
                {"work": {"time_s": 30}, "rest_s": 0},
            ],
            "notes": "2 rounds of 8 x 30s on/30s off",
        },
    ),
]


# ---------------------------------------------------------------------------
# Few-shot example selection
# ---------------------------------------------------------------------------


def _row_example_text(row: dict) -> str:
    title = row.get("title", "")
    description = row.get("description", "")
    return f"{title}. {description}"


def load_pool(dataset_path: str = DEFAULT_DATASET_PATH, rows: list | None = None) -> list:
    """Return the few-shot pool: rows from dataset_path (or, if `rows`
    is given, that in-memory list instead of reading dataset_path) with
    machines != 'BikeErg' that pm5keys.spec.parse_spec can parse. Each
    pool entry is a dict with 'title', 'description', 'text' (title +
    '. ' + description) and 'spec' (the rule parser's spec, machine
    forced to 'rower').

    NOTE: the default pool (dataset_path=DEFAULT_DATASET_PATH) is drawn
    from the full dataset, which includes any rows also used as eval
    identities elsewhere (e.g. data/eval.jsonl). Pass `rows` (a
    pre-filtered list of row dicts, e.g. with eval identities removed)
    when the caller needs to exclude specific rows from the pool.
    """
    pool = []
    if rows is None:
        with open(dataset_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]

    for row in rows:
        if row.get("machines") == "BikeErg":
            continue
        title = row.get("title", "")
        description = row.get("description", "")
        parse_text = f"{title}\n{description}"
        parsed = spec_mod.parse_spec(parse_text, row.get("machines"))
        if parsed is None:
            continue
        example_spec = dict(parsed)
        example_spec["machine"] = "rower"
        pool.append(
            {
                "title": title,
                "description": description,
                "text": _row_example_text(row),
                "spec": example_spec,
            }
        )

    for text, spec_dict in HANDWRITTEN_EXAMPLES:
        pool.append({"title": text, "description": "", "text": text, "spec": spec_dict})

    return pool


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def build_examples(text: str, pool: list, k: int = 25) -> list:
    """Return the k pool entries with the highest SequenceMatcher ratio
    between `text` and the entry's title (fallback to description if
    title is empty)."""
    scored = []
    for entry in pool:
        key = entry.get("title") or entry.get("description") or ""
        ratio = _similarity(text, key)
        scored.append((ratio, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _ratio, entry in scored[:k]]


def _format_examples(examples: list) -> str:
    blocks = []
    for entry in examples:
        blocks.append(f"Text: {entry['text']}\nSpec: {json.dumps(entry['spec'])}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _load_prompt_template() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def build_prompt(text: str, pool: list, k: int = 25) -> str:
    template = _load_prompt_template()
    examples = build_examples(text, pool, k=k)
    schema_json = json.dumps(spec_mod.SCHEMA, indent=2)
    return template.format(
        schema=schema_json,
        examples=_format_examples(examples),
        text=text,
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _default_cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "pm5keys")


def _cache_key(backend_name: str, model: str, prompt: str) -> str:
    h = hashlib.sha256()
    h.update(backend_name.encode("utf-8"))
    h.update(b"\0")
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(prompt.encode("utf-8"))
    return h.hexdigest()


def _cache_path(cache_dir: str, key: str) -> str:
    return os.path.join(cache_dir, f"{key}.txt")


def _get_response(prompt: str, backend: Backend, model: str, cache_dir: str | None) -> str:
    backend_name = getattr(backend, "name", type(backend).__name__)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        key = _cache_key(backend_name, model or "", prompt)
        path = _cache_path(cache_dir, key)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
        response_text = backend.complete(prompt, model)
        with open(path, "w", encoding="utf-8") as f:
            f.write(response_text)
        return response_text

    return backend.complete(prompt, model)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _parse_response(response_text: str) -> dict:
    """Parse a raw backend response into a spec dict, forcing machine
    to 'rower'. Raises ExtractError if the JSON has an 'error' key, and
    ValueError (propagated from validate_spec) if the spec is invalid.
    json.JSONDecodeError propagates on malformed JSON."""
    cleaned = _strip_code_fences(response_text)
    data = json.loads(cleaned)

    if not isinstance(data, dict):
        raise ExtractError("response is not a JSON object")

    if "error" in data:
        raise ExtractError(str(data["error"]))

    data = dict(data)
    data["machine"] = "rower"
    spec_mod.validate_spec(data)
    return data


# ---------------------------------------------------------------------------
# extract_spec
# ---------------------------------------------------------------------------


def extract_spec(
    text: str,
    backend: str | Backend | None = None,
    model: str | None = None,
    k: int = 25,
    cache_dir: str | None = None,
    pool: list | None = None,
) -> dict:
    """Extract a WorkoutSpec dict from free-form text via the resolved
    backend. Raises ExtractError if no valid spec can be produced after
    one retry.

    backend: None resolves via resolve_backend('auto'); a string
    resolves via resolve_backend(name); a Backend instance is used
    as-is.

    cache_dir: if None (and not explicitly disabled by the caller),
    defaults to $XDG_CACHE_HOME/pm5keys (or ~/.cache/pm5keys). Pass the
    empty string or False-y sentinel handling is the caller's
    responsibility -- this function treats any falsy cache_dir as "use
    the default", so callers that want caching fully OFF (--no-cache)
    should not call this with cache_dir=None; see the CLI below, which
    passes a distinct disable flag.
    """
    if pool is None:
        pool = load_pool()

    if backend is None:
        backend = resolve_backend("auto")
    elif isinstance(backend, str):
        backend = resolve_backend(backend)

    prompt = build_prompt(text, pool, k=k)
    model_name = model or ""

    response_text = _get_response(prompt, backend, model_name, cache_dir)

    try:
        return _parse_response(response_text)
    except ExtractError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        retry_prompt = (
            prompt
            + f"\n\nYour previous answer was invalid: {exc}\n"
            "Respond with corrected JSON only, no prose, no code fences."
        )
        retry_response_text = _get_response(retry_prompt, backend, model_name, cache_dir)
        try:
            return _parse_response(retry_response_text)
        except ExtractError:
            raise
        except (json.JSONDecodeError, ValueError) as exc2:
            raise ExtractError(f"invalid spec after retry: {exc2}") from exc2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="free-form workout text to extract")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "none", "anthropic", "claude-cli"],
        help="which backend to use (default: auto)",
    )
    parser.add_argument("--model", default=None, help="model id/alias to use")
    parser.add_argument("--k", type=int, default=25, help="number of few-shot examples")
    parser.add_argument(
        "--no-cache", action="store_true", help="disable response caching"
    )
    args = parser.parse_args(argv)

    cache_dir = None if args.no_cache else _default_cache_dir()

    try:
        result = extract_spec(
            args.text, backend=args.backend, model=args.model, k=args.k, cache_dir=cache_dir
        )
    except ExtractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
