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

    python3 -m pm5keys.spec --coverage dataset_unique.jsonl
        Run parse_spec over every row of a dataset_unique.jsonl-shaped
        file (using title + '\\n' + description as the text), print
        parsed/unparsed counts (by row and weighted by count), and
        write spec_unparsed.md and spec_parsed.jsonl.
"""

from __future__ import annotations

import json
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
                "intervals_variable must not carry work/rest_s/count "
                "(use intervals instead)"
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
                raise ValueError(
                    f"intervals[{i}].rest_s == 0 but is not the last interval"
                )
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
_BIKEERG_PAREN_RE = re.compile(
    r"\(\s*(?:for\s+)?bikeerg\s*:?\s*([^)]*)\)", re.IGNORECASE
)
_BIKEERG_NOTE_RE = re.compile(
    r"note:\s*for\s+bikeerg,\s*distance\s+is\s+([\d,]+)\s*met(?:er|re)s?",
    re.IGNORECASE,
)
_BIKEERG_INLINE_RE = re.compile(
    r"\(([\d,]+)\s*m\s+for\s+bikeerg\)", re.IGNORECASE
)

_DIST_NUM_UNIT_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(k\b|m\b|meters?\b|meter\b)\b", re.IGNORECASE
)


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
        raw_parts = [
            p.strip()
            for p in re.split(r"[,/]\s*(?!\d{3}\b)", inner)
            if p.strip()
        ]
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
            values = [
                _parse_distance_token(p, unit) for p in raw_parts[:-1]
            ]
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
    r"(" + _NUM_RE + r")\s*[xX]\s*("
    + r"\d{1,3}:\d{2}"  # mm:ss
    + r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"  # distance
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT  # minutes
    + r"|" + _NUM_RE + r"\s*" + _SEC_UNIT  # seconds
    + r"|" + _NUM_RE + r"\s*" + _CAL_UNIT  # calories
    + r")"
    r"(?:\s*(?:work)?\s*[,/]?\s*("
    + r"\d{1,2}:\d{2}"
    + r"|:\d{1,2}"  # bare colon-prefixed seconds, e.g. ':20'
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT
    + r"|" + _NUM_RE + r"\s*" + _SEC_UNIT
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
    r"(" + _NUM_RE + r")\s*[xX]\s*("
    + r"\d{1,3}:\d{2}"
    + r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT
    + r"|" + _NUM_RE + r"\s*" + _SEC_UNIT
    + r"|" + _NUM_RE + r"\s*" + _CAL_UNIT
    + r")",
    re.IGNORECASE,
)

# "N X 25 Cals with 1 minute easy" style (count before work, 'with' before
# rest). Handled by _N_X_WORK_SEP_REST_RE already via 'with' not matching
# the separator -- add a dedicated 'with' variant.
_N_X_WORK_WITH_REST_RE = re.compile(
    r"(" + _NUM_RE + r")\s*[xX]\s*("
    + r"[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT
    + r"|" + _NUM_RE + r"\s*" + _SEC_UNIT
    + r"|" + _NUM_RE + r"\s*" + _CAL_UNIT
    + r")"
    r"\s*with\s*("
    + _NUM_RE + r")\s*(" + _MIN_UNIT
    + r"|" + _SEC_UNIT
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
    r"(" + _NUM_RE + r")\s*(?:rounds?|intervals?)\s+of\s+("
    + _NUM_RE + r"\s*" + _SEC_UNIT
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT
    + r"|[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
    + r")\s*(?:work)?\s*(?:followed by|and|,)?\s*("
    + _NUM_RE + r"\s*" + _SEC_UNIT
    + r"|" + _NUM_RE + r"\s*" + _MIN_UNIT
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
    r"((?:" + _NUM_RE + r"\s*/\s*)+" + _NUM_RE + r")\s*" + _MIN_UNIT
    + r"\s*with\s*(" + _NUM_RE + r")\s*" + _MIN_UNIT + r"\s*(?:rest|easy|light|recovery)?",
    re.IGNORECASE,
)

# "Intervals of 6/3/3/1/1/1 minutes with 2 minutes rest."
_INTERVALS_OF_SLASH_MIN_RE = re.compile(
    r"intervals\s+of\s+((?:" + _NUM_RE + r"\s*/\s*)+" + _NUM_RE + r")\s*"
    + _MIN_UNIT + r"\s*with\s*(" + _NUM_RE + r")\s*" + _MIN_UNIT
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
# rest/500m", "3000m, 3 minutes rest, 10 minutes work" -----------------------

_SEGMENT_SPLIT_RE = re.compile(r"\s*/\s*")


def _try_parse_variable_chain(segments):
    """segments: list of strings alternating work/rest, where rest
    segments end in 'rest' (or similar). Build intervals_variable if it
    strictly alternates work, rest, work, rest, ..., work (odd length,
    starting and ending with work)."""
    if len(segments) < 3 or len(segments) % 2 == 0:
        return None
    works = []
    rests = []
    for i, seg in enumerate(segments):
        seg = seg.strip()
        if i % 2 == 0:
            w = _parse_work_chunk(seg)
            if w is None:
                return None
            works.append(w)
        else:
            m = re.match(
                r"^(" + _NUM_RE + r")\s*(" + _MIN_UNIT + r"|" + _SEC_UNIT + r")\s*rest\.?$",
                seg,
                re.IGNORECASE,
            )
            if not m:
                return None
            rests.append(_duration_words_to_seconds(m.group(1), m.group(2)))
    intervals = []
    for i, w in enumerate(works):
        r = rests[i] if i < len(rests) else 0
        intervals.append({"work": w, "rest_s": r})
    return _finalize(None, None, intervals=intervals)


_DIST_SEGMENT = r"[\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b)"
_REST_SEGMENT = (
    r"" + _NUM_RE + r"\s*(?:" + _MIN_UNIT + r"|" + _SEC_UNIT + r")\s*rest\.?"
)


def _match_slash_variable_rest_chain(text: str):
    # Look for a slash-separated run alternating distance segments with
    # "N minutes/seconds rest" segments, e.g. "2000m/3 minutes
    # rest/1000m/2 minutes rest/500m": distance, (rest, distance)*.
    for candidate in re.finditer(
        r"(?:" + _DIST_SEGMENT + r")"
        r"(?:\s*/\s*(?:" + _REST_SEGMENT + r"|" + _DIST_SEGMENT + r"))+",
        text,
        re.IGNORECASE,
    ):
        segs = _SEGMENT_SPLIT_RE.split(candidate.group(0))
        result = _try_parse_variable_chain(segs)
        if result is not None:
            return result
    return None


# "3000m, 3 minutes rest, 10 minutes work" (comma separated, explicit
# 'work' suffix on later durations).
_COMMA_VARIABLE_CHAIN_RE = re.compile(
    r"([\d,]+(?:\.\d+)?\s*(?:k\b|m\b|meters?\b|meter\b))\s*,\s*"
    r"(" + _NUM_RE + r")\s*(" + _MIN_UNIT + r")\s*rest\s*,\s*"
    r"(" + _NUM_RE + r")\s*(" + _MIN_UNIT + r")\s*work",
    re.IGNORECASE,
)


def _match_comma_variable_chain(text: str):
    m = _COMMA_VARIABLE_CHAIN_RE.search(text)
    if not m:
        return None
    w1 = _parse_work_chunk(m.group(1))
    if w1 is None:
        return None
    r1 = _duration_words_to_seconds(m.group(2), m.group(3))
    w2_s = _to_int(m.group(4)) * 60
    intervals = [
        {"work": w1, "rest_s": r1},
        {"work": {"time_s": w2_s}, "rest_s": 0},
    ]
    return _finalize(None, None, intervals=intervals)


# --- Minute pyramids without slashes: "1 min, 2 min, 3 min, 4 min, 3
# min, 2 min, 1 min pyramid / 1 min easy" ------------------------------------

_COMMA_MIN_PYRAMID_RE = re.compile(
    r"((?:" + _NUM_RE + r"\s*" + _MIN_UNIT + r"\s*,\s*)+" + _NUM_RE + r"\s*" + _MIN_UNIT
    + r")\s*pyramid\s*/\s*(" + _NUM_RE + r")\s*" + _MIN_UNIT + r"\s*(?:easy|light|recovery|rest)",
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
        distance_positions = [
            i for i, iv in enumerate(intervals) if "distance_m" in iv["work"]
        ]
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

# Matchers tried in priority order (most specific first).
_MATCHERS = [
    _match_equal_work_and_rest,
    _match_comma_variable_chain,
    _match_slash_variable_rest_chain,
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
_OUTER_REPEAT_OF_RE = re.compile(
    r"\b(" + _NUM_RE + r")\s*(?:rounds?|sets?)\s+of\b", re.IGNORECASE
)

# Rest/chaining cue words. These are only disqualifying for a single_*
# result when they occur in the *same sentence* as a number+unit work
# token (see _sentence_disqualifies_single below) -- a lone cue word can
# be innocuous framing text in an unrelated sentence (e.g. "...taking
# place between March 6-10, 2024", "Then enter your result in the Online
# Ranking..."), so a whole-text word search alone is not reliable.
_REST_CUE_WORDS_RE = re.compile(
    r"\b(rest|easy|off|recovery|recover|light|between|on/off|then"
    r"|followed by|warmup|warm up|cool down)\b",
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


def _leftover_cue_guard(kind: str, clean_text: str) -> bool:
    """Return True if clean_text still carries a cue the matched kind
    cannot represent -- i.e. the spec must be discarded (never guess)."""
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
        return bool(_OUTER_REPEAT_OF_RE.search(clean_text))

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
    for matcher in _MATCHERS:
        spec = matcher(clean)
        if spec is not None:
            break

    if spec is None:
        spec = _match_single(clean)

    if spec is None:
        return None

    if _leftover_cue_guard(spec["kind"], clean):
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


def _run_coverage(path: str) -> None:
    import os

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

    out_dir = os.path.dirname(os.path.abspath(__file__))

    unparsed_path = os.path.join(out_dir, "spec_unparsed.md")
    with open(unparsed_path, "w") as f:
        f.write("# Unparsed rows\n\n")
        f.write(f"{len(unparsed)} of {total_rows} distinct rows did not parse.\n\n")
        for r in unparsed:
            f.write(
                f"- count={r.get('count', 1)} machines={r.get('machines')!r}\n"
                f"  title: {r.get('title', '')!r}\n"
                f"  description: {r.get('description', '')!r}\n\n"
            )

    parsed_path = os.path.join(out_dir, "spec_parsed.jsonl")
    with open(parsed_path, "w") as f:
        for row in parsed_out:
            f.write(json.dumps(row) + "\n")

    print(f"wrote {unparsed_path}")
    print(f"wrote {parsed_path}")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] == "--coverage":
        if len(argv) < 2:
            print("usage: spec.py --coverage <dataset.jsonl>", file=sys.stderr)
            return 2
        _run_coverage(argv[1])
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
