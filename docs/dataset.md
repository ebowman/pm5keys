# The dataset

A data card for the `data/*.jsonl` files this repo ships and rebuilds
from. Every number in the "Counts" table below is computed directly
from those files (not hand-maintained) and is re-verified by
[`tests/test_dataset_doc.py`](../tests/test_dataset_doc.py) so this
page cannot silently drift from the data.

## What it is

One row per (date, machine group) of Concept2's public "Workout of the
Day" (WOD): the workout's title and description as Concept2 wrote
them, plus the PM5 (and, where Concept2 published one, PM3/PM4) button-
press sequence needed to program that workout into the monitor. A
single calendar date can contribute more than one row when Concept2
published separate button-press sequences for different machine
groups (e.g. "RowErg and SkiErg" vs. "BikeErg") on the same day.

## Source

Every row traces back to a page in Concept2's public WOD archive:

```
https://utilities.concept2.com/wod-email/newsletter/YYYY-MM-DD/en/us
```

- **First page:** `2022-07-08`. Dates before this (`2022-07-01` through
  `2022-07-07` were probed) return HTTP 500 **permanently** — this is
  the archive's floor, not a transient outage; `raw/missing.txt`
  records these as permanent `500`s.
- **Last page:** the maximum `date` present in `data/dataset.jsonl`
  (see the Counts table below for the current value).
- **Pages fetched:** the number of distinct `source_url` values in
  `data/dataset.jsonl` — one page can contribute multiple rows (one per
  machine group), so this is less than the row count.
- **Transient failures:** a 5xx response other than the permanent
  pre-archive floor is treated as transient and retried (see "How to
  rebuild" below); only a 4xx or an exhausted-retry 5xx/network error
  is recorded in `raw/missing.txt` and left unfetched.

## How to rebuild

All commands below use the `pm5keys-data` console script (equivalently
`python -m pm5keys.data <subcommand>`) and the repo's `.venv`. Paths
shown are each subcommand's own default, so the bare commands below
rebuild the dataset in place from the repo root.

1. **Fetch** the raw HTML pages (idempotent — already-downloaded dates
   are skipped unless `--force` is given):

   ```
   pm5keys-data fetch
   ```

   Defaults: `--since 2022-07-01`, `--until <today>`, `--delay 0.5`
   (seconds between requests), `--out raw`. A full fetch from scratch
   takes about 15 minutes (~1,523 pages at 0.5 s/page plus request
   latency). Each 5xx is retried up to 3 times with 1s/2s/4s backoff
   before being recorded as a permanent failure in `raw/missing.txt`;
   4xx responses are recorded immediately with no retry.

2. **Parse** the raw pages into structured records:

   ```
   pm5keys-data parse raw --json data/dataset.jsonl
   ```

3. **Build** the per-row dataset and dedup/reject views:

   ```
   pm5keys-data build --raw raw --out data
   ```

   (writes `data/dataset.jsonl`, `data/dataset_unique.jsonl`,
   `data/dataset_rejects.jsonl` under `--out`).

4. **Check** dataset-wide consistency (label/title conflicts, same-
   sequence/different-description groupings):

   ```
   pm5keys-data check --dataset data/dataset.jsonl --out data/reports/conflicts.md
   ```

5. **Split** the deduplicated dataset into train/eval:

   ```
   pm5keys-data split --unique data/dataset_unique.jsonl --train data/train.jsonl --eval data/eval.jsonl --seed 42 --eval-frac 0.15
   ```

6. **Crosscheck** a sample against the WOD email fixtures (title,
   description, and button sequences must agree with the web page):

   ```
   pm5keys-data crosscheck --fixtures tests/fixtures/email --raw raw --out data/reports/email_crosscheck.md
   ```

7. **Verify** the PM5 menu model and compiler against every gold
   `(title, pm5, spec)` row:

   ```
   python -m pm5keys.compile_keys --verify data/spec_parsed.jsonl
   ```

## Files and schema

All files are newline-delimited JSON (one JSON object per line, UTF-8).

### `data/dataset.jsonl` — one row per (date, machine group)

| Field | Type | Notes |
|---|---|---|
| `date` | `str` (`YYYY-MM-DD`) | date of the WOD page |
| `machines` | `str` | machine-group label as published, e.g. `"All Machines"`, `"RowErg and SkiErg"`, `"BikeErg"` |
| `title` | `str` | workout title as published |
| `description` | `str` | workout description as published |
| `pm5` | `str` | canonical PM5 button-press sequence (see [notation.md](notation.md)) |
| `pm5_expanded` | `list[str]` | `pm5` expanded to one button letter per list element |
| `pm34` | `str \| null` | PM3/PM4 button-press sequence, or `null` when Concept2 printed a note instead of a sequence (see "Known quirks" below) |
| `source_url` | `str` | the archive page this row was parsed from |

Row/field counts for the current data are in the Counts table below.

### `data/dataset_unique.jsonl` and `data/train.jsonl` / `data/eval.jsonl` — deduplicated, one row per distinct (title, description, machines)

Same per-row fields as `dataset.jsonl` (`title`, `description`,
`machines`, `pm5`, `pm5_expanded`, `pm34`) plus:

| Field | Type | Notes |
|---|---|---|
| `count` | `int` | number of `dataset.jsonl` rows collapsed into this one |
| `dates` | `list[str]` | every date this exact (title, description, machines, pm5) combination was published |
| `first_date` | `str` | `min(dates)` |
| `last_date` | `str` | `max(dates)` |
| `split` | `str` | `"train"` or `"eval"` — present only in `train.jsonl`/`eval.jsonl`, not in `dataset_unique.jsonl` |

### `data/dataset_rejects.jsonl` — rows dropped during build

Same shape as `dataset.jsonl` rows that failed a build-time validity
check (e.g. unparseable sequence). Currently empty (0 rows) for the
data shipped in this repo.

### `data/spec_parsed.jsonl` — gold `(title, pm5, spec)` triples

| Field | Type | Notes |
|---|---|---|
| `title` | `str` | workout title |
| `description` | `str` | workout description |
| `machines` | `str` | machine-group label |
| `pm5` | `str` | canonical PM5 button-press sequence |
| `spec` | `object` | the structured `WorkoutSpec` this sequence encodes — see [SPEC.md](SPEC.md) for the schema, keyed by `spec.kind` |

### `data/reports/*.md` — generated reports (regenerate, don't hand-edit)

| File | Produced by |
|---|---|
| `conflicts.md` | `pm5keys-data check` |
| `email_crosscheck.md` | `pm5keys-data crosscheck` |
| `compile_report.md` | `python -m pm5keys.compile_keys --verify` |
| `spec_unparsed.md` | the spec-parsing step that produces `spec_parsed.jsonl` |
| `extract_report.md`, `eval_report.md` | `pm5keys.llm` eval harnesses (LLM-assisted extraction/direct baselines; not part of the deterministic data pipeline) |

## Counts

Computed from `data/*.jsonl` — see
[`tests/test_dataset_doc.py`](../tests/test_dataset_doc.py), which
recomputes each of these at test time and fails if this table drifts
from the data.

| metric | value |
|---|---|
| dataset rows | 1950 |
| dataset_unique rows | 123 |
| dataset_rejects rows | 0 |
| train rows | 103 |
| eval rows | 20 |
| pages fetched (distinct source_url) | 1523 |
| first date | 2022-07-08 |
| last date | 2026-09-07 |
| distinct machines labels | 3 |
| distinct titles | 88 |
| pm34-null rows | 40 |

Distinct `machines` labels and their `dataset.jsonl` row counts:

| machines | rows |
|---|---|
| All Machines | 1096 |
| RowErg and SkiErg | 427 |
| BikeErg | 427 |

## Known quirks

All counts below are computed from the data, not estimated.

- **PM3/PM4 "not supported" notes (40 rows).** On days when a workout
  can't be programmed on a PM3/PM4 (e.g. interval-calorie workouts),
  Concept2 prints a note in place of a button sequence — for example
  `"The PM3 and PM4 monitors do not support interval calorie
  workouts"` (2022-07-13, "8 x 25 Cals with 1 minute easy"). Because
  that text doesn't parse as a valid key sequence, the build step
  stores `pm34: null` for these rows rather than the raw note text.
  There are 40 such rows in `data/dataset.jsonl`.
- **Combined "PM3/PM4/PM5" label (62 raw pages).** On some pages
  Concept2 publishes a single button-press sequence shared by PM3/PM4
  *and* PM5 under one combined `PM3/PM4/PM5:` heading instead of two
  separate `PM3/PM4:` / `PM5:` lines. The parser copies that one
  sequence into both the `pm34` and `pm5` fields. 62 of the 1,523 raw
  HTML pages under `raw/` use this combined-label form.
- **The gold pyramid typo (1 row).** "5 min, 10 min, 15 min, 10 min, 5
  min pyramid / 2 min easy" (first seen 2022-11-28) is a case where
  Concept2's own published button sequence doesn't match its title:
  simulating the gold sequence shows the last leg is actually 15
  minutes, not 5 — an extra button press on Concept2's side, not a
  parsing error here. `pm5keys` compiles the *title's* intended
  symmetric pyramid, not this apparent typo, so this is the one
  `GOLD_MISMATCH` row out of 116 in `compile_keys.py --verify`'s
  categorisation (108 EXACT, 4 EQUIVALENT, 3 GOLD_VARIABLE, 1
  GOLD_MISMATCH, 0 MODEL_ERROR — see
  [pm5-model.md](pm5-model.md#the-evidence-table) and
  `data/reports/compile_report.md`).
- **Train/eval split rule.** The split unit is *workout identity*
  (`casefold + collapse-whitespace` of `title` + `description`),
  deliberately ignoring `machines` — so if a workout has both a
  "RowErg and SkiErg" and a "BikeErg" row in `dataset_unique.jsonl`,
  both variants are assigned to the same split as a unit. This
  prevents one machine variant's description text from leaking between
  train and eval. See `src/pm5keys/data/split.py`'s module docstring
  for the full algorithm (including the under-represented-label
  guarantee).
- **RowErg-only evaluation convention.** `pm5keys`'s LLM-assisted
  extraction pipeline and its eval harnesses
  (`pm5keys.llm.eval_extract`, `pm5keys.llm.eval_direct`) are scoped to
  RowErg only — rows with `machines == "BikeErg"` are excluded from
  those evals (see each module's docstring). `eval.jsonl` itself
  contains all machine groups (20 rows total); excluding `BikeErg`
  rows from `eval.jsonl` leaves 14 rows, which is what those harnesses
  actually evaluate against.

## Attribution and rights

Workout titles, descriptions, and PM5/PM3/PM4 button-press sequences in
this dataset are © Concept2, Inc., scraped from Concept2's public WOD
archive and reproduced here unmodified, for interoperability and
research purposes. This project is not affiliated with, endorsed by,
or sponsored by Concept2, Inc. See [`NOTICE`](../NOTICE) at the repo
root for the short-form version of this statement.

If you are Concept2 (or represent Concept2) and want this content
removed or handled differently, please open an issue at
<https://github.com/ebowman/pm5keys/issues> — that's also the
contact point for any other question about this dataset.

## As-is

This dataset is provided as-is, scraped and parsed automatically from
public web pages. Parsing errors are possible despite the consistency
checks described above (`pm5keys-data check`, `crosscheck`, and
`compile_keys.py --verify`). Always verify any generated button-press
sequence on your own monitor before relying on it — see
[verification.md](verification.md) (pending: not yet pressed on
hardware) for how.
