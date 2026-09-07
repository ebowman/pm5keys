# Contributing

## Dev setup

```
git clone https://github.com/ericbowman/pm5keys.git
cd pm5keys
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

`.[dev]` pulls in `ruff` (lint/format) and `build` (sdist/wheel). The
optional LLM extras (`pip install -e .[llm]`) are not required for
development unless you're touching `src/pm5keys/llm/`.

## Running CI's checks locally

CI (`.github/workflows/ci.yml`) runs, in this order, on every push and
pull request, across Python 3.10-3.13 on Linux and macOS:

```
ruff check .
ruff format --check .
python -m unittest discover -s tests -t .
python -m build
```

Run all four before opening a PR. `ruff format --check .` only checks
formatting; run `ruff format .` (no `--check`) to actually reformat.

## Adding a phrasing rule to `src/pm5keys/spec.py`

`spec.py`'s rule parser (`parse_spec`) turns free-form WOD text into a
`WorkoutSpec` dict (see [docs/SPEC.md](docs/SPEC.md) for the schema and
the current pattern list). When adding a new phrasing pattern:

1. **Never guess.** A rule must only return a spec when it is
   confident the text means exactly that spec — if a pattern is
   ambiguous, or the text could plausibly mean something else,
   `parse_spec` must return `None` (unparsed) rather than a best
   guess. An unparsed row falls through to the optional LLM extractor
   (or a clear CLI error) instead of silently mis-programming someone's
   monitor.
2. **Respect the leftover-cue guard.** Rest/chaining cue words (e.g.
   "then", "rest", "followed by", "on"/"off") occurring in the same
   sentence as a work token disqualify a `single_*` result unless
   they're clearly not describing a second workout leg (e.g. a date
   range's "between" is excluded from the guard). Two or more
   number+unit work tokens in one sentence always disqualify a
   `single_*` guess, regardless of cue words. See
   `ParseSpecSentenceScopedCueGuardProbeTest` in `tests/test_spec.py`
   for the guard's current test coverage and edge cases.
3. **Add a positive test** in `tests/test_spec.py` asserting your new
   pattern parses to the exact expected `WorkoutSpec` dict.
4. **Add adversarial-probe coverage** using the existing convention:
   a `unittest.TestCase` subclass with a docstring naming the guard or
   ambiguity being probed, and one `test_..._unparsed` (or
   `test_probe_...`) method per near-miss phrasing that must *not* be
   accepted by your new rule (or must still return `None`, or must
   return only a specific safe kind — see
   `ParseSpecSentenceScopedCueGuardProbeTest` for the pattern,
   including its "may stay a single"/"already passing" comment style
   for probes that are allowed either outcome or that already pass
   without a code change).
5. **Re-run coverage against the full dataset** and confirm nothing
   else moved:

   ```
   python -m pm5keys.spec --coverage data/dataset_unique.jsonl
   git diff data/spec_parsed.jsonl
   ```

   `git diff` on `data/spec_parsed.jsonl` must be **empty** — your new
   rule should only affect rows it's designed to newly parse (verify
   any intended coverage increase by checking the printed
   `parsed rows: N/123` count went up as expected), not silently
   reclassify existing gold rows. If `data/spec_parsed.jsonl` changed
   in a way you didn't intend, your rule is too broad.
6. Run the full test suite (`python -m unittest discover -s tests -t
   .`) before committing.

## Adding gold rows

Gold `(title, pm5, spec)` rows live in `data/spec_parsed.jsonl` and are
regenerated (not hand-edited) by `pm5keys.spec --coverage`. To add
coverage for a new workout shape:

1. Refresh the dataset per [docs/dataset.md](docs/dataset.md)'s "How to
   rebuild" steps (fetch/parse/build/split), or add a fixture-backed
   row if you're working from a single new WOD page.
2. Regenerate `data/spec_parsed.jsonl`:

   ```
   python -m pm5keys.spec --coverage data/dataset_unique.jsonl
   ```

3. Verify the PM5 menu model and compiler still agree with every gold
   row:

   ```
   python -m pm5keys.compile_keys --verify data/spec_parsed.jsonl
   ```

   This must **not** gain any `MODEL_ERROR` or `GOLD_MISMATCH` rows
   beyond the one pre-existing, documented `GOLD_MISMATCH` (the
   pyramid typo — see
   [docs/pm5-model.md](docs/pm5-model.md#the-evidence-table)). A new
   `MODEL_ERROR` means the simulator or compiler broke on a real gold
   row; a new `GOLD_MISMATCH` means either the compiler's understanding
   of the workout is wrong, or Concept2's published sequence is another
   data anomaly worth documenting (as the existing one is) rather than
   silently accepting.
4. If your change affects `docs/dataset.md`'s "Counts" table, update
   it — `tests/test_dataset_doc.py` recomputes every value in that
   table from `data/*.jsonl` at test time and fails on drift.

## Doc example tables and the docs-count test

Two tests hold specific docs pages to the data so they can't silently
drift:

- **`tests/test_docs.py`** extracts every row of any markdown table
  in `docs/notation.md` or `docs/pm5-model.md` whose header is exactly
  `| Text | PM5 |`, and asserts `compile(parse_spec(text)) == sequence`
  for each row. If you edit or add a worked example in either doc,
  keep it in this exact table shape (header `| Text | PM5 |`, then a
  separator row, then one `| <text> | <sequence> |` row per example)
  so the test picks it up — and make sure the sequence is actually
  correct, since the test will fail otherwise. Do not repurpose this
  exact header for an unrelated table in either file.
- **`tests/test_dataset_doc.py`** extracts `docs/dataset.md`'s
  `## Counts` markdown table (`| metric | value |` shape) and asserts
  every value matches a fresh computation from `data/*.jsonl`. Any
  dataset refresh must be followed by updating that table by hand (or
  regenerating it, if you add tooling to do so) until the test passes.

## PR checklist

Before opening a PR:

- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `python -m unittest discover -s tests -t .` passes (full suite,
      including `tests/test_no_pii.py`)
- [ ] `python -m build` succeeds
- [ ] If you touched `src/pm5keys/spec.py`: added a positive test and
      adversarial-probe coverage in `tests/test_spec.py`, and
      `git diff data/spec_parsed.jsonl` is empty (or changed only as
      intended)
- [ ] If you added gold rows or refreshed the dataset:
      `python -m pm5keys.compile_keys --verify data/spec_parsed.jsonl`
      shows no new `MODEL_ERROR`/`GOLD_MISMATCH`, and
      `docs/dataset.md`'s Counts table is up to date
      (`tests/test_dataset_doc.py` passes)
- [ ] If you edited a `| Text | PM5 |` example table in
      `docs/notation.md` or `docs/pm5-model.md`: `tests/test_docs.py`
      passes
- [ ] New or updated test fixtures under `tests/fixtures/` are
      scrubbed per "Fixtures must be scrubbed" below

## Fixtures must be scrubbed

Test fixtures under `tests/fixtures/` are derived from real "Workout of
the Day" e-mails and web pages. Before committing a new or updated
fixture, strip anything that identifies a real person or subscriber,
including:

- ESP (e.g. Campaign Monitor) tracking links and any subscriber-specific
  token embedded in them — replace the whole line/URL with
  `https://workoutoftheday.example/t/REDACTED`.
- Subscriber-specific unsubscribe/preferences links or tokens.
- Real e-mail addresses, names, or absolute local filesystem
  home-directory paths.

Never commit the actual private token(s) anywhere in the tree or in a
commit message — not even as an example. `tests/test_no_pii.py`
enforces this automatically: it walks the repo and fails if it finds
known personal-identifier *shapes* (a local home-directory path, an
e-mail address ending in `.ie`, an ESP tracking-link shape, or, for
anything under `tests/fixtures/`, the ESP domain fragment), plus any
extra substring you list in a local, gitignored `.pii-patterns.local`
file at the repo root (one per line) — use that file to keep guarding
for your own private tokens without ever committing them. Run the full
suite, including this check, before opening a PR:

```
python -m unittest discover -s tests -t .
```

If you add a new kind of personal identifier to scrub, extend
`tests/test_no_pii.py`'s built-in *pattern shapes* (not literal private
tokens) alongside the fixture change so the check keeps catching it.

## Keeping the dataset docs in sync

When you refresh the dataset, regenerate docs/dataset.md counts (see tests/test_dataset_doc.py).
