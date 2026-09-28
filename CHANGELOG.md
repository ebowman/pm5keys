# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - unreleased

### Added

- `pm5keys` CLI: turns a free-form RowErg (and SkiErg) workout
  description into a Concept2 PM5 button-press sequence, with
  `--explain` for a per-press screen/action trace, `--verbose` for the
  parsed spec and its source, and stdin support.
- Deterministic rules parser (`pm5keys.spec`) covering a wide range of
  Concept2's own WOD phrasings (fixed distance/time/calorie intervals,
  slash/comma/dash-separated ladders and pyramids, "equal work and
  rest" chains, single distance/time/calorie workouts, and BikeErg
  distance overrides), with a never-guess policy: ambiguous text is
  left unparsed rather than misprogrammed.
- `WorkoutSpec` intermediate representation (`docs/SPEC.md`) sitting
  between free-form text and PM5 keys, shared by the rules parser, the
  optional LLM extractor, and the compiler.
- PM5 menu/entry-screen state machine simulator (`pm5keys.pm5_model`,
  documented in `docs/pm5-model.md`) and a compiler
  (`pm5keys.compile_keys`) that turns a `WorkoutSpec` into a canonical
  PM5 key sequence, reverse-engineered and verified against 116 gold
  `(title, pm5, spec)` rows scraped from Concept2's public WOD archive:
  108 EXACT, 4 EQUIVALENT, 3 GOLD_VARIABLE, 1 GOLD_MISMATCH (a
  documented Concept2 data typo), 0 MODEL_ERROR, with all 116 gold
  sequences round-tripping through the simulator.
- PM5 button-press notation grammar and canonicalisation rules
  (`pm5keys.keyseq`, documented in `docs/notation.md`).
- Optional LLM fallback (`pip install pm5keys[llm]`) for free-form
  phrasings the deterministic rules can't parse, selectable via
  `--llm {auto,none,anthropic,claude-cli}` and `--model`; the LLM only
  ever proposes a structured `WorkoutSpec`, never PM5 keys directly —
  the same deterministic compiler used for rules-derived specs always
  turns the spec into keys.
- `pm5keys-data` console script (`pm5keys.data`) for fetching, parsing,
  building, checking, splitting, and crosschecking the Concept2 WOD
  dataset (`docs/dataset.md`).
- Evaluation harnesses (`pm5keys.llm.eval_extract`,
  `pm5keys.llm.eval_direct`) comparing the LLM-assisted spec extractor
  and a "let the LLM emit keys directly" baseline against gold, scoped
  to RowErg-only rows.
- Documentation: `docs/pm5-model.md`, `docs/notation.md`,
  `docs/dataset.md`, `docs/SPEC.md`, `README.md`, `CONTRIBUTING.md`.
- Test suite (`tests/`) covering the notation grammar, spec parser
  (including adversarial-probe coverage for the never-guess policy),
  PM5 model, compiler, CLI, dataset docs drift, and fixture PII
  scrubbing.
- PM3/PM4 monitor support (`docs/pm3-model.md`): a `monitor` parameter
  on `pm5_model.PM5`/`run`/`explain` and `compile_keys.compile`/`explain`
  (`'pm5'` default, `'pm3'`, or `'pm4'` as a spelling alias of `'pm3'`),
  and a `--monitor {pm5,pm3,pm4,both}` CLI flag. PM3/PM4 shares every
  entry-screen field layout, default, cursor position, and
  Intervals:Variable rule with PM5; the only differences are a flat
  five-item New Workout chooser (no Intervals submenu) and the absence
  of any calorie workout screen (`compile()` raises `NotImplementedError`
  for `single_calorie`/`intervals_calorie` on `pm3`/`pm4`). Verified
  against 111 gold `pm34` rows (the PM3/PM4 button-sequence column in
  the scraped Concept2 dataset): 103 EXACT, 4 EQUIVALENT, 3
  GOLD_VARIABLE, 1 GOLD_MISMATCH, 0 MODEL_ERROR (5 calorie-workout rows
  have no `pm34` gold and are skipped) via
  `python -m pm5keys.compile_keys --verify --monitor pm3`.
- Static web demo (`web/`, deployed via GitHub Pages by
  `.github/workflows/pages.yml`) running the rules parser and compiler
  entirely client-side with [Pyodide](https://pyodide.org/) — no build
  step, no framework, no LLM in the browser. `web/build_examples.py`
  generates the example-chip titles (`web/examples.js`) from the top
  RowErg/All-Machines rows in `data/dataset_unique.jsonl`.
- Generalized the variable-rest chain matcher (`pm5keys.spec`) to
  accept any work unit (distance, time, or calories) in any leg,
  comma- or slash-separated (never mixed within one chain), with
  optional qualifiers on work legs (`work`/`hard`/`easy`/`light`/
  `steady`/`on`/`warm-up`/`cool-down`/`row`) and a required rest cue on
  rest legs (`rest`/`easy`/`light`/`off`/`recovery`/`paddle`); the
  chain must be a whole line, and text outside it is accepted only as
  an in-order prose restatement of the same legs.
- Extended the never-guess leftover-cue guard to fixed intervals
  (`warm-up`/`cool-down`/`then` remnants) and to `intervals_variable`
  results (`warm-up`/`cool-down` remnants), so text describing an
  untracked extra leg is left unparsed instead of silently dropped.
- Added a session matcher: `[warm-up], N x WORK / REST (, N x WORK /
  REST)*, [cool-down]` folds a warm-up, one or more work/rest sets, and
  a cool-down into a single `intervals_variable` workout. Segments
  split on commas, newlines, `;`, `then`, `and then`, and `followed
  by`; an identical set restated across a newline (title vs.
  description) is deduplicated, while the same restated across a
  comma/`then`/`followed by` is a genuine repeat — so multi-set text
  like `4 x 500m / 1 min rest, then 4 x 250m / 30 sec rest`, which
  previously silently parsed as only the first set, now parses as one
  12-leg variable workout.
- Enforced the PM5 (and PM3/PM4) 50-leg Variable Intervals hard limit:
  compiling an `intervals_variable` spec with more than 50 legs now
  exits 2 with `variable intervals: <n> legs exceeds the PM5 limit of
  50` instead of silently producing an unplayable sequence.
  Concept2 does not document a PM3-specific figure; PM3/PM4 is assumed
  to share the PM5 limit.
- Added `--summary`, a plain-text leg table printed before the
  key-sequence line(s) (one row per leg for `intervals_variable`
  workouts, collapsing consecutive identical legs into a range row),
  and taught `--explain` to collapse runs of consecutive legs that
  program identically into a single `<n>x ...` summary line.
