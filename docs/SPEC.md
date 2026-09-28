# WorkoutSpec

`src/pm5keys/spec.py` defines an intermediate representation, the **WorkoutSpec**,
that sits between a free-form Concept2 WOD title/description and the PM5
button-press sequence. `parse_spec(text, machines)` turns text into a
WorkoutSpec dict (or `None` if it cannot parse the text with confidence).
A later bead compiles a WorkoutSpec into PM5 keys, so the spec must carry
everything the PM5 monitor needs to be programmed for the workout, and
nothing else.

## Schema

```
{
  "machine": "rower" | "skierg" | "bikeerg" | "all",
  "kind": "single_distance" | "single_time" | "single_calorie"
        | "intervals_distance" | "intervals_time" | "intervals_calorie"
        | "intervals_variable",

  # singles and FIXED intervals (kind != intervals_variable):
  "work": {"distance_m": int} | {"time_s": int} | {"calories": int},

  # FIXED intervals only (kind starts with "intervals_", not "intervals_variable"):
  "rest_s": int,   # >= 0
  "count": int,    # >= 2

  # VARIABLE intervals only (kind == "intervals_variable"):
  "intervals": [
    {"work": {...}, "rest_s": int},   # >= 1 entries
    ...
  ],

  "notes": str   # free text not captured elsewhere; may be ""
}
```

`validate_spec(spec)` (in `src/pm5keys/spec.py`) enforces this shape and raises
`ValueError` on any violation. It is also exposed as the `SCHEMA` constant
for documentation purposes.

Rules:

- **Fixed vs. variable intervals.** A workout is `intervals_variable` only
  when the work amount or unit differs between segments, or the text
  gives per-segment work explicitly (e.g. a pyramid or ladder). A
  workout where every interval has identical work and rest is one of
  the fixed `intervals_*` kinds instead (`work` + `rest_s` + `count`,
  no `intervals` list).
- **`work` has exactly one key** among `distance_m`, `time_s`,
  `calories` — never more than one, never zero, for any place `work`
  appears (top-level or inside an `intervals` entry).
- **Trailing rest.** `rest_s >= 0` everywhere, but `validate_spec`
  forbids `rest_s == 0` on any `intervals_variable` entry that is *not*
  the last one in the list — a zero mid-sequence would be
  indistinguishable from "no rest recorded", and the parser never
  emits it. Only the final interval (or the shared `rest_s` of a fixed
  interval set, which genuinely can be 0) may be 0.
- **"Equal work and rest" ladders** (e.g. Concept2's `1:00, 1:30, ...,
  4:00 - equal work and rest`) are `intervals_variable` where each
  interval's `rest_s` equals its own work duration (except the last,
  which is 0).
- **No leg-count cap in the spec itself.** `validate_spec` places no
  limit on the length of an `intervals_variable` spec's `intervals`
  list — the parser (`_match_variable_chain`, `_match_session`, and the
  ladder/pyramid matchers) is allowed to describe an arbitrarily long
  workout. The 50-leg cap is enforced only where a spec is *compiled*
  to PM5 keys (`compile_keys`), since that's a hardware limit of the
  target monitor's Variable-interval screen, not a property of the
  workout description itself; see `docs/pm5-model.md` for the
  compile-time error message.
- **`notes`** carries framing text the spec doesn't otherwise capture
  (e.g. "time trial", "as fast as you can", "for time", challenge
  blurbs) — currently `parse_spec` always sets `notes` to `""`, since
  none of that framing changes what buttons get pressed; the field
  exists so a future parser/LLM-fallback path can populate it without
  a schema change.

## BikeErg overrides

Several Concept2 WOD pages give the same workout shape for RowErg/SkiErg
and BikeErg, but specify a *different distance* for BikeErg (typically
2x the RowErg/SkiErg distance, though not always exactly — the raw
override text is always used verbatim, never computed). `parse_spec`
only looks for and applies an override when `machines == "BikeErg"`.
Spellings seen in the corpus, all handled:

- `(BikeErg: 1000m)`, `(BikeErg:2000m)` — single value, parenthetical.
- `(BikeErg: 1500m pieces)` — single value with trailing word, parenthetical.
- `(BikeErg: 12 x 500m)` — single value restated with the (unchanged)
  interval count; only the distance is a single-value override.
- `(BikeErg: 1K, 2K, 1K, 2K, 1K)` — comma-separated **positional list**,
  one override per work interval, in order, unit given on every part.
- `(BikeErg: 4000/3000/2000/1000m)` — slash-separated **positional
  list**, unit given once on the *last* part only; that unit is applied
  to every part in the list.
- `(6666m for BikeErg)` — single value, inline "N for BikeErg" form.
- `Note: for BikeErg, distance is 1000 meters` — single value, sentence form.
- `(BikeErg: 4,046m)` — single value with a thousands separator (the
  comma here is *not* a list separator; a bare `fullmatch` against a
  single number+unit is tried before falling back to list-splitting).
  The comma/slash list splitter treats a separator as a thousands
  separator, not a list delimiter, when it is immediately followed by
  exactly three digits and a word boundary (e.g. the `,000` in
  `10,000m`), so `(BikeErg: 10,000m)` is one value, not two.

Application rules:

- A **single-value** override replaces every distance-typed work amount
  in the spec (every fixed interval's shared `work`, or every distance
  leg of an `intervals_variable` spec).
- A **positional-list** override must have exactly as many values as
  there are *distance-typed* legs in the spec; each value replaces the
  corresponding distance leg in order. Non-distance legs (e.g. a mixed
  distance+time `intervals_variable` spec) are left untouched.
- If the override value count doesn't match the number of distance legs
  needing an override, or the base work isn't distance-based at all,
  the override is not applied to that piece (never guess: if the base
  workout's `work` key already isn't `distance_m`, the override is
  silently inapplicable, since a workout carrying a BikeErg override in
  this corpus is always itself a distance workout).
- **Malformed overrides never guess.** If the text contains a
  `(BikeErg: ...)` / `Note: for BikeErg...` aside at all but it cannot
  be parsed into a clean single value or a fully-parseable positional
  list (e.g. one part of a comma/slash list isn't a distance token),
  `_extract_bikeerg_override` returns `None` *and* `parse_spec` treats
  the entire row as unparsed — it never silently falls back to the
  un-overridden RowErg/SkiErg distance, since that would misreport the
  BikeErg-specific workout.

## Pattern list (with one example each)

All examples below are the `title + '\n' + description` text
`parse_spec` is normally called with (title parsed first, description as
fallback for anything the title omits — usually rest and count).

| Pattern | Example |
|---|---|
| `N x DIST, REST minutes rest` | `8 x 500m, 2 minutes rest` |
| `N x TIME / REST easy` (min work) | `10 x 1 min / 1 min easy` |
| `N x M:SS / REST seconds easy` (m:ss work) | `10 x 2:30 / 30 seconds easy` |
| `N x Ns work, Ns rest` (seconds both sides) | `20 x 45s work, 45s rest` |
| `N X Cal Cals with REST minute easy` | `12 X 25 Cals with 1 minute easy` |
| `N x WORK/:SS rest` (bare colon-seconds rest) | `10 x 20 calories/:20 rest` |
| Minute pyramid, slash-separated | `1/3/5/3/1 minutes with 2 minutes rest` |
| Minute pyramid, comma-separated + "pyramid" | `1 min, 2 min, 3 min, 4 min, 3 min, 2 min, 1 min pyramid / 1 min easy` |
| "Intervals of a/b/c minutes with N minutes rest" | `Intervals of 6/3/3/1/1/1 minutes with 2 minutes rest.` |
| Distance ladder, slash-separated, word-number rest | `2000/1500/1000/500m with three minutes rest` |
| Distance ladder, unit on every segment | `500m/1000m/500m/1000m/500m with two minutes rest.` |
| Calorie ladder, slash-separated | `10/20/30/40/50/60 Calories. 1 minute rest between intervals.` |
| Calorie ladder, dash-separated, descending | `50 - 40 - 30 - 20 - 10 Cals with 2 minutes easy` |
| Single distance | `2000m` |
| Single time | `30 minutes` |
| Single calorie | `250 Calories` |
| Time trial / "as fast as you can" / "for time" (single, framing to notes) | `5000m time trial` |
| Variable rest chain, slash-separated | `2000m/3 minutes rest/1000m/2 minutes rest/500m` |
| Variable rest chain, comma-separated, mixed units | `3000m, 3 minutes rest, 10 minutes work` |
| Variable rest chain, time legs with qualifiers (`work`/`hard`/`easy`/`light`/`steady`/`on`/`warm-up`/`cool-down`/`row` on work legs, a required rest cue on rest legs) | `6 minutes easy, 1 minute rest, 1 minute hard, 1 minute rest, 3 minutes easy` (longer 12-leg version in [docs/pm5-model.md](pm5-model.md#session-workouts-fold-into-one-variable-interval-spec)) |
| Session: `[warm-up], N x WORK / REST, [cool-down]` | `7 min warm-up, 10 x 1 min hard / 1 min light, 3 min cool-down` |
| Session, then-chained sets (each `then`/`,`/`;`/`followed by` between sets is a genuine second set, not a restatement) | `4 x 500m / 1 min rest, then 4 x 250m / 30 sec rest` |
| "Equal work and rest" ladder | `1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and rest.` |
| Title omits rest, description supplies it | title `5 x 1000m`, description `5 x 1000m with 20 seconds rest` |
| BikeErg override (see above) | `(BikeErg: 1000m)` |

## Things left as `None` (deliberately unhandled)

- **Tabata-style nested repeats** (`Triple Tabata`: "8 sets of ... Repeat
  the 8 sets. Rest for 4 minutes. Repeat the 8 sets.") — an outer
  repeat-count wrapping an inner interval block has no representation in
  this schema (`intervals`/`count` are flat, one level).
- **Rate/cadence-change workouts** ("with rate changes", "different
  stroke rates or cadence") — the PM5 doesn't take stroke-rate targets
  as part of the button sequence in the way the site describes them
  (per-machine, per-segment rate tables); nothing in the schema
  represents a target rate, and guessing which segment gets which rate
  would be exactly the kind of guess this parser refuses to make.
- **"N rounds of M x ..." nested repeats** (`2 rounds of 16 x 20 seconds
  work and 10 seconds rest`) — same flat-schema limitation as Tabata:
  the rule parser (`src/pm5keys/spec.py`) leaves these unparsed and
  returns `None`. This is a genuine *nested* repeat (an outer round
  count wrapping an inner set), not the flat `[warm-up], SET (,
  SET)*, [cool-down]` session shape the rules parser does handle (see
  the pattern table above) — a session's sets are siblings, never
  wrapped in an outer repeat count. The LLM extractor
  (`src/pm5keys/llm/`) does not have this limitation — its prompt
  instructs it to unroll nested rounds/sets into a single flat
  `intervals_variable` list, one entry per interval leg across all
  rounds, with the between-rounds rest placed on the last leg of each
  round.
- **A single distance explicitly "split into" unequal, no-rest
  sub-intervals** (`4,024m ... split into three intervals
  1000m/2024m/1000m ... no rest`) — this is scored as one continuous
  piece with intermediate splits for time, not as three separate
  worked pieces; representing it as `intervals_variable` with
  `rest_s: 0` throughout would be indistinguishable from "no interval
  structure at all" once compiled to PM5 keys, and would misrepresent
  the workout as an actual multi-piece interval set.

## Never-guess: leftover-cue guard

Every matcher in `_MATCHERS` is written for a specific phrasing; text that
doesn't cleanly match any of them can still contain a stray number that
`_match_single` would otherwise happily turn into a `single_*` spec — the
wrong answer, since the text clearly describes something the parser
couldn't fully capture (an interval structure, a chained sequence of
pieces, etc.). `parse_spec` guards against this after a matcher succeeds,
by calling `_leftover_cue_guard(spec["kind"], clean_text)` on the
BikeErg-stripped text; if it returns `True`, `parse_spec` discards the
spec and returns `None` instead.

Two families of cue are checked:

- **Count cue** — `N x`/`N rounds`/`N sets`/`N reps`/`N intervals`/`N
  pieces`/`N times` (digits or a spelled-out word number), or plural
  shorthand like `500s`/`ten 500s` — signals a repeated/interval
  structure. Checked over the whole text.
- **Rest/chaining cue word** — `rest`, `easy`, `off`, `recovery`,
  `recover`, `light`, `between`, `then`, `followed by`, `on/off`,
  `warmup`, `warm up`, `cool down`. For `single_*` results, checked
  **sentence-scoped** (see below), not over the whole text.

The rule differs by the kind the matcher actually produced, because each
kind legitimately consumes some of these cues as part of its own,
correctly-matched phrasing:

- **`single_*`**: disqualified by any count cue anywhere in the text, or
  by any single **sentence** (text split on `. ! ? \n`) that
  disqualifies it. A sentence disqualifies a single result if either:
  - it contains a rest/chaining cue word *and* a number+unit work token
    (metres — incl. `k` thousands, minutes, seconds, calories, or
    `m:ss`) — e.g. `500m then 1000m` (`then` + two work tokens in one
    sentence), `1000m, rest, 1000m`, `30 minutes on, 30 minutes off`,
    `5k with a 2k warmup`, `2000m followed by 1000m`, `2000m, 3 minutes
    rest, 1000m`, `row 5000m, then ski 5000m` — a lone cue word is only
    disqualifying when it shares a sentence with a real work token, so
    "Then enter your result in the Online Ranking..." (no work token in
    that sentence) and "...taking place **between** March 6-10, 2024"
    (no work token in that sentence either) both parse fine as singles;
    or
  - it contains **two or more** number+unit work tokens, regardless of
    cue words — e.g. `row 5000m, then ski 5000m`, `2000m followed by
    1000m` (also caught this way, independent of the "then"/"followed
    by" cue).

  **Date-context exclusion for "between".** "between" does not count as
  a cue word when it introduces a date/event window rather than a rest
  duration: `between now and <...>`, `between <weekday>`, or `between
  <month name>`. This is what lets "...ski 1000m **between** now and
  Sunday" and "...taking place **between** March 6-10, 2024" parse as
  singles even though "1000m"/no work token respectively shares the
  sentence with "between" — the corpus has both an event-note sentence
  with a work token in it (`ski 1000m between now and Sunday`, excluded
  by the `between now and` guard) and one without (`taking place
  between March 6-10, 2024`, excluded because the sentence has no
  work token at all).
- **Fixed `intervals_*`** (`intervals_distance`/`intervals_time`/
  `intervals_calorie`): allowed as long as no outer-repeat cue (`N
  rounds/sets of`) remains that isn't a restatement of the *same* count
  already captured via an `N x ...` match in the text (titles and
  descriptions in the corpus often restate the same workout twice, e.g.
  title `20 x 45s work, 45s rest` / description `20 rounds of 45 seconds
  work followed by 45 seconds rest` — same `20`, not a nested repeat),
  and no `then`/`followed by` chaining cue remains once the legitimate
  "`... followed by DURATION rest-word`" phrasing (e.g. "`followed by 2
  minutes rest`") is discounted. The same sentence-scoped check also
  covers `warm-up`/`cool-down` (`warm-up`, `warm up`, `warmup`,
  `cool-down`, `cool down`, `cooldown`) alongside `then`: any of these,
  sharing a sentence with a number+unit work token, disqualifies — e.g.
  `8 x 500m, 2 minutes rest and a light cool down jog` is left
  unparsed, since the fixed matcher only captured the `8 x 500m, 2
  minutes rest` piece and the sentence-scoped cool-down mention signals
  an extra leg it didn't.
- **`intervals_variable`**: allowed as long as no outer-repeat (`N
  rounds/sets of`) cue remains — a variable-interval description
  legitimately restates its own piece count in prose (e.g. "Seven
  intervals in a pyramid of 1-2-3-4-3-2-1 minutes..."). The same
  sentence-scoped `warm-up`/`cool-down` leftover check as above also
  applies here (narrower: no bare `then`, since a variable result's own
  ladder/pyramid/chain matchers routinely accept a prose restatement
  like "... then 1000m, then 500m." on the description line) — *except*
  for a result that came from `_match_variable_chain` or `_match_session`
  themselves (see below), which skip this generic check because their
  own full-consumption rule already covers the same ground more
  precisely.

**Self-guarded matchers.** `_match_variable_chain` (the generalized
comma/slash chain matcher, pm5-7bk.1) and `_match_session` (the
`[warm-up], SET (, SET)*, [cool-down]` session matcher, pm5-7bk.3) each
enforce their own full-text-consumption rule instead of relying on the
generic sentence-scoped leftover-cue check above:

- **Chain matcher (restatement shape).** The chain itself must be a
  whole physical line (`^...$`, optionally followed by a trailing
  period) — nothing on that line may sit outside it. Text on *other*
  lines (title vs. description) is accepted only in "restatement
  shape": no outer-repeat cue (`N rounds/sets of`) anywhere outside the
  chain; the first work mention outside the chain is either at the very
  start of the text, right after sentence-ending punctuation, or right
  after a bare article (`a`/`an`/`the`); and every number+unit mention
  outside the chain, taken in order, must be an in-order subsequence of
  the chain's own leg values (each used at most once) — a mention that
  repeats a chain value out of order, or introduces a value the chain
  never had, rejects. E.g. `2000m, 3 minutes rest, 1000m` as the title
  with `A 2000m piece with 3 minutes rest, then a 1000m piece.` as the
  description restates the chain in order and parses; the same title
  with `Then do another 1000m for good measure.` as the description
  introduces a mention the chain doesn't account for and is rejected.
- **Session matcher (full-segment requirement).** The whole text is
  split into segments (on `,`, `;`, newline, `then`, `and then`,
  `followed by`); every segment must classify as the (optional)
  warm-up, a SET, or the (optional) cool-down, in that order, or the
  entire match fails — there is no partial session. E.g. `7 min
  warm-up, 10 x 1 min hard / 1 min light, but stretch after` fails
  outright, because the trailing segment is neither a valid SET nor a
  valid cool-down.

Reproductions (previously mis-parsed as `single_distance`, now `None`):

- `6 rounds of 500m, easy 90 seconds between each`
- `2000m with 3 minutes rest then 1000m`
- `500m then 1000m`
- `1000m, rest, 1000m`
- `30 minutes on, 30 minutes off`
- `5k with a 2k warmup`
- `2000m followed by 1000m`
- `2000m, 3 minutes rest, 1000m` (unparsed, or a correct variable ladder
  — never a single_distance guess)
- `row 5000m, then ski 5000m`
- `3 sets of 4 x 250m with 45 seconds off`
- `5 x 500m`
- `8 x 500m, 2 minutes rest and a light cool down jog` (fixed-interval
  leftover cool-down cue)
- `7 min warm-up, 10 x 1 min hard / 1 min light, but stretch after`
  (session matcher's trailing segment doesn't classify)

Time-trial and event-note framing is unaffected: `5000m time trial`,
`30 minutes`, `250 Calories`, and `1000m for the 2024 World Rowing
Virtual Indoor Sprints` (which contains a lone "between" in a sentence
with no work token) all still parse as singles. `2000m easy` (cue word
+ work token in the same sentence, so it disqualifies under this rule)
is treated as an acceptable edge case either way — not present in the
corpus.

## Worked examples

**1. Fixed distance intervals**
Input: `8 x 500m, 2 minutes rest` / `8 x 500m intervals with 2 minutes rest.`
```json
{
  "machine": "all",
  "kind": "intervals_distance",
  "work": {"distance_m": 500},
  "rest_s": 120,
  "count": 8,
  "notes": ""
}
```

**2. Fixed time intervals, m:ss work**
Input: `10 x 2:30 / 30 seconds easy` / `10 work intervals of 2 minutes and 30 seconds, with 30 seconds recovery between each interval.`
```json
{
  "machine": "all",
  "kind": "intervals_time",
  "work": {"time_s": 150},
  "rest_s": 30,
  "count": 10,
  "notes": ""
}
```

**3. Minute pyramid (variable intervals)**
Input: `1/3/5/3/1 minutes with 2 minutes rest` / `Intervals of 1 minute, 3 minutes, 5 minutes, 3 minutes and 1 minute. 2 minutes light between the work intervals.`
```json
{
  "machine": "all",
  "kind": "intervals_variable",
  "intervals": [
    {"work": {"time_s": 60}, "rest_s": 120},
    {"work": {"time_s": 180}, "rest_s": 120},
    {"work": {"time_s": 300}, "rest_s": 120},
    {"work": {"time_s": 180}, "rest_s": 120},
    {"work": {"time_s": 60}, "rest_s": 0}
  ],
  "notes": ""
}
```

**4. Single distance, time-trial framing**
Input: `30 minute time trial` / `Do a 30 minute time trial, going for your personal best.`
```json
{
  "machine": "all",
  "kind": "single_time",
  "work": {"time_s": 1800},
  "notes": ""
}
```

**5. BikeErg positional-list override**
Input (machines="BikeErg"): `500m/1000m/500m/1000m/500m with two minutes rest.` / `Intervals of 500m, 1000m, 500m, 1000m, 500m with two minutes rest between each interval. (BikeErg: 1K, 2K, 1K, 2K, 1K)`
```json
{
  "machine": "bikeerg",
  "kind": "intervals_variable",
  "intervals": [
    {"work": {"distance_m": 1000}, "rest_s": 120},
    {"work": {"distance_m": 2000}, "rest_s": 120},
    {"work": {"distance_m": 1000}, "rest_s": 120},
    {"work": {"distance_m": 2000}, "rest_s": 120},
    {"work": {"distance_m": 1000}, "rest_s": 0}
  ],
  "notes": ""
}
```

**6. Variable-rest chain (mixed distance and time legs)**
Input (machines="BikeErg"): `3000m, 3 minutes rest, 10 minutes work` / `A 3000m work interval, followed by 3 minutes rest. Then a 10 minute work interval. (BikeErg: 6000m)`
```json
{
  "machine": "bikeerg",
  "kind": "intervals_variable",
  "intervals": [
    {"work": {"distance_m": 6000}, "rest_s": 180},
    {"work": {"time_s": 600}, "rest_s": 0}
  ],
  "notes": ""
}
```
Note the BikeErg override (`6000m`) is applied only to the distance leg;
the `10 minutes work` leg is untouched.

## CLI

```
python -m pm5keys.spec "<text>" [--machines X]
    Parse a single piece of text and print the resulting spec as JSON,
    or exit 2 and print 'unparsed' to stderr.

python -m pm5keys.spec --coverage data/dataset_unique.jsonl
    Run parse_spec over every row (title + '\n' + description, using
    the row's machines), print parsed/unparsed counts (both weighted
    by distinct row and by the row's `count` field), and write:
      data/reports/spec_unparsed.md -- every unparsed row (count,
                                 machines, title, description)
      data/spec_parsed.jsonl -- {title, description, machines, pm5,
                                 spec} for every parsed row, committed
                                 for the next bead (spec -> PM5 keys)
                                 to consume.
```
