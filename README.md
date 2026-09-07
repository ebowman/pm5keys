# pm5keys

`pm5keys` turns a free-form rowing workout description — the kind of
sentence a coach types into a WOD email — into the exact button-press
sequence you punch into a Concept2 PM5 monitor to program it. It's for
rowers, coxes, and coaches who want to stop translating "8 x 500m, 2
minutes rest" into `B-2D-5A-2B-E` by hand.

## Demo

```
$ pm5keys "8 x 500m, 2 minutes rest"
8 x 500m, 2 minutes rest
PM5: B-2D-5A-2B-E

$ pm5keys --explain "8 x 500m, 2 minutes rest"
8 x 500m, 2 minutes rest
PM5: B-2D-5A-2B-E
B    Main Menu          : Select Workout
D    Select Workout     : New Workout
D    New Workout        : Intervals
A    Intervals          : Distance
4xA  Intervals: Distance: cursor right to rest minutes
2xB  Intervals: Distance: rest minutes +2 (now 2)
E    Intervals: Distance: confirm
```

`--explain` walks the PM5's own menu simulator press by press, so you
can see exactly which screen each button acts on and why.

## Install

Not yet on PyPI (pending release) — until then, install straight from
the repo:

```
pip install git+https://github.com/ericbowman/pm5keys.git
```

or with `pipx`, if you want `pm5keys` on your `PATH` without touching
any project's virtualenv:

```
pipx install git+https://github.com/ericbowman/pm5keys.git
```

From source, for development:

```
git clone https://github.com/ericbowman/pm5keys.git
cd pm5keys
pip install -e .[dev]
```

## Usage

```
pm5keys "<text>" [options]
```

With no positional argument, the workout text is read from stdin.

| Flag | Meaning |
|---|---|
| `--explain` | print a per-press explanation of the PM5 sequence (screen + action for each button) |
| `--llm {auto,none,anthropic,claude-cli}` | which LLM backend to use when the deterministic rules can't parse the text (default: `auto` — prefers the Anthropic SDK+key, then the `claude` CLI, then disables the fallback) |
| `--no-llm` | alias for `--llm none`; never fall back to the LLM extractor |
| `--model MODEL` | LLM model id/alias to pass through to the resolved backend |
| `--verbose` | print the parsed spec as JSON and its source (`rules` or `llm`) to stderr |
| (stdin) | omit the positional `text` argument and pipe the workout description in instead |
| `--version` | print `pm5keys`'s version and exit 0 |

Exit codes: `0` on success. `2`, with a one-line message on stderr and
no traceback, when: the input text is empty; the rules can't parse the
text and `--llm none`/`--no-llm` was given; the resolved LLM backend is
unavailable when the fallback is needed (e.g. the `llm` extra isn't
installed, or no API key/CLI is configured); the LLM extractor fails;
or the parsed spec fails to compile into PM5 keys.

## What it understands

The deterministic rules parser (no LLM involved) handles a wide range
of Concept2's own WOD phrasings directly, for example:

- `8 x 500m, 2 minutes rest`
- `10 x 1 min / 1 min easy`
- `10 x 2:30 / 30 seconds easy`
- `20 x 45s work, 45s rest`
- `12 X 25 Cals with 1 minute easy`
- `10 x 20 calories/:20 rest`
- `1/3/5/3/1 minutes with 2 minutes rest`
- `2000/1500/1000/500m with three minutes rest`

Free-form phrasings that don't match a known pattern fall back to an
optional LLM extractor (see Install/Usage above), for example:

- `four hard 500s with 90 seconds off`
- `an easy 5k to loosen up`
- `pyramid 1-2-3-2-1 minutes, a minute off between`
- `2 rounds of 8 x 30 seconds on, 30 off, 2 minutes between rounds`

See [docs/SPEC.md](docs/SPEC.md) for the full pattern list.

## How accurate is it

Against 116 gold `(title, button-sequence)` pairs scraped from
Concept2's own public WOD archive: 108/116 compile to Concept2's exact
published button sequence, 4/116 compile to a different-but-equivalent
sequence (same resulting workout, different button path), 3/116 are
cases where Concept2 itself used the PM5's Variable-interval screen for
a workout the fixed-interval screens could have programmed directly,
and 1/116 is a Concept2 data error (a pyramid workout whose published
sequence doesn't match its own title) that `pm5keys` deliberately does
not reproduce. Separately, all 116/116 of those gold sequences
round-trip through the PM5 menu simulator back to their originating
workout, which validates the menu *model* independently of the
compiler. On the RowErg-only LLM eval set (14 rows), the LLM-assisted
spec extractor gets 14/14 correct; asking an LLM to emit PM5 keys
directly, instead of a structured spec, gets only 2/14 exact matches —
which is exactly why `pm5keys`'s deterministic pipeline never lets an
LLM emit key presses itself; the LLM (when used at all) only ever
proposes a structured workout spec, and the same deterministic compiler
turns every spec, rules-derived or LLM-derived, into keys.

See [docs/pm5-model.md](docs/pm5-model.md) for the full menu model and
evidence table behind these numbers.

## Limitations

- **RowErg (and SkiErg) only.** SkiErg shares the exact same PM5 button
  sequences as RowErg, so it's covered for free. BikeErg workouts often
  use different (typically doubled) distances; `pm5keys` doesn't
  compute these for you — if you're on a BikeErg, work out the
  doubled distance yourself and enter it into the tool's input text.
- **PM3/PM4 monitors are not supported yet.** Only PM5 button sequences
  are generated.
- Two entry-screen details (the Single Calorie screen's layout, and
  whether digit fields wrap or clamp at 0/9) each rest on a single
  observed data point rather than broad corpus coverage — see the
  evidence table in [docs/pm5-model.md](docs/pm5-model.md#the-evidence-table).
- Hardware verification against a real PM5 monitor is pending; a
  verification guide is coming — see `docs/verification.md` (not yet
  written).

## Docs

- [docs/pm5-model.md](docs/pm5-model.md) — the PM5 menu/entry-screen
  state machine `pm5keys` simulates and compiles against.
- [docs/notation.md](docs/notation.md) — the `B-2D-5A-2B-E`-style
  button-press notation itself.
- [docs/dataset.md](docs/dataset.md) — the Concept2 WOD dataset this
  project is built and verified against.

## Attribution

Concept2, PM5, RowErg, SkiErg, and BikeErg are trademarks of Concept2,
Inc. `pm5keys` is not affiliated with, endorsed by, or sponsored by
Concept2, Inc. This project bundles Concept2 WOD text and button
sequences reproduced for interoperability and research purposes — see
[NOTICE](NOTICE) for the full attribution and takedown contact point.

## Licence

MIT — see [LICENSE](LICENSE). (The MIT licence covers `pm5keys`'s own
code only; see [NOTICE](NOTICE) for the Concept2 content it bundles.)
