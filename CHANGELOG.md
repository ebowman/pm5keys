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
