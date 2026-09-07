# Run from repo root: python3 -m unittest discover -s tests -t .
#
# Fully offline: the LLM path is always exercised via an injected
# extract_fn, never a real LLM backend or the pm5keys.llm subpackage
# (which is an optional extra and may not be installed).

import io
import json
import os
import unittest
from unittest import mock

from pm5keys import cli


def _no_backend_env():
    """Return an environment mapping guaranteed to make
    pm5keys.llm.resolve_backend('auto') fall through to NoneBackend:
    no ANTHROPIC_API_KEY, no PM5KEYS_CLAUDE_BIN, and a PATH that can't
    resolve a 'claude' binary."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("PM5KEYS_CLAUDE_BIN", None)
    env["PATH"] = "/nonexistent-bin-dir"
    return env


ANCHORS = [
    ("8 x 500m, 2 minutes rest", "B-2D-5A-2B-E"),
    (
        "1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest",
        "B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E",
    ),
    (
        "10/20/30/40/50/60 Calories. 1 minute rest between intervals.",
        "B-3D-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E",
    ),
]


class ExtractError(Exception):
    """Stand-in for pm5keys.llm.ExtractError, used only to exercise
    run()'s error handling without depending on the optional llm
    extra."""


class RunRulePathTest(unittest.TestCase):
    def test_anchors_via_rules(self):
        for text, gold_keys in ANCHORS:
            with self.subTest(text=text):
                result = cli.run(text, llm="none")
                self.assertEqual(result["keys"], gold_keys)
                self.assertEqual(result["source"], "rules")

    def test_no_llm_flag_never_calls_extractor(self):
        # If the rule parser handles it, llm='none' must still work
        # (the extractor is simply never invoked).
        called = []

        def fake_extract(text, model="sonnet"):
            called.append(text)
            raise AssertionError("extract_fn should not be called on the rule path")

        text, gold_keys = ANCHORS[0]
        result = cli.run(text, llm="none", extract_fn=fake_extract)
        self.assertEqual(result["keys"], gold_keys)
        self.assertEqual(called, [])


class RunLlmFallbackTest(unittest.TestCase):
    def test_llm_used_only_when_rules_fail(self):
        text = "four hard 500s with 90 seconds off"
        fake_spec = {
            "machine": "rower",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 90,
            "count": 4,
            "notes": "hard",
        }
        calls = []

        def fake_extract(t, model="sonnet"):
            calls.append((t, model))
            return fake_spec

        result = cli.run(text, llm="auto", model="sonnet", extract_fn=fake_extract)
        self.assertEqual(result["source"], "llm")
        self.assertEqual(calls, [(text, "sonnet")])
        self.assertTrue(result["keys"])  # compiled successfully

    def test_extract_error_propagates_as_wod2keys_error(self):
        def fake_extract(t, model="sonnet"):
            raise ExtractError("boom: no valid spec")

        with self.assertRaises(cli.Wod2KeysError) as ctx:
            cli.run("some unparseable free-form text with no rule match", extract_fn=fake_extract)
        self.assertIn("boom: no valid spec", str(ctx.exception))

    def test_llm_unavailable_exits_with_install_hint(self):
        # No extract_fn given and no backend resolves (no key, no
        # claude-cli): run() must surface the install/enable hint
        # rather than an ImportError/traceback.
        text = "some unparseable free-form text with no rule match"
        with mock.patch.dict(os.environ, _no_backend_env(), clear=True):
            with self.assertRaises(cli.Wod2KeysError) as ctx:
                cli.run(text, llm="auto")
        message = str(ctx.exception)
        self.assertIn("unparsed", message)
        self.assertIn("pm5keys[llm]", message)
        self.assertIn("ANTHROPIC_API_KEY", message)
        self.assertIn("--llm claude-cli", message)


class RunErrorCasesTest(unittest.TestCase):
    def test_empty_input_raises(self):
        with self.assertRaises(cli.Wod2KeysError):
            cli.run("")

    def test_whitespace_only_input_raises(self):
        with self.assertRaises(cli.Wod2KeysError):
            cli.run("   \n  ")

    def test_unparsed_with_no_llm_message(self):
        with self.assertRaises(cli.Wod2KeysError) as ctx:
            cli.run("some free-form text nobody could parse as a workout", llm="none")
        message = str(ctx.exception)
        self.assertIn("unparsed", message)
        self.assertIn("--llm anthropic", message)
        self.assertIn("--llm claude-cli", message)


class MainCliTest(unittest.TestCase):
    def _run_main(self, argv, stdin_text=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            if stdin_text is not None:
                with mock.patch("sys.stdin", io.StringIO(stdin_text)):
                    code = cli.main(argv)
            else:
                code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_anchor_no_llm_cli(self):
        text, gold_keys = ANCHORS[0]
        code, out, err = self._run_main([text, "--no-llm"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], text)
        self.assertEqual(lines[1], f"PM5: {gold_keys}")

    def test_stdin_input(self):
        text, gold_keys = ANCHORS[0]
        code, out, err = self._run_main(["--no-llm"], stdin_text=text)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], text)
        self.assertEqual(lines[1], f"PM5: {gold_keys}")

    def test_no_llm_free_form_exits_2_with_message(self):
        code, out, err = self._run_main(
            ["some free-form text nobody could parse as a workout", "--no-llm"]
        )
        self.assertEqual(code, 2)
        self.assertIn("unparsed", err)
        self.assertIn("--llm anthropic", err)
        self.assertIn("--llm claude-cli", err)
        self.assertEqual(out, "")

    def test_llm_none_flag_equivalent_to_no_llm(self):
        code, out, err = self._run_main(
            ["some free-form text nobody could parse as a workout", "--llm", "none"]
        )
        self.assertEqual(code, 2)
        self.assertIn("unparsed", err)
        self.assertEqual(out, "")

    def test_empty_input_exits_2(self):
        code, out, err = self._run_main(["--no-llm"], stdin_text="")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")

    def test_llm_unavailable_exits_2_with_install_hint(self):
        with mock.patch.dict(os.environ, _no_backend_env(), clear=True):
            code, out, err = self._run_main(["four hard 500s with 90 seconds off"])
        self.assertEqual(code, 2)
        self.assertIn("unparsed", err)
        self.assertIn("pm5keys[llm]", err)
        self.assertIn("ANTHROPIC_API_KEY", err)
        self.assertEqual(out, "")

    def test_llm_anthropic_without_key_exits_2_naming_env_var_sdk_present(self):
        # anthropic SDK importable (as in the repo .venv), key absent:
        # stderr must still name ANTHROPIC_API_KEY.
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            code, out, err = self._run_main(
                ["four hard 500s with 90 seconds off", "--llm", "anthropic"]
            )
        self.assertEqual(code, 2)
        self.assertIn("ANTHROPIC_API_KEY", err)
        self.assertEqual(out, "")

    def test_llm_anthropic_without_key_exits_2_naming_env_var_sdk_absent(self):
        # anthropic SDK NOT importable (as in a `pip install .[dev]`-only
        # venv, which is what CI installs), key also absent: stderr must
        # still name ANTHROPIC_API_KEY, not just the install hint.
        import sys

        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            with mock.patch.dict(os.environ, env, clear=True):
                code, out, err = self._run_main(
                    ["four hard 500s with 90 seconds off", "--llm", "anthropic"]
                )
        self.assertEqual(code, 2)
        self.assertIn("ANTHROPIC_API_KEY", err)
        self.assertEqual(out, "")

    def test_verbose_prints_spec_and_source_to_stderr(self):
        text, gold_keys = ANCHORS[0]
        code, out, err = self._run_main([text, "--no-llm", "--verbose"])
        self.assertEqual(code, 0)
        self.assertIn("source: rules", err)
        # spec JSON should be valid JSON containing the expected kind.
        json_part = err.split("source: rules")[0]
        spec = json.loads(json_part)
        self.assertEqual(spec["kind"], "intervals_distance")

    def test_explain_output_starts_with_b_and_one_line_per_group(self):
        text, gold_keys = ANCHORS[0]
        code, out, err = self._run_main([text, "--no-llm", "--explain"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        # First two lines are title + PM5:, remaining are explain lines.
        explain_lines = lines[2:]
        self.assertTrue(len(explain_lines) >= 1)
        self.assertTrue(explain_lines[0].lstrip().startswith("B"))
        for line in explain_lines:
            self.assertIn(": ", line)
        # The rest-minutes cursor moves (4xA) and rest-minutes +1 edits
        # (2xB) collapse per the coordinator's required shape.
        self.assertTrue(
            any("4xA" in line and "cursor right to rest minutes" in line for line in explain_lines)
        )
        self.assertTrue(
            any("2xB" in line and "rest minutes +2 (now 2)" in line for line in explain_lines)
        )

    def test_title_whitespace_normalisation(self):
        text = "8   x    500m,\t2 minutes   rest"
        code, out, err = self._run_main([text, "--no-llm"])
        self.assertEqual(code, 0)
        title_line = out.splitlines()[0]
        self.assertEqual(title_line, "8 x 500m, 2 minutes rest")

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run_main(["--version"])
        self.assertEqual(ctx.exception.code, 0)


class MonitorFlagCliTest(unittest.TestCase):
    """--monitor {pm5,pm3,pm4,both} CLI behaviour."""

    # Anchor also used in ANCHORS[0], with its pm34 (PM3/PM4) sequence
    # reproduced from data/dataset.jsonl / the fastmail-808.12 brief.
    PM34_ANCHOR_KEYS = "B-D-C-4A-2B-E"  # "8 x 500m, 2 minutes rest"

    def _run_main(self, argv, stdin_text=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            if stdin_text is not None:
                with mock.patch("sys.stdin", io.StringIO(stdin_text)):
                    code = cli.main(argv)
            else:
                code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_monitor_pm3_prints_pm34_line(self):
        text, _pm5_keys = ANCHORS[0]
        code, out, err = self._run_main([text, "--no-llm", "--monitor", "pm3"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], text)
        self.assertEqual(lines[1], f"PM3/PM4: {self.PM34_ANCHOR_KEYS}")
        self.assertEqual(len(lines), 2)

    def test_monitor_pm4_is_an_alias_of_pm3(self):
        text, _pm5_keys = ANCHORS[0]
        code_pm3, out_pm3, _err_pm3 = self._run_main([text, "--no-llm", "--monitor", "pm3"])
        code_pm4, out_pm4, _err_pm4 = self._run_main([text, "--no-llm", "--monitor", "pm4"])
        self.assertEqual(code_pm3, 0)
        self.assertEqual(code_pm4, 0)
        self.assertEqual(out_pm3, out_pm4)

    def test_monitor_both_prints_pm34_line_first_then_pm5(self):
        text, pm5_keys = ANCHORS[0]
        code, out, err = self._run_main([text, "--no-llm", "--monitor", "both"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], text)
        self.assertEqual(lines[1], f"PM3/PM4: {self.PM34_ANCHOR_KEYS}")
        self.assertEqual(lines[2], f"PM5: {pm5_keys}")
        self.assertEqual(len(lines), 3)

    def test_monitor_both_explain_prints_both_traces_with_headings(self):
        code, out, err = self._run_main(["2000m", "--no-llm", "--monitor", "both", "--explain"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("PM3/PM4:", lines)
        self.assertIn("PM5:", lines)
        # The PM3/PM4 heading must come before the PM5 heading.
        self.assertLess(lines.index("PM3/PM4:"), lines.index("PM5:"))

    def test_monitor_pm5_default_unaffected(self):
        text, pm5_keys = ANCHORS[0]
        code, out, err = self._run_main([text, "--no-llm"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[1], f"PM5: {pm5_keys}")
        self.assertEqual(len(lines), 2)

    def test_monitor_pm3_calorie_workout_exits_2(self):
        code, out, err = self._run_main(["250 Calories", "--no-llm", "--monitor", "pm3"])
        self.assertEqual(code, 2)
        self.assertIn("PM3/PM4", err)
        self.assertIn("calorie", err.lower())
        self.assertEqual(out, "")

    def test_monitor_pm4_calorie_workout_exits_2(self):
        code, out, err = self._run_main(["250 Calories", "--no-llm", "--monitor", "pm4"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")

    def test_monitor_both_calorie_workout_prints_pm5_and_not_supported_line(self):
        code, out, err = self._run_main(["250 Calories", "--no-llm", "--monitor", "both"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "250 Calories")
        self.assertIn("PM3/PM4: not supported (calorie workouts)", lines)
        self.assertTrue(any(line.startswith("PM5: ") for line in lines))
        # PM3/PM4 line still comes first.
        pm34_idx = next(i for i, line in enumerate(lines) if line.startswith("PM3/PM4:"))
        pm5_idx = next(i for i, line in enumerate(lines) if line.startswith("PM5:"))
        self.assertLess(pm34_idx, pm5_idx)

    def test_invalid_monitor_choice_rejected_by_argparse(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run_main(["2000m", "--no-llm", "--monitor", "pm2"])
        self.assertNotEqual(ctx.exception.code, 0)


class FormatExplainTest(unittest.TestCase):
    def test_does_not_collapse_unrelated_same_letter_actions(self):
        # Same press letter, but different screens -- must not collapse.
        trace = [
            ("B", "Main Menu", "Select Workout"),
            ("B", "Select Workout", "New Workout"),
        ]
        lines = cli._format_explain(trace)
        self.assertEqual(len(lines), 2)

    def test_collapses_cursor_moves_showing_last_destination(self):
        trace = [
            ("A", "Intervals: Distance", "cursor right to distance 10s digit"),
            ("A", "Intervals: Distance", "cursor right to distance 1s digit"),
            ("A", "Intervals: Distance", "cursor right to rest 10-minutes"),
            ("A", "Intervals: Distance", "cursor right to rest minutes"),
        ]
        lines = cli._format_explain(trace)
        self.assertEqual(len(lines), 1)
        self.assertIn("4xA", lines[0])
        self.assertIn("cursor right to rest minutes", lines[0])

    def test_collapses_digit_edits_summing_delta_and_showing_last_value(self):
        trace = [
            ("B", "Intervals: Distance", "rest minutes +1 (now 1)"),
            ("B", "Intervals: Distance", "rest minutes +1 (now 2)"),
        ]
        lines = cli._format_explain(trace)
        self.assertEqual(len(lines), 1)
        self.assertIn("2xB", lines[0])
        self.assertIn("rest minutes +2 (now 2)", lines[0])

    def test_does_not_collapse_digit_edits_across_different_fields(self):
        trace = [
            ("B", "Intervals: Distance", "distance 100s digit +1 (now 1)"),
            ("B", "Intervals: Distance", "rest minutes +1 (now 1)"),
        ]
        lines = cli._format_explain(trace)
        self.assertEqual(len(lines), 2)

    def test_does_not_collapse_across_confirm_or_screen_change(self):
        trace = [
            ("E", "Intervals: Distance", "confirm"),
            ("E", "Intervals: Variable", "finish workout"),
        ]
        lines = cli._format_explain(trace)
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
