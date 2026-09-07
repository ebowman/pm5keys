# Runs inside Pyodide. Mirrors pm5keys.cli.run()'s monitor-selection
# and calorie-on-PM3/PM4 handling, but returns a JSON-able dict instead
# of printing to stdout/exiting, since this is called from JS via
# generate(text, monitor).
import json

from pm5keys import compile_keys
from pm5keys import pm5_model as pm5
from pm5keys.spec import parse_spec

_MONITOR_LINE_LABEL = {"pm5": "PM5", "pm3": "PM3/PM4", "pm4": "PM3/PM4"}
_CALORIE_KINDS = ("single_calorie", "intervals_calorie")

_UNPARSED_HINT = (
    "unparsed: rules could not parse this text; free-form text like this "
    "needs the CLI with an LLM backend (pip install pm5keys[llm] and "
    "pm5keys --llm anthropic/claude-cli) -- there is no LLM in this "
    "browser demo"
)


def generate(text, monitor):
    """Parse `text` and compile it for `monitor` ('pm5', 'pm3', 'pm4',
    or 'both'). Returns a JSON string: {ok, lines, explains: {pm5:
    [[press, screen, action], ...], pm3: [...]}, error}."""
    result = {"ok": False, "lines": [], "explains": {"pm5": [], "pm3": []}, "error": None}

    if not text or not text.strip():
        result["error"] = "empty input"
        return json.dumps(result)

    spec = parse_spec(text, None)
    if spec is None:
        result["error"] = _UNPARSED_HINT
        return json.dumps(result)

    spec = dict(spec)
    spec["machine"] = "rower"

    if monitor == "both":
        target_monitors = ["pm3", "pm5"]
    else:
        target_monitors = [monitor]

    lines = []
    explains = {"pm5": [], "pm3": []}

    for target in target_monitors:
        try:
            keys = compile_keys.compile(spec, monitor=target)
        except (ValueError, NotImplementedError) as exc:
            if monitor == "both" and target == "pm3" and spec.get("kind") in _CALORIE_KINDS:
                lines.append("PM3/PM4: not supported (calorie workouts)")
                continue
            result["error"] = str(exc)
            return json.dumps(result)

        label = _MONITOR_LINE_LABEL[target]
        lines.append(f"{label}: {keys}")
        trace = pm5.explain(keys, monitor=target)
        explain_key = "pm5" if target == "pm5" else "pm3"
        explains[explain_key] = [list(t) for t in trace]

    result["ok"] = True
    result["lines"] = lines
    result["explains"] = explains
    return json.dumps(result)
