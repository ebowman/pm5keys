#!/usr/bin/env python3
"""Split data/dataset_unique.jsonl into leakage-free train/eval sets.

Split unit is *workout identity*, not row. Many workouts in
dataset_unique.jsonl appear twice with the same title/description but a
different `machines` label (e.g. "RowErg and SkiErg" vs "BikeErg") and a
different pm5 sequence for each variant. If the split were done per-row,
one machine variant of a workout could land in train while the other
landed in eval -- since both variants share the same title/description
text, that would leak the eval workout's description into the training
set (and vice versa). To avoid this, identity is defined as
(norm(title), norm(description)) with norm = casefold + collapse
whitespace + strip, deliberately IGNORING `machines`. All rows sharing an
identity (i.e. all machine variants of one workout) are assigned to the
same split as a unit.

Split algorithm:
  1. Collect the distinct identity keys, sorted for determinism.
  2. Shuffle that sorted list with random.Random(seed).
  3. Take the first round(n * eval_frac) keys (minimum 1 if n >= 2) as
     eval; the rest are train.
  4. Guarantee: for any `machines` label with >= 3 unique (identity) rows
     in the whole dataset, if the resulting eval split has zero rows for
     that label, deterministically move one identity into eval: the
     lowest-sorting identity key (among the train identities that carry
     a row with that label) is moved from train to eval. This runs once
     per under-represented label, using the sorted-key order established
     in step 1 (not the shuffled order), so the outcome is reproducible
     for a given input regardless of shuffle.

Output rows keep all original dataset_unique.jsonl fields plus a `split`
key set to "train" or "eval". Within each output file rows are sorted by
(count desc, first_date, machines).

Three pure functions do the real work so they can be unit-tested without
touching the filesystem:

    identity_key(row) -> (norm_title, norm_description)
    split_identities(keys, seed, eval_frac) -> (train_keys, eval_keys)
    assign(rows, seed, eval_frac) -> (train_rows, eval_rows)

Usage::

    pm5keys-data split [--unique data/dataset_unique.jsonl]
        [--train data/train.jsonl] [--eval data/eval.jsonl]
        [--seed 42] [--eval-frac 0.15]

`--unique`, `--train`, and `--eval` default to paths relative to the
current working directory -- this module never writes next to its own
file.
"""

from __future__ import annotations

import argparse
import json
import random
import sys


def _norm(text: str) -> str:
    """casefold + collapse whitespace + strip, for identity keying."""
    return " ".join(text.split()).casefold().strip()


def identity_key(row: dict) -> tuple[str, str]:
    """Workout identity for `row`, ignoring `machines`.

    (norm(title), norm(description)) -- all machine variants of the same
    workout text share this key, so they are always assigned to the same
    split.
    """
    return (_norm(row.get("title", "")), _norm(row.get("description", "")))


def split_identities(
    keys: list[tuple[str, str]], seed: int, eval_frac: float
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split a list of distinct identity keys into (train_keys, eval_keys).

    `keys` is sorted first (for determinism regardless of input order),
    then shuffled with random.Random(seed). The first
    round(n * eval_frac) keys of the shuffled order become eval (minimum
    1 if n >= 2); the remainder become train.
    """
    unique_sorted = sorted(set(keys))
    n = len(unique_sorted)
    shuffled = list(unique_sorted)
    random.Random(seed).shuffle(shuffled)

    eval_count = round(n * eval_frac)
    if n >= 2 and eval_count < 1:
        eval_count = 1
    eval_count = min(eval_count, n)

    eval_keys = shuffled[:eval_count]
    train_keys = shuffled[eval_count:]
    return train_keys, eval_keys


def assign(rows: list[dict], seed: int, eval_frac: float) -> tuple[list[dict], list[dict]]:
    """Assign `rows` to (train_rows, eval_rows) by workout identity.

    All rows sharing an identity_key() land in the same split. After the
    base split, applies the >=3-uniques `machines` guarantee: for any
    machines label with >= 3 distinct identities in `rows`, if none of
    its identities landed in eval, the lowest-sorting train identity
    carrying that label (by identity key, in the full sorted-key order)
    is moved from train to eval.
    """
    all_keys = [identity_key(row) for row in rows]
    train_keys, eval_keys = split_identities(all_keys, seed, eval_frac)
    train_key_set = set(train_keys)
    eval_key_set = set(eval_keys)

    # Map each identity to the set of machines labels it carries, and to
    # the full sorted list of identity keys for deterministic guarantee
    # resolution.
    machines_by_key: dict[tuple[str, str], set] = {}
    for row in rows:
        key = identity_key(row)
        machines_by_key.setdefault(key, set()).add(row["machines"])

    # Count distinct identities per machines label across the whole
    # dataset.
    identity_count_by_machines: dict[str, int] = {}
    for key, machines_set in machines_by_key.items():
        for machines in machines_set:
            identity_count_by_machines[machines] = identity_count_by_machines.get(machines, 0) + 1

    sorted_all_keys = sorted(machines_by_key.keys())

    for machines, ident_count in identity_count_by_machines.items():
        if ident_count < 3:
            continue
        has_eval = any(machines in machines_by_key[key] for key in eval_key_set)
        if has_eval:
            continue
        # Move the lowest-sorting train identity carrying this label
        # from train to eval.
        candidate = None
        for key in sorted_all_keys:
            if key in train_key_set and machines in machines_by_key[key]:
                candidate = key
                break
        if candidate is not None:
            train_key_set.discard(candidate)
            eval_key_set.add(candidate)

    train_rows = [row for row in rows if identity_key(row) in train_key_set]
    eval_rows = [row for row in rows if identity_key(row) in eval_key_set]
    return train_rows, eval_rows


def _sort_key(row: dict) -> tuple:
    return (-row.get("count", 0), row.get("first_date") or "", row.get("machines") or "")


def _read_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _machines_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["machines"]] = counts.get(row["machines"], 0) + 1
    return counts


def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Split data/dataset_unique.jsonl into leakage-free train/eval "
            "sets. The split unit is workout identity "
            "(norm(title), norm(description)), IGNORING `machines`, so "
            "that all machine variants of a workout (which share "
            "title/description text but differ in machines/pm5) always "
            "land in the same split -- splitting per-row would leak a "
            "workout's description across train and eval."
        )
    )
    parser.add_argument(
        "--unique",
        default="data/dataset_unique.jsonl",
        help="input deduped dataset (default: data/dataset_unique.jsonl)",
    )
    parser.add_argument(
        "--train", default="data/train.jsonl", help="train output path (default: data/train.jsonl)"
    )
    parser.add_argument(
        "--eval", default="data/eval.jsonl", help="eval output path (default: data/eval.jsonl)"
    )
    parser.add_argument("--seed", type=int, default=42, help="shuffle seed (default: 42)")
    parser.add_argument(
        "--eval-frac",
        type=float,
        default=0.15,
        help="fraction of identities assigned to eval (default: 0.15)",
    )
    args = parser.parse_args(argv)

    rows = _read_jsonl(args.unique)
    train_rows, eval_rows = assign(rows, args.seed, args.eval_frac)

    for row in train_rows:
        row["split"] = "train"
    for row in eval_rows:
        row["split"] = "eval"

    train_rows_sorted = sorted(train_rows, key=_sort_key)
    eval_rows_sorted = sorted(eval_rows, key=_sort_key)

    _write_jsonl(args.train, train_rows_sorted)
    _write_jsonl(args.eval, eval_rows_sorted)

    total_identities = len({identity_key(row) for row in rows})
    train_identities = len({identity_key(row) for row in train_rows})
    eval_identities = len({identity_key(row) for row in eval_rows})

    print(f"identities: total={total_identities} train={train_identities} eval={eval_identities}")
    print(f"rows: total={len(rows)} train={len(train_rows)} eval={len(eval_rows)}")

    train_machines = _machines_counts(train_rows)
    eval_machines = _machines_counts(eval_rows)
    all_machines = sorted(set(train_machines) | set(eval_machines))
    print("rows by machines:")
    for machines in all_machines:
        print(
            f"  {machines}: train={train_machines.get(machines, 0)} eval={eval_machines.get(machines, 0)}"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    return _run_cli(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
