#!/usr/bin/env python3
"""WorkoutSpec: a machine-parseable intermediate representation between a
free-form Concept2 WOD description and a PM5 button-press sequence.

parse_spec(text, machines) turns a title/description pair into a
WorkoutSpec dict, or returns None when the text cannot be parsed with
confidence (never guesses). See docs/SPEC.md for the schema, the pattern
list this parser was built against, and worked examples.

CLI:
    python3 -m pm5keys.spec "<text>" [--machines X]
        Parse a single piece of text and print the resulting spec as
        JSON, or exit 2 and print 'unparsed'.

    python3 -m pm5keys.spec --coverage dataset_unique.jsonl [--parsed PATH] [--unparsed PATH]
        Run parse_spec over every row of a dataset_unique.jsonl-shaped
        file (using title + '\\n' + description as the text), print
        parsed/unparsed counts (by row and weighted by count), and
        write the parsed/unparsed reports (`--parsed`, default
        `data/spec_parsed.jsonl`; `--unparsed`, default
        `data/reports/spec_unparsed.md`; both relative to the current
        working directory -- this module never writes next to its own
        file).
"""

from __future__ import annotations

import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

MACHINES = {"rower", "skierg", "bikeerg", "all"}
KINDS = {
    "single_distance",
    "single_time",
    "single_calorie",
    "intervals_distance",
    "intervals_time",
    "intervals_calorie",
    "intervals_variable",
}

# Documented schema, mirrored in docs/SPEC.md. Used by validate_spec.
SCHEMA = {
    "machine": "one of: rower, skierg, bikeerg, all",
    "kind": "one of: " + ", ".join(sorted(KINDS)),
    "work": "dict with exactly one of distance_m (int), time_s (int), "
    "calories (int) -- required for singles and fixed intervals; "
    "omitted for intervals_variable",
    "rest_s": "int >= 0 -- required for fixed intervals; omitted for "
    "singles and intervals_variable",
    "count": "int >= 2 -- required for fixed intervals (kind starting "
    "with 'intervals_' other than intervals_variable)",
    "intervals": "list of {work: {...}, rest_s: int}, len >= 1 -- "
    "required for intervals_variable only; rest_s of the last "
    "interval may be 0 (no trailing rest)",
    "notes": "free text not captured elsewhere (time-trial framing, "
    "challenge blurbs, etc.); always present, may be ''",
}


def validate_spec(spec: dict) -> None:
    """Raise ValueError if spec does not conform to the WorkoutSpec schema."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")

    machine = spec.get("machine")
    if machine not in MACHINES:
        raise ValueError(f"invalid machine: {machine!r}")

    kind = spec.get("kind")
    if kind not in KINDS:
        raise ValueError(f"invalid kind: {kind!r}")

    notes = spec.get("notes")
    if not isinstance(notes, str):
        raise ValueError("notes must be a str (may be '')")

    def _check_work(work, where):
        if not isinstance(work, dict):
            raise ValueError(f"{where}: work must be a dict")
        keys = [k for k in ("distance_m", "time_s", "calories") if k in work]
        if len(keys) != 1:
            raise ValueError(
                f"{where}: work must have exactly one of distance_m/time_s/"
                f"calories, got {sorted(work.keys())}"
            )
        val = work[keys[0]]
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            raise ValueError(f"{where}: work.{keys[0]} must be a positive int")

    if kind == "intervals_variable":
        if "work" in spec or "rest_s" in spec or "count" in spec:
            raise ValueError(
                "intervals_variable must not carry work/rest_s/count (use intervals instead)"
            )
        intervals = spec.get("intervals")
        if not isinstance(intervals, list) or len(intervals) == 0:
            raise ValueError("intervals_variable requires a non-empty intervals list")
        for i, iv in enumerate(intervals):
            if not isinstance(iv, dict):
                raise ValueError(f"intervals[{i}] must be a dict")
            _check_work(iv.get("work"), f"intervals[{i}]")
            rest_s = iv.get("rest_s")
            if not isinstance(rest_s, int) or isinstance(rest_s, bool) or rest_s < 0:
                raise ValueError(f"intervals[{i}].rest_s must be an int >= 0")
            if i < len(intervals) - 1 and rest_s == 0:
                # Only the last interval may have rest_s == 0.
                raise ValueError(f"intervals[{i}].rest_s == 0 but is not the last interval")
    else:
        if "intervals" in spec:
            raise ValueError(f"{kind} must not carry an intervals list")
        _check_work(spec.get("work"), "work")
        if kind.startswith("intervals_"):
            rest_s = spec.get("rest_s")
            if not isinstance(rest_s, int) or isinstance(rest_s, bool) or rest_s < 0:
                raise ValueError("rest_s must be an int >= 0")
            count = spec.get("count")
            if not isinstance(count, int) or isinstance(count, bool) or count < 2:
                raise ValueError("count must be an int >= 2 for fixed intervals")
        else:
            if "rest_s" in spec:
                raise ValueError(f"{kind} must not carry rest_s")
            if "count" in spec:
                raise ValueError(f"{kind} must not carry count")


# ---------------------------------------------------------------------------
# Tokenising helpers
# ---------------------------------------------------------------------------

_WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

# A count/number token: digits (with optional thousands separators) or a
# spelled-out word one..twenty.
_NUM_RE = r"(?:\d[\d,]*|" + "|".join(_WORD_NUMBERS) + r")"


def _to_int(num_str: str) -> int:
    """Parse a digit string (with optional commas) or word number to int."""
    s = num_str.strip().lower()
    if s in _WORD_NUMBERS:
        return _WORD_NUMBERS[s]
    return int(s.replace(",", ""))


def _mmss_to_seconds(mm: str, ss: str) -> int:
    return int(mm) * 60 + int(ss)


# Unit alternations, case-insensitive (applied with re.IGNORECASE).
_MIN_UNIT = r"(?:min(?:ute)?s?)"
_SEC_UNIT = r"(?:sec(?:ond)?s?|s)"
_CAL_UNIT = r"(?:cal(?:orie)?s?)"


def _parse_distance_token(num: str, unit: str) -> int:
    """num+unit -> metres. Handles plain metres and 'K' (thousands)."""
    if unit.lower() == "k":
        return int(round(_to_int(num) * 1000))
    return _to_int(num)


# ---------------------------------------------------------------------------
# BikeErg overrides
# ---------------------------------------------------------------------------

# Matches the various "(BikeErg: ...)" / "Note: for BikeErg, distance is
# ... meters" spellings seen in the corpus, capturing the raw override
# text after the colon/'is'.
_BIKEERG_PAREN_RE = re.compile(r"\(\s*(?:for\s+)?bikeerg\s*:?\s*([^)]*)\)", re.IGNORECASE)
_BIKEERG_NOTE_RE = re.compile(
    r"note:\s*for\s+bikeerg,\s*distance\s+is\s+([\d,]+)\s*met(?:er|re)s?",
    re.IGNORECASE,
)
_BIKEERG_INLINE_RE = re.compile(r"\(([\d,]+)\s*m\s+for\s+bikeerg\)", re.IGNORECASE)

_DIST_NUM_UNIT_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(k\b|m\b|meters?\b|meter\b)\b", re.IGNORECASE)


def _extract_bikeerg_override(text: str):
    """Return a list of override distances in metres (positional, one per
    work interval) if the text contains a recognised BikeErg override,
    else None. A single-value override applies to every interval."""
    m = _BIKEERG_NOTE_RE.search(text)
    if m:
        return [int(m.group(1).replace(",", ""))]

    m = _BIKEERG_INLINE_RE.search(text)
    if m:
        return [int(m.group(1).replace(",", ""))]

    m = _BIKEERG_PAREN_RE.search(text)
    if m:
        inner = m.group(1).strip()
        # Try a single value first, e.g. "10,000m" (comma = thousands
        # separator, not a list separator) or "4,046m".
        single = _DIST_NUM_UNIT_RE.fullmatch(inner)
        if single:
            return [_parse_distance_token(single.group(1), single.group(2))]

        # "12 x 500m" -- restates the interval count with a single
        # overridden distance (not a positional list); the count is
        # already carried by the base spec, so only the distance value
        # is a single-value override.
        n_x_single = re.fullmatch(
            r"" + _NUM_RE + r"\s*[xX]\s*(" + _DIST_NUM_UNIT_RE.pattern + r")",
            inner,
            re.IGNORECASE,
        )
        if n_x_single:
            dm = _DIST_NUM_UNIT_RE.fullmatch(n_x_single.group(1))
            return [_parse_distance_token(dm.group(1), dm.group(2))]

        # "1500m pieces" / "2000m pieces" -- a single distance value
        # followed only by trailing descriptive word(s) with no further
        # digits anywhere, so it is unambiguously one value and must not
        # be routed through the positional-list splitter below (which
        # would treat "pieces" as a second, unparseable part).
        single_plus_words = re.fullmatch(
            r"(" + _DIST_NUM_UNIT_RE.pattern + r")\s*[a-zA-Z\s]*",
            inner,
            re.IGNORECASE,
        )
        if single_plus_words:
            dm = _DIST_NUM_UNIT_RE.fullmatch(single_plus_words.group(1))
            if dm:
                return [_parse_distance_token(dm.group(1), dm.group(2))]

        # Otherwise it's a positional list. Two spellings appear in the
        # corpus:
        #   - comma-separated, unit on every part: "1K, 2K, 1K, 2K, 1K",
        #     "1000m, 2000m"
        #   - slash-separated, unit given once on the last part only:
        #     "4000/3000/2000/1000m", "4000/2000/1000m"
        # Split on commas or slashes that are NOT thousands separators
        # (not immediately followed by exactly 3 digits then a word
        # boundary, i.e. a real thousands group like the ",000" in
        # "10,000m").
        raw_parts = [p.strip() for p in re.split(r"[,/]\s*(?!\d{3}\b)", inner) if p.strip()]
        if not raw_parts:
            return None

        # If only the last part carries a unit and every earlier part is
        # a bare number, the trailing unit applies to all of them (the
        # slash-separated spelling above).
        last_match = _DIST_NUM_UNIT_RE.fullmatch(raw_parts[-1])
        bare_number_re = re.compile(r"^[\d,]+(?:\.\d+)?$")
        earlier_bare = all(bare_number_re.fullmatch(p) for p in raw_parts[:-1])
        if last_match and earlier_bare and len(raw_parts) > 1:
            unit = last_match.group(2)
            values = [_parse_distance_token(p, unit) for p in raw_parts[:-1]]
            values.append(_parse_distance_token(last_match.group(1), unit))
            return values

        values = []
        for p in raw_parts:
            pm = _DIST_NUM_UNIT_RE.fullmatch(p)
            if not pm:
                # Never guess: a part that doesn't cleanly parse as a
                # single distance means the whole override is malformed.
                return None
            values.append(_parse_distance_token(pm.group(1), pm.group(2)))
        if values:
            return values

    return None


def _strip_parenthetical_and_notes(text: str) -> str:
    """Drop '(BikeErg: ...)'/'Note: for BikeErg...' asides and any
    '*'-prefixed trailing blurb, for cleaner pattern matching. Kept text
    (title + description) is otherwise untouched."""
    text = _BIKEERG_PAREN_RE.sub(" ", text)
    text = _BIKEERG_INLINE_RE.sub(" ", text)
    text = _BIKEERG_NOTE_RE.sub(" ", text)
    return text


# ---------------------------------------------------------------------------
# Machine mapping
# ---------------------------------------------------------------------------


def _map_machine(machines: str | None) -> str:
    if machines is None:
        return "all"
    if machines == "BikeErg":
        return "bikeerg"
    if machines == "RowErg and SkiErg":
        return "rower"
    if machines == "All Machines":
        return "all"
    raise ValueError(f"unknown machines value: {machines!r}")


# ---------------------------------------------------------------------------
# Work-unit parsing: turn a "work chunk" string into a work dict
# ---------------------------------------------------------------------------

_MMSS_RE = re.compile(r"^\s*(\d{1,3}):(\d{2})\s*$")
_DIST_RE = re.compile(r"^\s*([\d,]+(?:\.\d+)?)\s*(k\b|m\b|meters?\b|meter\b)\s*$", re.IGNORECASE)
_TIME_RE = re.compile(r"^\s*(" + _NUM_RE + r")\s*" + _MIN_UNIT + r"\s*$", re.IGNORECASE)
_TIME_SEC_RE = re.compile(r"^\s*(" + _NUM_RE + r")\s*" + _SEC_UNIT + r"\s*$", re.IGNORECASE)
_CAL_RE = re.compile(r"^\s*(" + _NUM_RE + r")\s*" + _CAL_UNIT + r"\s*$", re.IGNORECASE)


def _parse_work_chunk(chunk: str):
    """Parse a single work-amount chunk (e.g. '500m', '2:30', '3 minutes',
    '45s', '25 Cals') into a work dict, or None if unrecognised."""
    chunk = chunk.strip()
    m = _MMSS_RE.match(chunk)
    if m:
        return {"time_s": _mmss_to_seconds(m.group(1), m.group(2))}
    m = _DIST_RE.match(chunk)
    if m:
        return {"distance_m": _parse_distance_token(m.group(1), m.group(2))}
    m = _TIME_RE.match(chunk)
    if m:
        return {"time_s": _to_int(m.group(1)) * 60}
    m = _TIME_SEC_RE.match(chunk)
    if m:
        return {"time_s": _to_int(m.group(1))}
    m = _CAL_RE.match(chunk)
    if m:
        return {"calories": _to_int(m.group(1))}
    return None


# ---------------------------------------------------------------------------
# Rest parsing
# ---------------------------------------------------------------------------


def _duration_words_to_seconds(num_str: str, unit_str: str) -> int:
    unit_str = unit_str.lower()
    if re.match(_MIN_UNIT, unit_str):
        return _to_int(num_str) * 60
    return _to_int(num_str)


# ---------------------------------------------------------------------------
# Pattern matchers. Each returns a spec dict (without machine/notes
# finalised) or None. Tried in order by parse_spec.
# ---------------------------------------------------------------------------


def _finalize(work_kind_prefix, work, rest_s=None, count=None, intervals=None):
    if intervals is not None:
        return {"kind": "intervals_variable", "intervals": intervals}
    unit = next(iter(work.keys()))
    unit_name = {"distance_m": "distance", "time_s": "time", "calories": "calorie"}[unit]
    if count is None:
        kind = f"single_{unit_name}"
        return {"kind": kind, "work": work}
    kind = f"intervals_{unit_name}"
    return {"kind": kind, "work": work, "rest_s": rest_s, "count": count}


# --- N x WORK, REST patterns -------------------------------------------------

# "N x 500m, 2 minutes rest" / "8 x 1000m, 2 minutes rest" / "N X 25 Cals
# with 1 minute easy" / "N x 1 min / 1 min easy" / "N x 2:30 / 30 seconds
# easy" / "N x 45s work, 45s rest" / "10 x 20 calories/:20 rest"
_N_X_WORK_SEP_REST_RE = re.compile(
    r"("
    + _NUM_RE
    + r")\s*[xX]\s*("
    + r"\d{1,3}:\d{2}"  # mm:ss
    + r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"  # distance
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT  # minutes
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _SEC_UNIT  # seconds
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _CAL_UNIT  # calories
    + r")"
    r"(?:\s*(?:work)?\s*[,/]?\s*("
    + r"\d{1,2}:\d{2}"
    + r"|:\d{1,2}"  # bare colon-prefixed seconds, e.g. ':20'
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _SEC_UNIT
    + r")\s*(?:work,?\s*)?(?:rest|easy|light|recovery)?)?",
    re.IGNORECASE,
)


def _match_n_x_work_rest(text: str):
    """'N x WORK[, /]REST [rest-word]' e.g. '8 x 500m, 2 minutes rest',
    '10 x 1 min / 1 min easy', '10 x 2:30 / 30 seconds easy',
    '20 x 45s work, 45s rest', '10 x 20 calories/:20 rest'."""
    m = _N_X_WORK_SEP_REST_RE.search(text)
    if not m or not m.group(2):
        return None
    count = _to_int(m.group(1))
    work = _parse_work_chunk(m.group(2))
    if work is None:
        return None
    rest_str = m.group(3)
    if rest_str is None:
        return None
    rest_chunk = rest_str.strip()
    bare_colon = re.match(r"^:(\d{1,2})$", rest_chunk)
    if bare_colon:
        rest_s = int(bare_colon.group(1))
    else:
        rest_work = _parse_work_chunk(rest_chunk)
        if rest_work is None or "distance_m" in rest_work or "calories" in rest_work:
            return None
        rest_s = rest_work["time_s"]
    return _finalize(None, work, rest_s=rest_s, count=count)


# "N x 500m" / "8 x 1000m" with count but NO rest in this chunk -- caller
# falls back to searching the rest of the text for a rest spec.
_N_X_WORK_ONLY_RE = re.compile(
    r"("
    + _NUM_RE
    + r")\s*[xX]\s*("
    + r"\d{1,3}:\d{2}"
    + r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _SEC_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _CAL_UNIT
    + r")",
    re.IGNORECASE,
)

# "N X 25 Cals with 1 minute easy" style (count before work, 'with' before
# rest). Handled by _N_X_WORK_SEP_REST_RE already via 'with' not matching
# the separator -- add a dedicated 'with' variant.
_N_X_WORK_WITH_REST_RE = re.compile(
    r"("
    + _NUM_RE
    + r")\s*[xX]\s*("
    + r"[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _SEC_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _CAL_UNIT
    + r")"
    r"\s*with\s*("
    + _NUM_RE
    + r")\s*("
    + _MIN_UNIT
    + r"|"
    + _SEC_UNIT
    + r")\s*(?:easy|light|recovery|rest)?",
    re.IGNORECASE,
)

# Standalone rest clause elsewhere in the text, e.g. "with 20 seconds
# rest", "8 X 1000m with 2 minutes rest", "5 x 1000m with 60 seconds
# rest.".
_STANDALONE_REST_RE = re.compile(
    r"(?:with\s+)?(" + _NUM_RE + r")\s*(" + _MIN_UNIT + r"|" + _SEC_UNIT + r")"
    r"\s*(?:rest|easy|light|recovery)\b",
    re.IGNORECASE,
)

# "N intervals of ... 2 minutes rest between" or "2 minutes light between"
# free-standing rest mention (used as a fallback rest source).
_REST_BETWEEN_RE = re.compile(
    r"(" + _NUM_RE + r")\s*(" + _MIN_UNIT + r"|" + _SEC_UNIT + r")"
    r"\s*(?:of\s+)?(?:rest|light|easy|recovery)?\s*(?:between|in between)",
    re.IGNORECASE,
)


def _find_rest_seconds_anywhere(text: str):
    m = _STANDALONE_REST_RE.search(text)
    if m:
        return _duration_words_to_seconds(m.group(1), m.group(2))
    m = _REST_BETWEEN_RE.search(text)
    if m:
        return _duration_words_to_seconds(m.group(1), m.group(2))
    return None


def _match_n_x_work_with_rest(text: str):
    m = _N_X_WORK_WITH_REST_RE.search(text)
    if not m:
        return None
    count = _to_int(m.group(1))
    work = _parse_work_chunk(m.group(2))
    if work is None:
        return None
    rest_s = _duration_words_to_seconds(m.group(3), m.group(4))
    return _finalize(None, work, rest_s=rest_s, count=count)


def _match_n_x_work_then_fallback_rest(text: str):
    m = _N_X_WORK_ONLY_RE.search(text)
    if not m:
        return None
    count = _to_int(m.group(1))
    work = _parse_work_chunk(m.group(2))
    if work is None:
        return None
    rest_s = _find_rest_seconds_anywhere(text)
    if rest_s is None:
        return None
    return _finalize(None, work, rest_s=rest_s, count=count)


# --- "N rounds/intervals of WORK [work/rest word] REST" ---------------------

_N_ROUNDS_OF_WORK_REST_RE = re.compile(
    r"("
    + _NUM_RE
    + r")\s*(?:rounds?|intervals?)\s+of\s+("
    + _NUM_RE
    + r"\s*"
    + _SEC_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    + r")\s*(?:work)?\s*(?:followed by|and|,)?\s*("
    + _NUM_RE
    + r"\s*"
    + _SEC_UNIT
    + r"|"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r")\s*(?:rest|easy|light|recovery)",
    re.IGNORECASE,
)


def _match_n_rounds_of(text: str):
    m = _N_ROUNDS_OF_WORK_REST_RE.search(text)
    if not m:
        return None
    count = _to_int(m.group(1))
    work = _parse_work_chunk(m.group(2))
    if work is None:
        return None
    rest_work = _parse_work_chunk(m.group(3))
    if rest_work is None or "time_s" not in rest_work:
        return None
    return _finalize(None, work, rest_s=rest_work["time_s"], count=count)


# --- Slash pyramids / ladders: "a/b/c/... minutes with N minutes rest" -----

_SLASH_MIN_WITH_REST_RE = re.compile(
    r"((?:"
    + _NUM_RE
    + r"\s*/\s*)+"
    + _NUM_RE
    + r")\s*"
    + _MIN_UNIT
    + r"\s*with\s*("
    + _NUM_RE
    + r")\s*"
    + _MIN_UNIT
    + r"\s*(?:rest|easy|light|recovery)?",
    re.IGNORECASE,
)

# "Intervals of 6/3/3/1/1/1 minutes with 2 minutes rest."
_INTERVALS_OF_SLASH_MIN_RE = re.compile(
    r"intervals\s+of\s+((?:"
    + _NUM_RE
    + r"\s*/\s*)+"
    + _NUM_RE
    + r")\s*"
    + _MIN_UNIT
    + r"\s*with\s*("
    + _NUM_RE
    + r")\s*"
    + _MIN_UNIT
    + r"\s*(?:rest|easy|light|recovery)?",
    re.IGNORECASE,
)

# Distance ladders: "2000/1500/1000/500m with three minutes rest",
# "500m/1000m/500m/1000m/500m with two minutes rest."
_SLASH_DIST_WITH_REST_RE = re.compile(
    r"((?:[\d,]+(?:\.\d+)?\s*m?\s*/\s*)+[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b))"
    r"\s*with\s*(" + _NUM_RE + r")\s*" + _MIN_UNIT + r"\s*(?:rest|easy|light|recovery)?",
    re.IGNORECASE,
)

# Calorie ladders: "10/20/30/40/50/60 Calories. 1 minute rest between
# intervals.", "50 - 40 - 30 - 20 - 10 Cals with 2 minutes easy",
# "20 - 40 - 60 - 80 - 100 Cal with 2 minutes easy"
_SLASH_OR_DASH_CAL_RE = re.compile(
    r"((?:" + _NUM_RE + r"\s*[/-]\s*)+" + _NUM_RE + r")\s*" + _CAL_UNIT,
    re.IGNORECASE,
)


def _split_numbers(numbers_str: str, sep_re=r"[/]"):
    parts = re.split(sep_re, numbers_str)
    return [_to_int(p.strip()) for p in parts if p.strip()]


def _fixed_or_variable_from_values(values, unit_key, rest_s):
    """values: list of ints in the given unit. If all equal, it's a fixed
    interval set; otherwise intervals_variable with constant rest_s
    between each (rest_s applies to all but possibly none omitted --
    every interval except we still set rest_s on every interval; last
    interval's rest_s is 0 per convention of 'no trailing rest')."""
    if len(values) < 2:
        return None
    if len(set(values)) == 1:
        return _finalize(None, {unit_key: values[0]}, rest_s=rest_s, count=len(values))
    intervals = []
    for i, v in enumerate(values):
        r = rest_s if i < len(values) - 1 else 0
        intervals.append({"work": {unit_key: v}, "rest_s": r})
    return _finalize(None, None, intervals=intervals)


def _match_slash_minutes_with_rest(text: str):
    m = _INTERVALS_OF_SLASH_MIN_RE.search(text) or _SLASH_MIN_WITH_REST_RE.search(text)
    if not m:
        return None
    values = [v * 60 for v in _split_numbers(m.group(1))]
    rest_s = _to_int(m.group(2)) * 60
    return _fixed_or_variable_from_values(values, "time_s", rest_s)


def _match_slash_distance_with_rest(text: str):
    m = _SLASH_DIST_WITH_REST_RE.search(text)
    if not m:
        return None
    numbers_part = m.group(1)
    # Strip trailing unit tokens like 'm' before splitting, e.g.
    # "500m/1000m/500m/1000m/500m" -> ['500','1000','500','1000','500'].
    numbers_part = re.sub(r"(?:k\b|m\b|meters?\b|meter\b)\b", "", numbers_part, flags=re.IGNORECASE)
    values = _split_numbers(numbers_part)
    rest_s = _to_int(m.group(2)) * 60
    return _fixed_or_variable_from_values(values, "distance_m", rest_s)


def _match_slash_or_dash_calories(text: str):
    m = _SLASH_OR_DASH_CAL_RE.search(text)
    if not m:
        return None
    values = _split_numbers(m.group(1), sep_re=r"[/-]")
    rest_s = _find_rest_seconds_anywhere(text)
    if rest_s is None:
        return None
    return _fixed_or_variable_from_values(values, "calories", rest_s)


# --- Equal work and rest: "1:00, 1:30, ..., 4:00 - equal work and rest." ---

_EQUAL_WORK_REST_RE = re.compile(
    r"((?:\d{1,2}:\d{2}\s*,\s*)+\d{1,2}:\d{2})\s*[-–]\s*equal\s+work\s+and\s+rest",
    re.IGNORECASE,
)


def _match_equal_work_and_rest(text: str):
    m = _EQUAL_WORK_REST_RE.search(text)
    if not m:
        return None
    chunks = [c.strip() for c in m.group(1).split(",") if c.strip()]
    seconds = []
    for c in chunks:
        mm = _MMSS_RE.match(c)
        if not mm:
            return None
        seconds.append(_mmss_to_seconds(mm.group(1), mm.group(2)))
    intervals = []
    for i, s in enumerate(seconds):
        r = s if i < len(seconds) - 1 else 0
        intervals.append({"work": {"time_s": s}, "rest_s": r})
    return _finalize(None, None, intervals=intervals)


# --- Variable rest sequences: "2000m/3 minutes rest/1000m/2 minutes
# rest/500m", "3000m, 3 minutes rest, 10 minutes work", and arbitrarily
# long comma- or slash-separated chains of the same shape -------------------

_SEGMENT_SPLIT_RE = re.compile(r"\s*/\s*")
_COMMA_SEGMENT_SPLIT_RE = re.compile(r"\s*,\s*")

# Optional trailing qualifier on a WORK leg -- never changes what the leg
# means, just confirms it (position decides work vs rest).
_WORK_QUALIFIER_ALT = (
    r"(?:warm-up|warm up|warmup|cool-down|cool down|cooldown"
    r"|work|hard|easy|light|steady|on|row)"
)
# Required cue on a REST leg -- a rest-position leg without one of these
# fails the whole chain rather than being guessed at.
_REST_CUE_ALT = r"(?:rest|easy|light|off|recovery|paddle)"

_WORK_QUALIFIER_SUFFIX_RE = re.compile(
    r"^(?P<unit>.*?)\s+\b" + _WORK_QUALIFIER_ALT + r"\b\.?$", re.IGNORECASE
)
_REST_CUE_SUFFIX_RE = re.compile(
    r"^(?P<dur>.*?)\s+\b" + _REST_CUE_ALT + r"\b\.?$", re.IGNORECASE
)
_REST_DURATION_RE = re.compile(
    r"^\s*(?:(\d{1,3}):(\d{2})|:(\d{1,2})|("
    + _NUM_RE
    + r")\s*("
    + _MIN_UNIT
    + r"|"
    + _SEC_UNIT
    + r"))\s*$",
    re.IGNORECASE,
)


def _parse_variable_work_leg(seg: str):
    """Parse a WORK-position leg: any _parse_work_chunk unit, optionally
    followed by a qualifier word/phrase. A leg that isn't a recognised
    unit (once an optional qualifier is stripped) -- including one that
    says rest/off/recovery, none of which are valid qualifiers -- fails."""
    seg = seg.strip()
    if not seg:
        return None
    m = _WORK_QUALIFIER_SUFFIX_RE.match(seg)
    if m:
        unit_text = m.group("unit")
    else:
        unit_text = seg[:-1].rstrip() if seg.endswith(".") else seg
    return _parse_work_chunk(unit_text)


def _parse_variable_rest_leg(seg: str):
    """Parse a REST-position leg: a duration (N min/sec, M:SS, or bare
    :SS) followed by a REQUIRED rest cue. Missing the cue fails the leg
    (and so the whole chain) rather than guessing."""
    seg = seg.strip()
    if not seg:
        return None
    m = _REST_CUE_SUFFIX_RE.match(seg)
    if not m:
        return None
    dm = _REST_DURATION_RE.match(m.group("dur"))
    if not dm:
        return None
    if dm.group(1) is not None:
        return _mmss_to_seconds(dm.group(1), dm.group(2))
    if dm.group(3) is not None:
        return _to_int(dm.group(3))
    return _duration_words_to_seconds(dm.group(4), dm.group(5))


def _try_parse_variable_chain(segments):
    """segments: list of strings alternating work/rest, where rest
    segments carry a required rest cue. Build intervals_variable if it
    strictly alternates work, rest, work, rest, ..., work (odd length,
    >= 3 items, starting and ending with work)."""
    if len(segments) < 3 or len(segments) % 2 == 0:
        return None
    works = []
    rests = []
    for i, seg in enumerate(segments):
        if i % 2 == 0:
            w = _parse_variable_work_leg(seg)
            if w is None:
                return None
            works.append(w)
        else:
            r = _parse_variable_rest_leg(seg)
            if r is None:
                return None
            rests.append(r)
    intervals = []
    for i, w in enumerate(works):
        r = rests[i] if i < len(rests) else 0
        intervals.append({"work": w, "rest_s": r})
    return _finalize(None, None, intervals=intervals)


# Permissive leg shape used only to find candidate chain spans in the
# text: any work unit, optionally followed by a single qualifier-or-cue
# word/phrase (the position-aware, strict checks above decide whether
# each leg is actually valid once the chain is split).
_CHAIN_UNIT_ALT = (
    r"(?:\d{1,3}:\d{2}"  # mm:ss
    r"|:\d{1,2}"  # bare :ss
    r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"  # distance
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT  # N minutes
    + r"|" + _NUM_RE + r"\s*" + _SEC_UNIT  # N seconds
    + r"|" + _NUM_RE + r"\s*" + _CAL_UNIT  # N calories
    + r")"
)
_CHAIN_TRAILER_ALT = (
    r"\b(?:warm-up|warm up|warmup|cool-down|cool down|cooldown"
    r"|work|hard|easy|light|steady|on|row"
    r"|rest|off|recovery|paddle)\b"
)
_CHAIN_LEG_RE_STR = _CHAIN_UNIT_ALT + r"(?:\s+" + _CHAIN_TRAILER_ALT + r")?"

# Full-text consumption, not just "fills a line": parse_spec hands every
# matcher title + "\n" + description as one string, and title/description
# routinely restate each other (title: the bare chain; description: the
# same chain retold in prose, e.g. "3000m, 3 minutes rest, 10 minutes
# work" / "A 3000m work interval, followed by 3 minutes rest. Then a 10
# minute work interval.") -- every other matcher in this module tolerates
# that restatement by matching only the defining fragment and trusting
# _leftover_cue_guard, not by demanding the whole raw text be nothing but
# the match. A literal whole-string fullmatch was tried here first and
# rejects that convention outright (it fails all of the pre-existing
# restatement-style tests, which have narrative descriptions the chain
# pattern itself can never match), so it is not what "full text
# consumption" means for this matcher.
#
# What full consumption DOES need to rule out (the actual bug): a chain
# that only fills ONE LINE while a SIBLING line carries real, distinct
# workout content that was silently dropped -- a leading "3 x" line that
# turns the chain into an outer-repeat count instead, a trailing "then
# 4 x 250m" cool-down/extra block, a bare "then 2000m" leftover leg. The
# fix below keeps the existing per-line anchor (^...$, MULTILINE -- it
# already correctly rejects same-line leading/trailing junk such as
# "then do 500m, 1 minute rest, 500m" or "... and then some") and adds
# THREE checks:
#
#   (a) REPEAT CUE, anywhere outside the matched span: "N x"/"N X"/"N×",
#       "N rounds"/"N sets"/"N times" (N a digit or number-word),
#       "twice", "thrice", "repeat", "rounds of", "sets of". Always
#       rejects, regardless of what N is or whether it matches a chain
#       value -- it means the chain is (or may be) the body of an
#       outer-repeat construct that belongs to a different matcher, or
#       an explicit "do the whole thing again" cue, neither of which
#       this matcher may guess at. This is what makes "3 x\n500m, 1
#       minute rest, 500m", "...\nThen 4 x 250m", "...\n5 rounds",
#       "...\nDo it twice" and "Row 2 rounds\n..." fall through/reject.
#   (b) AMBIGUOUS DUPLICATE CANDIDATE: if this separator kind (comma or
#       slash) finds MORE THAN ONE independent full-line chain candidate
#       anywhere in the text, refuse all of them for that kind rather
#       than picking one. Two identical chain lines back to back ("500m,
#       1 minute rest, 500m" twice) are exactly as consistent with "the
#       same workout, restated" as with "do it twice" -- an outer-repeat
#       meaning this spec has no way to express -- so guessing either
#       reading would be guessing at something we cannot tell apart.
#       Genuine prose restatement is never itself comma/slash-chain
#       shaped, so it never trips this.
#   (c) RESTATEMENT-SHAPE WHITELIST (not a cue-word blacklist -- an
#       open-ended list of "bad" lead-in words is whack-a-mole; this
#       checks the SHAPE a genuine restatement always has instead).
#       Text outside the span is acceptable only if BOTH hold:
#
#       1. LEAD-IN on the first outside WORK mention: find the first
#          unit-bearing token outside the span that is not unambiguously
#          a rest mention (a rest-only cue -- rest/off/recovery/paddle,
#          and not also a work qualifier -- makes a token a rest mention
#          and it is skipped when hunting for this "first" one; see
#          _is_rest_mention/_first_work_mention). Whatever comes right
#          before that first WORK mention, up to the nearest sentence
#          boundary (start of text, after "\n", or after one of ".!?:;")
#          or all the way back to the start of the text if there is no
#          boundary, must be EITHER just whitespace/punctuation, OR end
#          in exactly one bare article word ("a"/"an"/"the") -- what
#          comes before that article does not matter, since a genuine
#          restatement's own earlier content (an already-matched rest
#          mention, "A 2000m interval, followed by three minutes rest.
#          Then a 10 minute work interval." -- the "Then a" before this
#          SECOND leg) is exactly as legitimate as no lead-in at all.
#          Any OTHER word directly before the first work mention (then,
#          next, plus, and, another, afterwards, finish, or literally
#          anything that isn't nothing/punctuation/a single article)
#          rejects -- this is what makes "Finish with 500m", "then 1k",
#          "then 2000m cool down", "then 10 minutes easy", "Then, 500m",
#          "Next - 500m", "Then another 500m", "Afterwards 500m", "Plus
#          500m", "and another 500m" and "Then 1 minute rest and 500m
#          more" all reject, while "...followed by 3 minutes rest
#          before a 10 minute piece" (rest mention cued, first WORK
#          mention preceded only by "a") accepts.
#       2. IN-ORDER SUBSEQUENCE: the chain's own work/rest legs form a
#          token sequence (work1, rest1, work2, rest2, ..., workN;
#          rest_i omitted where 0) of (kind, value) pairs -- kind is
#          "distance" (m/k/km/meters/metres), "time" (min/sec/s/M:SS/
#          :SS, normalised to seconds) or "cal", matched purely on
#          (kind, value), no role. Every unit-bearing token outside the
#          span, in text order (work and rest mentions both -- digits or
#          number-words all count, since _NUM_RE/_to_int already
#          normalise them; a bare number with no unit, "Day 2", "Week
#          3", is never unit-bearing and is ignored), must match some
#          chain-sequence token AFTER the one the previous outside token
#          matched (each chain token usable at most once, greedy
#          leftmost assignment). Any outside mention that cannot be
#          matched to a later, unconsumed chain token rejects -- this is
#          what makes a description that mentions a value more times, or
#          out of order, than the chain itself does reject, while 1-for-1
#          in-order restatement -- including a stray unit-less "Day 2 of
#          the challenge" -- always has room and is accepted.
#
# Newline-in-separator decision: the inter-leg separators ("\s*,\s*" /
# "\s*/\s*") and the optional qualifier's leading "\s+" all use \s, which
# already matches "\n". That is left as-is on purpose: a single logical
# chain that merely word-wraps mid-list onto the next physical line
# (e.g. a title stored as "500m, 1 minute\nrest, 500m") should still
# parse as one chain. This is safe together with the per-line anchor
# above because Python's re "^"/"$" in MULTILINE mode anchor to the
# start/end of the whole subject too when a candidate's internal "\s"
# happens to swallow a "\n" -- the candidate then simply spans more than
# one physical line as a single match, and the checks above still run
# against whatever text is left outside that (possibly multi-line) match.
_COMMA_CHAIN_CANDIDATE_RE = re.compile(
    r"^[ \t]*"
    + _CHAIN_LEG_RE_STR
    + r"(?:\s*,\s*"
    + _CHAIN_LEG_RE_STR
    + r"){2,}[ \t]*\.?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_SLASH_CHAIN_CANDIDATE_RE = re.compile(
    r"^[ \t]*"
    + _CHAIN_LEG_RE_STR
    + r"(?:\s*/\s*"
    + _CHAIN_LEG_RE_STR
    + r"){2,}[ \t]*\.?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# (a) Repeat cues: "N x"/"N X"/"N×", "N rounds"/"N sets"/"N times", or a
# bare "twice"/"thrice"/"repeat"/"rounds of"/"sets of".
_REPEAT_CUE_RE = re.compile(
    r"\b(?:"
    + _NUM_RE
    + r"\s*[xX×]\b"
    + r"|"
    + _NUM_RE
    + r"\s*rounds?\b"
    + r"|"
    + _NUM_RE
    + r"\s*sets?\b"
    + r"|"
    + _NUM_RE
    + r"\s*times\b"
    + r"|twice\b"
    + r"|thrice\b"
    + r"|repeat\b"
    + r"|rounds?\s+of\b"
    + r"|sets?\s+of\b"
    + r")",
    re.IGNORECASE,
)

# (c) A number+UNIT token: digits or a number-word immediately followed
# by a recognised unit, or an M:SS / :SS time. Mirrors the unit
# alternations used elsewhere in this module (_MIN_UNIT/_SEC_UNIT/
# _CAL_UNIT/distance units) so "unit-bearing" means exactly what the
# work/rest leg parsers themselves accept.
_UNIT_BEARING_RE = re.compile(
    r"\b(?P<num>"
    + _NUM_RE
    + r"(?:\.\d+)?)\s*(?P<unit>k\b|km\b|m\b|meters?\b|metres?\b|"
    + _MIN_UNIT
    + r"\b|"
    + _SEC_UNIT
    + r"\b|"
    + _CAL_UNIT
    + r"\b)"
    r"|(?P<mmss>\d{1,3}:\d{2})\b"
    r"|(?P<bare_ss>:\d{1,2})\b",
    re.IGNORECASE,
)

# A qualifier word immediately following a unit-bearing token, used only
# to read off whether that token is unambiguously a rest mention (check
# (c).1's "skip rest mentions"). "easy"/"light" appear in both lists on
# purpose -- they are genuinely ambiguous elsewhere in this module too.
_TRAILING_REST_ROLE_RE = re.compile(r"^\s*" + _REST_CUE_ALT + r"\b", re.IGNORECASE)
_TRAILING_WORK_ROLE_RE = re.compile(r"^\s*" + _WORK_QUALIFIER_ALT + r"\b", re.IGNORECASE)

# Check (c).1's lead-in test: the text immediately before the first
# outside WORK mention is acceptable if it is (via re.search, so this
# matches regardless of what -- if anything -- comes further back)
# either the very start of the text, a sentence-boundary punctuation
# mark, or a single bare article word, followed only by whitespace up
# to the mention. This is a whitelist, not a blacklist: everything not
# matching this shape rejects, so no cue word needs to be named.
_LEAD_IN_OK_RE = re.compile(r"(?:\A|[\n.!?:;]|\b(?:a|an|the)\b)\s*\Z", re.IGNORECASE)


def _unit_kind_value(unit: str, num: str) -> tuple:
    """(kind, value) for a matched _UNIT_BEARING_RE 'num'+'unit' pair,
    with time/distance normalised (minutes/k/km -> seconds/metres)."""
    unit_l = unit.lower()
    n = _to_int(num)
    if unit_l in ("k", "km"):
        return ("distance", int(round(n * 1000)))
    if unit_l == "m" or unit_l.startswith("meter") or unit_l.startswith("metre"):
        return ("distance", n)
    if unit_l.startswith("min"):
        return ("time", n * 60)
    if unit_l.startswith("sec") or unit_l == "s":
        return ("time", n)
    return ("cal", n)


def _is_rest_mention(kind: str, trailer: str) -> bool:
    """True only if a unit-bearing token is UNAMBIGUOUSLY a rest mention
    (a rest-only cue follows and no work qualifier also does) -- used to
    skip rest mentions when hunting for the first WORK mention outside
    the span (check (d))."""
    if kind != "time":
        return False
    is_rest = bool(_TRAILING_REST_ROLE_RE.match(trailer))
    is_work = bool(_TRAILING_WORK_ROLE_RE.match(trailer))
    return is_rest and not is_work


def _first_work_mention(rest_of_text: str):
    """The first _UNIT_BEARING_RE match in rest_of_text that is not
    unambiguously a rest mention, or None (see check (d))."""
    for m in _UNIT_BEARING_RE.finditer(rest_of_text):
        if m.group("num") is not None:
            kind, _value = _unit_kind_value(m.group("unit"), m.group("num"))
        else:
            kind = "time"  # mm:ss / bare :ss are always time
        if _is_rest_mention(kind, rest_of_text[m.end() :]):
            continue
        return m
    return None


def _chain_token_sequence(result: dict) -> list:
    """(kind, value) for every leg of an already-built intervals_variable
    result, in order: work1, rest1, work2, rest2, ..., workN (a leg's
    rest is omitted when 0, i.e. always for the last leg) -- see check
    (c).2 above."""
    seq = []
    for iv in result["intervals"]:
        work = iv["work"]
        if "distance_m" in work:
            seq.append(("distance", work["distance_m"]))
        elif "time_s" in work:
            seq.append(("time", work["time_s"]))
        else:
            seq.append(("cal", work["calories"]))
        if iv["rest_s"]:
            seq.append(("time", iv["rest_s"]))
    return seq


def _outside_mention_tokens(rest_of_text: str) -> list:
    """(kind, value) for every unit-bearing token in rest_of_text, in
    text order -- see check (c).2 above."""
    tokens = []
    for m in _UNIT_BEARING_RE.finditer(rest_of_text):
        if m.group("num") is not None:
            tokens.append(_unit_kind_value(m.group("unit"), m.group("num")))
        elif m.group("mmss") is not None:
            mm, ss = m.group("mmss").split(":")
            tokens.append(("time", int(mm) * 60 + int(ss)))
        else:
            tokens.append(("time", int(m.group("bare_ss").lstrip(":"))))
    return tokens


def _is_in_order_subsequence(mentions: list, chain_seq: list) -> bool:
    """True iff mentions is an in-order subsequence of chain_seq, each
    chain_seq token usable at most once (greedy leftmost assignment --
    see check (c).2 above)."""
    pointer = 0
    for tok in mentions:
        for j in range(pointer, len(chain_seq)):
            if chain_seq[j] == tok:
                pointer = j + 1
                break
        else:
            return False
    return True


def _match_variable_chain(text: str):
    """One separator kind per chain (comma or slash, never mixed):
    split a candidate run into an odd-length alternating work, rest,
    work, ... list. Full consumption of the input text is enforced by
    the checks in the comment above this matcher's regexes: a repeat
    cue outside the span, more than one independent chain candidate of
    the same kind, or text outside the span that doesn't have the
    restatement shape (a bad lead-in on the first WORK mention, or
    mentions that aren't an in-order subsequence of the chain's own
    tokens), all reject. No leg-count cap."""
    for candidate_re, split_re in (
        (_COMMA_CHAIN_CANDIDATE_RE, _COMMA_SEGMENT_SPLIT_RE),
        (_SLASH_CHAIN_CANDIDATE_RE, _SEGMENT_SPLIT_RE),
    ):
        matches = list(candidate_re.finditer(text))
        if len(matches) != 1:
            continue
        candidate = matches[0]
        candidate_text = candidate.group(0).strip()
        if candidate_text.endswith("."):
            candidate_text = candidate_text[:-1].rstrip()
        segs = split_re.split(candidate_text)
        result = _try_parse_variable_chain(segs)
        if result is None:
            continue
        rest_of_text = text[: candidate.start()] + text[candidate.end() :]
        if _REPEAT_CUE_RE.search(rest_of_text):
            continue
        first_work = _first_work_mention(rest_of_text)
        if first_work is not None and not _LEAD_IN_OK_RE.search(
            rest_of_text[: first_work.start()]
        ):
            continue
        if not _is_in_order_subsequence(
            _outside_mention_tokens(rest_of_text), _chain_token_sequence(result)
        ):
            continue
        return result
    return None


# --- Minute pyramids without slashes: "1 min, 2 min, 3 min, 4 min, 3
# min, 2 min, 1 min pyramid / 1 min easy" ------------------------------------

_COMMA_MIN_PYRAMID_RE = re.compile(
    r"((?:"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r"\s*,\s*)+"
    + _NUM_RE
    + r"\s*"
    + _MIN_UNIT
    + r")\s*pyramid\s*/\s*("
    + _NUM_RE
    + r")\s*"
    + _MIN_UNIT
    + r"\s*(?:easy|light|recovery|rest)",
    re.IGNORECASE,
)


def _match_comma_minute_pyramid(text: str):
    m = _COMMA_MIN_PYRAMID_RE.search(text)
    if not m:
        return None
    chunks = [c.strip() for c in m.group(1).split(",") if c.strip()]
    values = []
    for c in chunks:
        cm = re.match(r"^(" + _NUM_RE + r")\s*" + _MIN_UNIT + r"$", c, re.IGNORECASE)
        if not cm:
            return None
        values.append(_to_int(cm.group(1)) * 60)
    rest_s = _to_int(m.group(2)) * 60
    return _fixed_or_variable_from_values(values, "time_s", rest_s)


# --- "N x WORK / M REST-WORD" pyramids already covered by slash-min match
# above via 'a/b/c minutes with N minutes rest'; also need bare
# "a/b/c/d minutes with N minutes rest" without 'Intervals of' prefix --
# already covered by _SLASH_MIN_WITH_REST_RE.

# --- Single distance/time/calorie ------------------------------------------

_SINGLE_DIST_RE = re.compile(
    r"\b([\d,]+(?:\.\d+)?)\s*(k\b|m\b|meters?\b|meter\b)\b(?!\s*(?:[/xX]|:\d))",
    re.IGNORECASE,
)
_SINGLE_TIME_RE = re.compile(
    r"\b(" + _NUM_RE + r")\s*" + _MIN_UNIT + r"\b(?!\s*[,/])",
    re.IGNORECASE,
)
_SINGLE_CAL_RE = re.compile(
    r"\b(" + _NUM_RE + r")\s*" + _CAL_UNIT + r"\b",
    re.IGNORECASE,
)


# A "N x" / "N X" count prefix anywhere in the text means this is (or was
# meant to be) an interval workout. If none of the interval matchers
# handled it, treat it as unparsed rather than let _match_single guess a
# single workout from a stray number in the text.
_ANY_N_X_RE = re.compile(r"\b" + _NUM_RE + r"\s*[xX]\s*\d", re.IGNORECASE)


def _match_single(text: str):
    if _ANY_N_X_RE.search(text):
        return None
    # Distance takes priority (e.g. "5000m time trial", "2000m").
    m = _SINGLE_DIST_RE.search(text)
    if m:
        return _finalize(None, {"distance_m": _parse_distance_token(m.group(1), m.group(2))})
    m = _SINGLE_TIME_RE.search(text)
    if m:
        return _finalize(None, {"time_s": _to_int(m.group(1)) * 60})
    m = _SINGLE_CAL_RE.search(text)
    if m:
        return _finalize(None, {"calories": _to_int(m.group(1))})
    return None


# ---------------------------------------------------------------------------
# Session: [WARMUP] SET (SEP SET)* [COOLDOWN] -> one intervals_variable
# spec, e.g. "7 min warm-up, 10 x 1 min hard / 1 min light, 3 min
# cool-down". See docs/SPEC.md / bead pm5-7bk.3 for the grammar:
#
#   SESSION := [WARMUP SEP] SET (SEP SET)* [SEP COOLDOWN]
#   WARMUP  := WORK_UNIT (warm-up|warm up|warmup|easy|light)
#            | (warm up|warm-up|warmup) WORK_UNIT
#   COOLDOWN:= WORK_UNIT (cool-down|cool down|cooldown|easy|light)
#            | (cool down|cool-down|cooldown) WORK_UNIT
#   SET     := any text the existing FIXED interval matchers already
#              parse on their own (see _match_fixed_set below)
#   WORK_UNIT := what _parse_work_chunk accepts (distance/time/calories)
# ---------------------------------------------------------------------------

# Segment separators: comma, ';', newline, or a 'then'/'and then'/
# 'followed by' cue. Each split point is tagged 'comma', 'newline', or
# 'hard' (';'/'then'/'and then'/'followed by'):
#   - a SET can be greedily grown across a COMMA boundary only (a
#     fixed-interval phrase's own rest clause, e.g. "8 x 500m, 2 minutes
#     rest", is comma-separated from its count -- see _match_session
#     below) and never across a 'newline'/'hard' boundary, which always
#     marks a WARMUP/SET/COOLDOWN block boundary and must never be
#     folded into a SET;
#   - a 'newline' boundary specifically (title vs. description in this
#     corpus's title+"\n"+description convention) is the one place an
#     identical repeated SET is treated as prose restatement rather than
#     a genuine second block -- see the dedup comment in _match_session.
_SESSION_SEP_TOKEN_RE = re.compile(
    r"(?P<comma>,)|(?P<newline>\n)|(?P<hard>;|\band\s+then\b|\bthen\b|\bfollowed\s+by\b)",
    re.IGNORECASE,
)


def _split_session_segments(text: str):
    """Split text into (segment_text, preceded_by) pairs, preceded_by in
    {None, 'comma', 'newline', 'hard'} -- the kind of separator
    immediately before this segment (None for the first segment). Empty
    pieces (e.g. the space between a comma and a following 'then') are
    dropped; when that happens the *next* real separator's tag wins,
    since ', then' is one hard boundary as a whole, not a comma one
    followed by a hard one."""
    segments = []
    pos = 0
    preceded_by = None
    for m in _SESSION_SEP_TOKEN_RE.finditer(text):
        piece = text[pos : m.start()].strip()
        if piece:
            segments.append((piece, preceded_by))
        if m.group("comma"):
            preceded_by = "comma"
        elif m.group("newline"):
            preceded_by = "newline"
        else:
            preceded_by = "hard"
        pos = m.end()
    piece = text[pos:].strip()
    if piece:
        segments.append((piece, preceded_by))
    return segments


_SESSION_WARMUP_CUE_SUFFIX = r"(?:warm-up|warm up|warmup|easy|light)"
_SESSION_WARMUP_CUE_PREFIX = r"(?:warm up|warm-up|warmup)"
_SESSION_COOLDOWN_CUE_SUFFIX = r"(?:cool-down|cool down|cooldown|easy|light)"
_SESSION_COOLDOWN_CUE_PREFIX = r"(?:cool down|cool-down|cooldown)"

_SESSION_WARMUP_SUFFIX_RE = re.compile(
    r"^(.*?)\s+" + _SESSION_WARMUP_CUE_SUFFIX + r"\.?$", re.IGNORECASE
)
_SESSION_WARMUP_PREFIX_RE = re.compile(
    r"^" + _SESSION_WARMUP_CUE_PREFIX + r"\s+(.*?)\.?$", re.IGNORECASE
)
_SESSION_COOLDOWN_SUFFIX_RE = re.compile(
    r"^(.*?)\s+" + _SESSION_COOLDOWN_CUE_SUFFIX + r"\.?$", re.IGNORECASE
)
_SESSION_COOLDOWN_PREFIX_RE = re.compile(
    r"^" + _SESSION_COOLDOWN_CUE_PREFIX + r"\s+(.*?)\.?$", re.IGNORECASE
)


def _match_session_warmup(seg: str):
    """WARMUP, tried only on the first unconsumed segment. A segment
    that doesn't reduce to exactly a bare WORK_UNIT plus the cue word --
    e.g. an 'N x ...' SET that merely ends in the shared 'light'/'easy'
    word -- fails, since _parse_work_chunk rejects anything but a single
    amount+unit chunk."""
    seg = seg.strip()
    m = _SESSION_WARMUP_SUFFIX_RE.match(seg)
    if m:
        work = _parse_work_chunk(m.group(1))
        if work is not None:
            return work
    m = _SESSION_WARMUP_PREFIX_RE.match(seg)
    if m:
        work = _parse_work_chunk(m.group(1))
        if work is not None:
            return work
    return None


def _match_session_cooldown(seg: str):
    """COOLDOWN, tried only on the last unconsumed segment. Mirrors
    _match_session_warmup above."""
    seg = seg.strip()
    m = _SESSION_COOLDOWN_SUFFIX_RE.match(seg)
    if m:
        work = _parse_work_chunk(m.group(1))
        if work is not None:
            return work
    m = _SESSION_COOLDOWN_PREFIX_RE.match(seg)
    if m:
        work = _parse_work_chunk(m.group(1))
        if work is not None:
            return work
    return None


# SET, part 2: the existing FIXED interval matchers all require the rest
# clause to sit *immediately* after the work chunk (no qualifier word in
# between), so none of them accept e.g. '10 x 1:00 on / 1:00 off' ('on'
# blocks the rest clause from being recognised). Reuse the *chain*
# matcher's own permissive per-leg parsers instead
# (_parse_variable_work_leg / _parse_variable_rest_leg, from pm5-7bk.1,
# already know 'on' as a work qualifier and 'off' as a required rest
# cue) for a plain 'N x WORK_LEG [/,] REST_LEG' shape. Tried only as a
# fallback, after every existing fixed matcher, so it never changes what
# they already handle on their own -- it only covers SET shapes none of
# them recognise.
_SESSION_N_X_LEG_RE = re.compile(r"^(" + _NUM_RE + r")\s*[xX]\s*(.+)$", re.IGNORECASE)


def _match_n_x_leg_pair(text: str):
    m = _SESSION_N_X_LEG_RE.match(text.strip())
    if not m:
        return None
    count = _to_int(m.group(1))
    rest_text = m.group(2).strip()
    for split_re in (_SEGMENT_SPLIT_RE, _COMMA_SEGMENT_SPLIT_RE):
        parts = split_re.split(rest_text)
        if len(parts) != 2:
            continue
        work = _parse_variable_work_leg(parts[0])
        rest_s = _parse_variable_rest_leg(parts[1])
        if work is not None and rest_s is not None:
            return _finalize(None, work, rest_s=rest_s, count=count)
    return None


def _regex_covers_whole_text(compiled_re: re.Pattern, text: str) -> bool:
    """True iff compiled_re, searched against text, matches a span that
    covers the ENTIRE text (start to end) -- not just some substring of
    it. Used by _match_fixed_set below to reject a partial match rather
    than silently accept it with unmatched trailing (or leading) text,
    which is what let a SET's fixed matcher silently swallow only part
    of a segment and drop the rest (see the pm5-7bk.3 review that added
    this check)."""
    m = compiled_re.search(text)
    return m is not None and m.start() == 0 and m.end() == len(text)


# The existing FIXED interval matchers a SET may reuse, paired with a
# check that the matcher's OWN regex spans the whole (normalised)
# segment text -- never a partial match, which a plain .search() is
# otherwise happy to return while silently ignoring trailing/leading
# text it didn't account for (e.g. "3 x 4 min / 2 min rest and 3 min
# cool-down": _match_n_x_work_rest happily matches just "3 x 4 min / 2
# min rest" and would otherwise let " and 3 min cool-down" -- a real,
# separate leg -- vanish unclassified and unreported).
#
# _match_n_x_work_then_fallback_rest and _match_slash_or_dash_calories
# are deliberately NOT reused here (unlike in the top-level _MATCHERS
# pipeline): both search for their rest clause *anywhere* in the text
# rather than immediately after the work chunk, so "whole text covered"
# isn't a single contiguous regex span for them and can't be checked
# this way. Every SET shape they exist to catch inside a session is
# already covered by a stricter, self-anchored alternative --
# _match_n_x_work_rest (adjacent rest) or _match_n_x_leg_pair (permissive
# qualifier words, but still anchored end-to-end) -- so dropping them
# here only removes a source of exactly this partial-match risk, without
# losing any required SET shape.
_FIXED_SET_MATCHERS = [
    (_match_comma_minute_pyramid, lambda t: _regex_covers_whole_text(_COMMA_MIN_PYRAMID_RE, t)),
    (
        _match_slash_minutes_with_rest,
        lambda t: (
            _regex_covers_whole_text(_INTERVALS_OF_SLASH_MIN_RE, t)
            or _regex_covers_whole_text(_SLASH_MIN_WITH_REST_RE, t)
        ),
    ),
    (
        _match_slash_distance_with_rest,
        lambda t: _regex_covers_whole_text(_SLASH_DIST_WITH_REST_RE, t),
    ),
    (_match_n_rounds_of, lambda t: _regex_covers_whole_text(_N_ROUNDS_OF_WORK_REST_RE, t)),
    (_match_n_x_work_rest, lambda t: _regex_covers_whole_text(_N_X_WORK_SEP_REST_RE, t)),
    (
        _match_n_x_work_with_rest,
        lambda t: _regex_covers_whole_text(_N_X_WORK_WITH_REST_RE, t),
    ),
    # Already fully self-anchored (^...$ throughout, and each leg parser
    # requires its own whole sub-part), so it can never partially match.
    (_match_n_x_leg_pair, lambda t: True),
]


def _fixed_set_key(fixed_set: dict):
    """Comparable (work, rest_s, count) key for a _match_fixed_set
    result, used to detect a restated duplicate SET (see
    _match_session)."""
    work = fixed_set["work"]
    return (tuple(sorted(work.items())), fixed_set["rest_s"], fixed_set["count"])


def _match_fixed_set(text: str):
    """Try each FIXED interval matcher against text, keeping only a
    result whose own regex spans the WHOLE (normalised) text -- see
    _regex_covers_whole_text -- and only a uniform fixed-shape result
    (kind intervals_* other than intervals_variable -- a ladder/pyramid
    result from e.g. _match_slash_minutes_with_rest on unequal values
    isn't a SET this grammar can expand into count-many equal legs, so
    that's treated as no match here, not as a session SET)."""
    text = text.strip()
    if text.endswith("."):
        text = text[:-1].rstrip()
    if not text:
        return None
    for matcher, covers_whole_text in _FIXED_SET_MATCHERS:
        if not covers_whole_text(text):
            continue
        spec = matcher(text)
        if spec is not None and spec["kind"] != "intervals_variable":
            return spec
    return None


def _match_session(text: str):
    """Parse the whole SESSION grammar (see the block comment above).
    Full consumption is enforced directly (every split segment must
    classify as WARMUP, a SET, or COOLDOWN, in that structural order, or
    the whole match fails) rather than via the leftover-cue guard, since
    a legitimate session's own text always contains a warm-up/cool-down
    cue word next to a number+unit token -- exactly what that guard
    would otherwise flag as leftover (see the self_guarded parameter on
    _leftover_cue_guard).

    Returns None (never guesses) if any segment can't be classified, or
    if the text is just one bare SET with no WARMUP/COOLDOWN and no
    second SET -- that case is left to the plain fixed-interval matchers
    so '10 x 1 min / 1 min easy' stays intervals_time, not a one-set
    'session'."""
    segs = _split_session_segments(text)
    n = len(segs)
    if n == 0:
        return None

    i = 0
    warmup_work = _match_session_warmup(segs[0][0])
    if warmup_work is not None:
        i = 1

    end = n
    cooldown_work = None
    if end > i:
        cooldown_work = _match_session_cooldown(segs[end - 1][0])
        if cooldown_work is not None:
            end -= 1

    # Consume SET(s) from the remaining [i, end) segments. For each SET,
    # try the smallest span first (just segs[i] alone); grow across a
    # COMMA boundary one segment at a time only when the smaller span
    # doesn't match on its own (e.g. "8 x 500m" alone has no rest clause
    # and fails every fixed matcher, forcing a grow to "8 x 500m, 2
    # minutes rest", which does match) -- this is what keeps a comma
    # that belongs to a SET's own rest clause from being treated as a
    # session-level segment boundary.
    sets = []
    while i < end:
        # The separator immediately before this SET's own first segment
        # -- used below to decide whether an identical repeat is prose
        # restatement (only across a bare NEWLINE, i.e. a title vs. its
        # description in this corpus's title+"\n"+description
        # convention) or a genuine second block (across a comma, ';',
        # 'then'/'and then', or 'followed by' -- all of which state a
        # deliberate second SET, never a restatement of the first).
        boundary_before_set = segs[i][1]
        joined_parts = [segs[i][0]]
        span = 1
        matched = _match_fixed_set(joined_parts[0])
        while matched is None:
            next_idx = i + span
            if next_idx >= end or segs[next_idx][1] != "comma":
                break
            joined_parts.append(segs[next_idx][0])
            span += 1
            matched = _match_fixed_set(", ".join(joined_parts))
        if matched is None:
            # Unclassified segment(s) -- never guess.
            return None
        # A SET whose (work, rest_s, count) is identical to the
        # immediately preceding SET, separated from it by a bare
        # NEWLINE, is a prose restatement of it (e.g. a title's terse
        # "8 x 500m, 2 minutes rest" restated in the description as
        # "8 x 500m intervals with 2 minutes rest."), not a second
        # distinct interval block: consume it (so it isn't leftover,
        # unclassified text) but don't add a duplicate SET's worth of
        # legs, and don't let it count toward the "or a 2nd SET" arity
        # rule below. An identical SET separated by anything else --
        # comma, ';', 'then'/'and then', 'followed by' -- is a genuine
        # repeat (e.g. "4 x 500m / 1 min rest, then 4 x 500m / 1 min
        # rest" really does mean 8 work legs, not 4), and a SET with
        # *different* values is of course never deduped either way.
        if (
            sets
            and boundary_before_set == "newline"
            and _fixed_set_key(matched) == _fixed_set_key(sets[-1])
        ):
            pass
        else:
            sets.append(matched)
        i += span

    if not sets:
        return None
    if warmup_work is None and cooldown_work is None and len(sets) < 2:
        return None

    legs = []
    first_set_rest = sets[0]["rest_s"]
    if warmup_work is not None:
        # Design decision: the warm-up flows into the FIRST set's own
        # rest (not a rest of 0) -- the warm-up leg still needs some
        # rest value to hand off into the first work interval, and the
        # first SET's own rest is the only rest value in scope for it.
        legs.append({"work": warmup_work, "rest_s": first_set_rest})

    for idx, s in enumerate(sets):
        if s["rest_s"] == 0 and idx != len(sets) - 1:
            # validate_spec forbids rest_s == 0 on a non-final leg; a
            # SET with no rest that isn't the last SET would produce
            # exactly that once expanded. Never guess a rest value here.
            return None
        for _ in range(s["count"]):
            legs.append({"work": s["work"], "rest_s": s["rest_s"]})

    if cooldown_work is not None:
        legs.append({"work": cooldown_work, "rest_s": 0})
    else:
        # The PM5 never runs the last rest -- with no COOLDOWN leg, the
        # final SET's own last leg becomes the final leg overall.
        legs[-1] = {"work": legs[-1]["work"], "rest_s": 0}

    return _finalize(None, None, intervals=legs)


# ---------------------------------------------------------------------------
# BikeErg override application
# ---------------------------------------------------------------------------


def _apply_bikeerg_override(spec: dict, overrides) -> dict:
    """Positionally apply a BikeErg distance override to a spec's work
    (singles/fixed intervals) or intervals (variable). Only intervals
    whose own work unit is distance are overridden -- a mixed
    intervals_variable spec (e.g. one distance leg + one time leg) must
    not have its time-based leg silently turned into a distance
    (BikeErg overrides in this corpus are always distance replacements
    for what was, on RowErg/SkiErg, a distance leg)."""
    if spec["kind"] == "intervals_variable":
        intervals = spec["intervals"]
        distance_positions = [i for i, iv in enumerate(intervals) if "distance_m" in iv["work"]]
        if not distance_positions:
            return spec
        new_intervals = list(intervals)
        if len(overrides) == 1:
            # Single override value applies to every distance leg.
            for i in distance_positions:
                new_intervals[i] = {
                    "work": {"distance_m": overrides[0]},
                    "rest_s": intervals[i]["rest_s"],
                }
        elif len(overrides) == len(distance_positions):
            # Positional list maps one-to-one onto the distance legs, in
            # order (skipping any non-distance legs).
            for override_i, pos in enumerate(distance_positions):
                new_intervals[pos] = {
                    "work": {"distance_m": overrides[override_i]},
                    "rest_s": intervals[pos]["rest_s"],
                }
        else:
            # Override count doesn't line up with the number of distance
            # legs -- ambiguous, never guess.
            return spec
        spec = dict(spec)
        spec["intervals"] = new_intervals
        return spec

    work = spec.get("work")
    if work is None or "distance_m" not in work:
        return spec
    if len(overrides) != 1:
        # A positional list override doesn't make sense for a single
        # work value or fixed-interval spec (only one distance slot to
        # fill) -- ambiguous, never guess.
        return spec
    spec = dict(spec)
    spec["work"] = {"distance_m": overrides[0]}
    return spec


# ---------------------------------------------------------------------------
# Top-level parse_spec
# ---------------------------------------------------------------------------

# Matchers tried in priority order (most specific first). _match_session
# is tried before every fixed-interval matcher (it needs first refusal
# so a warm-up/cool-down-wrapped SET isn't instead swallowed piecemeal
# by a fixed matcher matching just the SET portion) and before
# _match_variable_chain too: a session's SET always has its own explicit
# 'N x'/'rounds of'/ladder count, a shape _match_variable_chain's
# alternating-legs-without-a-count grammar never produces, so the two
# are effectively disjoint and ordering between them doesn't change any
# result -- _match_session goes first as the more specific, more
# tightly-validated (full segment consumption) check of the two.
_MATCHERS = [
    _match_equal_work_and_rest,
    _match_session,
    _match_variable_chain,
    _match_comma_minute_pyramid,
    _match_slash_minutes_with_rest,
    _match_slash_distance_with_rest,
    _match_slash_or_dash_calories,
    _match_n_rounds_of,
    _match_n_x_work_rest,
    _match_n_x_work_with_rest,
    _match_n_x_work_then_fallback_rest,
]

# Text containing any of these signals a workout shape the spec cannot
# express with confidence (nested/repeated blocks, per-segment stroke
# rates that change mid-interval, or a single distance explicitly split
# into unequal, unrest sub-intervals). Rather than let a later, more
# permissive matcher (e.g. the bare single_distance/time fallback)
# silently produce a *wrong* spec for this text, bail out up front.
# Matched case-insensitively against the raw (non-stripped) text so it
# also catches these phrases inside a stripped-out BikeErg parenthetical.
_REJECT_RE = re.compile(
    r"\btabata\b"
    r"|\brate changes?\b"
    r"|\bstroke rates?\b"
    r"|\bcadence\b"
    r"|\brepeat\b"
    r"|\bsplit into\b",
    re.IGNORECASE,
)

# "N rounds of ... x ..." / "N sets of ... x ..." -- a repeated block of
# intervals nested inside an outer repeat count. The spec has no
# outer-repeat concept, so this must not fall through to a flat
# intervals_* match.
_NESTED_REPEAT_RE = re.compile(
    r"\b(?:" + _NUM_RE + r")\s*(?:rounds?|sets?)\s+of\s+(?:" + _NUM_RE + r")\s*[xX]\s",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Leftover-cue guard: reject a spec if the text still contains a signal the
# matched kind cannot represent, rather than let a matcher silently
# under-fit an interval/rest structure it didn't actually capture (never
# guess). See docs/SPEC.md, "Never-guess: leftover-cue guard".
# ---------------------------------------------------------------------------

# A count cue: "N x", "N rounds", "N sets", "N reps", "N intervals", "N
# pieces", "N times" -- signals a repeated/interval structure. Also catches
# plural shorthand like "500s" / "ten 500s".
_COUNT_CUE_RE = re.compile(
    r"\b" + _NUM_RE + r"\s*(?:x|×|rounds?|sets?|reps?|intervals?|pieces?|times)\b",
    re.IGNORECASE,
)
_PLURAL_NUM_CUE_RE = re.compile(r"\b\d+s\b")

# An outer-repeat cue: "N rounds/sets of" -- signals a repeat wrapping
# further structure. Narrower than _COUNT_CUE_RE (excludes bare "N
# intervals"/"N pieces" framing, which fixed/variable interval descriptions
# legitimately use to restate their own count, e.g. "Seven intervals in a
# pyramid of ...").
_OUTER_REPEAT_OF_RE = re.compile(r"\b(" + _NUM_RE + r")\s*(?:rounds?|sets?)\s+of\b", re.IGNORECASE)

# Rest/chaining cue words. These are only disqualifying for a single_*
# result when they occur in the *same sentence* as a number+unit work
# token (see _sentence_disqualifies_single below) -- a lone cue word can
# be innocuous framing text in an unrelated sentence (e.g. "...taking
# place between March 6-10, 2024", "Then enter your result in the Online
# Ranking..."), so a whole-text word search alone is not reliable.
_REST_CUE_WORDS_RE = re.compile(
    r"\b(rest|easy|off|recovery|recover|light|between|on/off|then"
    r"|followed by|warm-up|warm up|warmup|cool-down|cool down|cooldown)\b",
    re.IGNORECASE,
)

# Structural leftover cues that signal an outside warm-up/cool-down/
# chained leg a matched fixed *interval* span cannot represent --
# narrower than _REST_CUE_WORDS_RE above (deliberately excludes
# rest/easy/light/off/recovery/between, which legitimately occur
# *inside* an interval matcher's own captured rest-word suffix, e.g.
# "8 x 500m, 2 minutes rest"; warm-up/cool-down/then never legitimately
# occur inside a fixed-interval matcher's own captured span). Only
# disqualifying when a cue word here co-occurs with a number+unit work
# token in the same sentence -- see _sentence_has_interval_leftover_cue
# below.
_INTERVAL_LEFTOVER_CUE_WORDS_RE = re.compile(
    r"\b(warm-up|warm up|warmup|cool-down|cool down|cooldown|then)\b",
    re.IGNORECASE,
)

# Same idea, restricted to warm-up/cool-down only (no "then"), for
# intervals_variable results. The intervals_variable-producing matchers
# (ladders/pyramids as well as the variable chain) only match the
# concise title-line shape and routinely trust a prose *description*
# that restates the same ladder with "... then 1000m, then 500m." --
# unlike warm-up/cool-down, a bare "then" is not a reliable signal of
# an untracked extra leg here, so it is intentionally left out of this
# narrower set to avoid rejecting that legitimate restatement style.
_VARIABLE_LEFTOVER_CUE_WORDS_RE = re.compile(
    r"\b(warm-up|warm up|warmup|cool-down|cool down|cooldown)\b",
    re.IGNORECASE,
)

# "followed by DURATION rest-word" -- the legitimate "WORK followed by
# REST" phrasing already consumed by the N-rounds-of/N-x-work matchers
# (e.g. "20 rounds of 45 seconds work followed by 45 seconds rest", "6
# intervals of 1000m followed by 2 minutes rest"). Stripped out before
# checking for a leftover "followed by" chaining cue.
_FOLLOWED_BY_REST_RE = re.compile(
    r"followed by\s*" + _NUM_RE + r"\s*(?:" + _MIN_UNIT + r"|" + _SEC_UNIT + r")"
    r"\s*(?:rest|easy|light|recovery)\b",
    re.IGNORECASE,
)

# "N rounds/sets of" restating the same count already captured by an "N x
# ..." match in the same text (e.g. title "20 x 45s work, 45s rest",
# description "20 rounds of 45 seconds work followed by 45 seconds rest")
# is a redundant restatement, not a nested outer repeat -- only disqualify
# when the numbers differ (or there is no "N x" match to compare against).
_ANY_N_X_NUM_RE = re.compile(r"\b(" + _NUM_RE + r")\s*[xX]\s*\d", re.IGNORECASE)

# A number+unit "work" token: metres (incl. 'k' thousands), minutes,
# seconds, calories, or m:ss. Used to scope the rest/chaining-cue check to
# the sentence that actually describes a piece of work, and to detect two
# or more such tokens co-occurring in one sentence (a chained/second
# piece), e.g. "500m then 1000m", "2000m followed by 1000m".
_NUM_UNIT_TOKEN_RE = re.compile(
    r"\b\d{1,3}:\d{2}\b"
    r"|\b[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    r"|\b" + _NUM_RE + r"\s*" + _MIN_UNIT + r"\b"
    r"|\b" + _NUM_RE + r"\s*" + _SEC_UNIT + r"\b"
    r"|\b" + _NUM_RE + r"\s*" + _CAL_UNIT + r"\b",
    re.IGNORECASE,
)

# Sentence boundary: '.', '!', '?', or a newline (title/description are
# joined with '\n', and each is itself often multiple '.'-terminated
# sentences).
_SENTENCE_SPLIT_RE = re.compile(r"[.!?\n]+")

# Narrow date-context exclusion: "between" does not count as a rest cue
# when it introduces a date/event window rather than a rest duration,
# e.g. "...ski 1000m between now and Sunday", "...taking place between
# March 6-10, 2024". Matches "between now and", "between <Weekday>", or
# "between <Month>".
_BETWEEN_DATE_CONTEXT_RE = re.compile(
    r"\bbetween\s+(?:now\s+and\b"
    r"|(?:Mon|Tues?|Wed(?:nes)?|Thur?s?|Fri|Sat(?:ur)?|Sun)(?:day)?\b"
    r"|Jan(?:uary)?\b|Feb(?:ruary)?\b|Mar(?:ch)?\b|Apr(?:il)?\b|May\b"
    r"|Jun(?:e)?\b|Jul(?:y)?\b|Aug(?:ust)?\b|Sep(?:t(?:ember)?)?\b"
    r"|Oct(?:ober)?\b|Nov(?:ember)?\b|Dec(?:ember)?\b)",
    re.IGNORECASE,
)


def _sentence_disqualifies_single(sentence: str) -> bool:
    """Return True if this one sentence (from clean_text, split on
    [.!?\\n]) disqualifies a single_* result: either a rest/chaining cue
    word co-occurring with a number+unit work token in the sentence (a
    lone "between" that only introduces a date/event window is excluded),
    or two or more number+unit work tokens in the sentence (a chained
    second piece, regardless of cue words)."""
    tokens = _NUM_UNIT_TOKEN_RE.findall(sentence)
    if len(tokens) >= 2:
        return True
    if not tokens:
        return False
    for cue in _REST_CUE_WORDS_RE.finditer(sentence):
        word = cue.group(1).lower()
        if word == "between":
            # Only disqualifying if this "between" is not a date/event
            # window reference.
            date_ctx = False
            for dm in _BETWEEN_DATE_CONTEXT_RE.finditer(sentence):
                if dm.start() == cue.start():
                    date_ctx = True
                    break
            if date_ctx:
                continue
        return True
    return False


def _sentence_has_interval_leftover_cue(sentence: str, cue_re: re.Pattern) -> bool:
    """Return True if this one sentence (from clean_text, split on
    [.!?\\n]) carries a cue word matched by cue_re together with a
    number+unit work token -- e.g. "7 min warm-up", "then 3 minutes
    cool down". A bare cue word alone, with no accompanying
    duration/distance in the same sentence (e.g. "Warm up well
    first."), is not disqualifying -- mirrors the co-occurrence rule in
    _sentence_disqualifies_single above, but scoped to the narrower
    _INTERVAL_LEFTOVER_CUE_WORDS_RE / _VARIABLE_LEFTOVER_CUE_WORDS_RE
    cue sets (see their comments for why rest/easy/light/off/
    recovery/between/then are excluded)."""
    if not cue_re.search(sentence):
        return False
    return bool(_NUM_UNIT_TOKEN_RE.search(sentence))


def _leftover_cue_guard(kind: str, clean_text: str, self_guarded: bool = False) -> bool:
    """Return True if clean_text still carries a cue the matched kind
    cannot represent -- i.e. the spec must be discarded (never guess).

    self_guarded: True when the spec came from _match_variable_chain or
    _match_session, matchers that already enforce their own full-text-
    consumption rule (see the long comment above _match_variable_chain,
    and _match_session's docstring) -- so the generic sentence-scoped
    warm-up/cool-down/then check below is skipped for their results.
    Applying it on top would reject:
      - the chain matcher's own legitimate prose restatements (e.g. "A 6
        minute warm-up, then ten 1 minute hard efforts ..., then a 3
        minute cool-down.") that say in prose exactly what the chain
        already captured;
      - every successful _match_session result outright, since a
        session's own matched text always contains a warm-up/cool-down
        cue word next to a number+unit token -- that's what the session
        matcher itself looks for, not leftover content it failed to
        capture."""
    count_hits = _COUNT_CUE_RE.findall(clean_text)
    has_count_cue = bool(count_hits) or bool(_PLURAL_NUM_CUE_RE.search(clean_text))

    if kind.startswith("single_"):
        # A single piece has no count cue anywhere, and no sentence
        # containing a number+unit work token also carries a
        # (non-date-context) rest/chaining cue word or a second
        # number+unit work token.
        if has_count_cue:
            return True
        for sentence in _SENTENCE_SPLIT_RE.split(clean_text):
            if _sentence_disqualifies_single(sentence):
                return True
        return False

    if kind == "intervals_variable":
        # Allowed as long as no outer-repeat ("N rounds/sets of") cue
        # remains -- a variable-interval description legitimately mentions
        # its own piece count in prose (e.g. "Seven intervals in a
        # pyramid of ...").
        if _OUTER_REPEAT_OF_RE.search(clean_text):
            return True
        if self_guarded:
            return False
        # A leftover warm-up/cool-down cue co-occurring with a
        # number+unit token in the same sentence signals an extra leg
        # this variable-interval match didn't actually capture.
        for sentence in _SENTENCE_SPLIT_RE.split(clean_text):
            if _sentence_has_interval_leftover_cue(sentence, _VARIABLE_LEFTOVER_CUE_WORDS_RE):
                return True
        return False

    # Fixed intervals_* (intervals_distance/time/calorie): allowed as long
    # as no outer-repeat cue remains that isn't a restatement of the same
    # count already captured via "N x ...", and no "then"/"followed by"
    # chaining cue remains once the legitimate "... followed by DURATION
    # rest" phrasing is discounted.
    outer_repeat_matches = _OUTER_REPEAT_OF_RE.findall(clean_text)
    if outer_repeat_matches:
        n_x_match = _ANY_N_X_NUM_RE.search(clean_text)
        matched_count = _to_int(n_x_match.group(1)) if n_x_match else None
        for n in outer_repeat_matches:
            if matched_count is None or _to_int(n) != matched_count:
                return True

    without_followed_by_rest = _FOLLOWED_BY_REST_RE.sub(" ", clean_text)
    if re.search(r"\bthen\b|\bfollowed by\b", without_followed_by_rest, re.IGNORECASE):
        return True

    # A leftover warm-up/cool-down cue (or a 'then' not already caught
    # above) co-occurring with a number+unit token in the same sentence
    # signals an extra leg this fixed-interval match didn't capture,
    # e.g. "7 min warm-up, 10 x 1 min hard / 1 min light, 3 min
    # cool-down".
    for sentence in _SENTENCE_SPLIT_RE.split(clean_text):
        if _sentence_has_interval_leftover_cue(sentence, _INTERVAL_LEFTOVER_CUE_WORDS_RE):
            return True

    return False


def parse_spec(text: str, machines: str | None = None) -> dict | None:
    """Parse free-form workout text into a WorkoutSpec dict, or return
    None if it cannot be parsed with confidence."""
    if not text or not text.strip():
        return None

    if _REJECT_RE.search(text) or _NESTED_REPEAT_RE.search(text):
        return None

    machine = _map_machine(machines)
    overrides = _extract_bikeerg_override(text) if machines == "BikeErg" else None

    if (
        machines == "BikeErg"
        and overrides is None
        and (
            _BIKEERG_PAREN_RE.search(text)
            or _BIKEERG_INLINE_RE.search(text)
            or _BIKEERG_NOTE_RE.search(text)
        )
    ):
        # A BikeErg override aside is present but couldn't be parsed
        # (e.g. a malformed positional list) -- never silently fall back
        # to the un-overridden RowErg/SkiErg distance.
        return None

    clean = _strip_parenthetical_and_notes(text)

    spec = None
    matched_by = None
    for matcher in _MATCHERS:
        spec = matcher(clean)
        if spec is not None:
            matched_by = matcher
            break

    if spec is None:
        spec = _match_single(clean)

    if spec is None:
        return None

    if _leftover_cue_guard(
        spec["kind"],
        clean,
        self_guarded=(matched_by is _match_variable_chain or matched_by is _match_session),
    ):
        return None

    spec["machine"] = machine
    spec["notes"] = ""

    if overrides:
        spec = _apply_bikeerg_override(spec, overrides)

    try:
        validate_spec(spec)
    except ValueError:
        return None

    return spec


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_DEFAULT_COVERAGE_PARSED = os.path.join("data", "spec_parsed.jsonl")
_DEFAULT_COVERAGE_UNPARSED = os.path.join("data", "reports", "spec_unparsed.md")


def _run_coverage(
    path: str,
    parsed_path: str = _DEFAULT_COVERAGE_PARSED,
    unparsed_path: str = _DEFAULT_COVERAGE_UNPARSED,
) -> None:
    rows = [json.loads(line) for line in open(path)]

    parsed_rows = 0
    parsed_count = 0
    total_count = 0
    unparsed = []
    parsed_out = []

    for r in rows:
        title = r.get("title", "")
        description = r.get("description", "")
        machines = r.get("machines")
        count = r.get("count", 1)
        total_count += count
        text = f"{title}\n{description}"
        spec = parse_spec(text, machines)
        if spec is None:
            unparsed.append(r)
        else:
            parsed_rows += 1
            parsed_count += count
            parsed_out.append(
                {
                    "title": title,
                    "description": description,
                    "machines": machines,
                    "pm5": r.get("pm5"),
                    "spec": spec,
                }
            )

    total_rows = len(rows)
    pct_rows = 100.0 * parsed_rows / total_rows if total_rows else 0.0
    pct_count = 100.0 * parsed_count / total_count if total_count else 0.0

    print(f"parsed rows: {parsed_rows}/{total_rows} ({pct_rows:.1f}%)")
    print(f"parsed count-weighted: {parsed_count}/{total_count} ({pct_count:.1f}%)")
    print(f"unparsed rows: {len(unparsed)}")

    unparsed_dir = os.path.dirname(unparsed_path)
    if unparsed_dir:
        os.makedirs(unparsed_dir, exist_ok=True)
    with open(unparsed_path, "w") as f:
        f.write("# Unparsed rows\n\n")
        f.write(f"{len(unparsed)} of {total_rows} distinct rows did not parse.\n\n")
        for r in unparsed:
            f.write(
                f"- count={r.get('count', 1)} machines={r.get('machines')!r}\n"
                f"  title: {r.get('title', '')!r}\n"
                f"  description: {r.get('description', '')!r}\n\n"
            )

    parsed_dir = os.path.dirname(parsed_path)
    if parsed_dir:
        os.makedirs(parsed_dir, exist_ok=True)
    with open(parsed_path, "w") as f:
        for row in parsed_out:
            f.write(json.dumps(row) + "\n")

    print(f"wrote {unparsed_path}")
    print(f"wrote {parsed_path}")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] == "--coverage":
        if len(argv) < 2:
            print(
                "usage: spec.py --coverage <dataset.jsonl> "
                f"[--parsed {_DEFAULT_COVERAGE_PARSED}] [--unparsed {_DEFAULT_COVERAGE_UNPARSED}]",
                file=sys.stderr,
            )
            return 2
        dataset_path = argv[1]
        parsed_path = _DEFAULT_COVERAGE_PARSED
        unparsed_path = _DEFAULT_COVERAGE_UNPARSED
        i = 2
        while i < len(argv):
            if argv[i] == "--parsed" and i + 1 < len(argv):
                parsed_path = argv[i + 1]
                i += 2
            elif argv[i] == "--unparsed" and i + 1 < len(argv):
                unparsed_path = argv[i + 1]
                i += 2
            else:
                print(
                    "usage: spec.py --coverage <dataset.jsonl> "
                    f"[--parsed {_DEFAULT_COVERAGE_PARSED}] "
                    f"[--unparsed {_DEFAULT_COVERAGE_UNPARSED}]",
                    file=sys.stderr,
                )
                return 2
        _run_coverage(dataset_path, parsed_path, unparsed_path)
        return 0

    machines = None
    text_parts = []
    i = 0
    while i < len(argv):
        if argv[i] == "--machines":
            machines = argv[i + 1]
            i += 2
        else:
            text_parts.append(argv[i])
            i += 1

    text = " ".join(text_parts)
    spec = parse_spec(text, machines)
    if spec is None:
        print("unparsed", file=sys.stderr)
        return 2

    print(json.dumps(spec, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
