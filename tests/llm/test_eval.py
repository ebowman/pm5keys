# Run from repo root: python -m unittest discover -s tests -t .
#
# All backend calls go through FakeBackend/mocked subprocess.run --
# this suite never actually shells out to `claude` or reaches a real
# HTTP endpoint.

import json
import os
import tempfile
import unittest
from unittest import mock

from pm5keys.llm import eval_direct as ed
from pm5keys.llm import eval_extract as ee


SIMPLE_POOL_DIRECT = [
    {
        "title": "8 x 500m, 2 minutes rest",
        "description": "8 x 500m intervals with 2 minutes rest.",
        "pm5": "B-D-A-3B-2D-5A-2B-E",
    },
    {
        "title": "30 minutes",
        "description": "A steady 30 minute row.",
        "pm5": "B-D-C-A-3B-E",
    },
]


class FakeBackend:
    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, prompt, model):
        self.calls.append((prompt, model))
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# eval_direct.py
# ---------------------------------------------------------------------------


class DirectBuildExamplesTest(unittest.TestCase):
    def test_ranks_by_title_similarity(self):
        examples = ed.build_examples("8 x 500m, 90 seconds rest", SIMPLE_POOL_DIRECT, k=1)
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["title"], "8 x 500m, 2 minutes rest")

    def test_respects_k(self):
        examples = ed.build_examples("some text", SIMPLE_POOL_DIRECT, k=1)
        self.assertEqual(len(examples), 1)


class DirectPromptAssemblyTest(unittest.TestCase):
    def test_prompt_includes_legend_examples_and_workout(self):
        prompt = ed.build_prompt("a steady 5k", "5000m for time", SIMPLE_POOL_DIRECT, k=2)
        self.assertIn("Legend", prompt)
        self.assertIn("Grammar", prompt)
        self.assertIn("Workout: 8 x 500m, 2 minutes rest", prompt)
        self.assertIn("PM5: B-D-A-3B-2D-5A-2B-E", prompt)
        self.assertIn("Workout: 30 minutes", prompt)
        self.assertIn("PM5: B-D-C-A-3B-E", prompt)
        self.assertIn("Workout: a steady 5k. 5000m for time", prompt)
        self.assertIn("sequence only", prompt.lower())

    def test_prompt_uses_k_examples_only(self):
        prompt = ed.build_prompt("8 x 500m, 90 seconds rest", "", SIMPLE_POOL_DIRECT, k=1)
        self.assertIn("Workout: 8 x 500m, 2 minutes rest", prompt)
        self.assertNotIn("Workout: 30 minutes", prompt)


class ExtractAnswerTest(unittest.TestCase):
    def test_plain_pm5_prefixed_answer(self):
        self.assertEqual(ed.extract_answer("PM5: B-2D-5A-2B-E"), "B-2D-5A-2B-E")

    def test_plain_answer_no_prefix(self):
        self.assertEqual(ed.extract_answer("B-2D-5A-2B-E"), "B-2D-5A-2B-E")

    def test_fenced_answer(self):
        raw = "```\nPM5: B-2D-5A-2B-E\n```"
        self.assertEqual(ed.extract_answer(raw), "B-2D-5A-2B-E")

    def test_fenced_answer_with_language_tag(self):
        raw = "```text\nB-2D-5A-2B-E\n```"
        self.assertEqual(ed.extract_answer(raw), "B-2D-5A-2B-E")

    def test_answer_with_trailing_prose(self):
        raw = "PM5: B-2D-5A-2B-E\n\nThis programs the workout as requested."
        self.assertEqual(ed.extract_answer(raw), "B-2D-5A-2B-E")

    def test_answer_with_leading_prose(self):
        raw = "Here is the sequence:\nB-2D-5A-2B-E"
        self.assertEqual(ed.extract_answer(raw), "B-2D-5A-2B-E")

    def test_garbage_returns_none(self):
        self.assertIsNone(ed.extract_answer("I cannot determine this workout."))

    def test_empty_returns_none(self):
        self.assertIsNone(ed.extract_answer(""))

    def test_none_returns_none(self):
        self.assertIsNone(ed.extract_answer(None))


class ScorePredictionTest(unittest.TestCase):
    def setUp(self):
        self.gold = "B-D-A-E"

    def test_exact_match(self):
        result = ed.score_prediction("B-D-A-E", self.gold)
        self.assertFalse(result["unparsable"])
        self.assertTrue(result["exact"])
        self.assertTrue(result["semantic"])

    def test_exact_match_after_canonicalisation(self):
        from pm5keys import keyseq

        gold = "B-D-A-2B-E"
        pred = "B-D-A-B-B-E"
        self.assertEqual(keyseq.canonical(pred), keyseq.canonical(gold))
        result = ed.score_prediction(pred, gold)
        self.assertTrue(result["exact"])

    def test_semantic_and_exact_both_false_on_mismatch(self):
        pred = "B-D-A-C-E"
        result = ed.score_prediction(pred, self.gold)
        self.assertFalse(result["exact"])
        self.assertFalse(result["semantic"])

    def test_unparsable_none_prediction(self):
        result = ed.score_prediction(None, self.gold)
        self.assertTrue(result["unparsable"])
        self.assertFalse(result["exact"])
        self.assertFalse(result["semantic"])

    def test_unparsable_invalid_sequence(self):
        result = ed.score_prediction("not-a-sequence!!", self.gold)
        self.assertTrue(result["unparsable"])
        self.assertFalse(result["exact"])
        self.assertFalse(result["semantic"])

    def test_unparsable_empty_string(self):
        result = ed.score_prediction("", self.gold)
        self.assertTrue(result["unparsable"])

    def test_valid_but_unsimulatable_prediction_not_semantic(self):
        pred = "E"
        result = ed.score_prediction(pred, self.gold)
        self.assertFalse(result["unparsable"])
        self.assertFalse(result["exact"])
        self.assertFalse(result["semantic"])


class ScorePipelineRowTest(unittest.TestCase):
    def test_pipeline_scores_deterministic_row(self):
        row = {
            "title": "8 x 500m, 2 minutes rest",
            "description": "8 x 500m intervals with 2 minutes rest.",
            "pm5": "B-4D-5A-2B-2C-E",
        }
        result = ed.score_pipeline_row(row)
        self.assertIn("exact", result)
        self.assertIn("semantic", result)
        self.assertIn("compiled", result)
        self.assertIsInstance(result["exact"], bool)
        self.assertIsInstance(result["semantic"], bool)

    def test_pipeline_unparsable_text_yields_false_false_none(self):
        row = {
            "title": "some totally ambiguous nonsense workout description",
            "description": "",
            "pm5": "B-D-A-E",
        }
        result = ed.score_pipeline_row(row)
        self.assertFalse(result["exact"])
        self.assertFalse(result["semantic"])
        self.assertIsNone(result["compiled"])


class DirectRunEvalTest(unittest.TestCase):
    def test_run_eval_end_to_end_with_fake_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            eval_path = os.path.join(tmp, "eval.jsonl")
            train_path = os.path.join(tmp, "train.jsonl")

            eval_rows = [
                {
                    "title": "8 x 500m, 2 minutes rest",
                    "description": "8 x 500m intervals with 2 minutes rest.",
                    "machines": "RowErg and SkiErg",
                    "pm5": "B-D-A-E",
                },
                {
                    "title": "a bike workout",
                    "description": "should be excluded",
                    "machines": "BikeErg",
                    "pm5": "B-D-A-E",
                },
            ]
            train_rows = [
                {
                    "title": "8 x 500m, 2 minutes rest",
                    "description": "8 x 500m intervals with 2 minutes rest.",
                    "machines": "RowErg and SkiErg",
                    "pm5": "B-D-A-3B-2D-5A-2B-E",
                },
                {
                    "title": "a bike only example",
                    "description": "excluded from pool",
                    "machines": "BikeErg",
                    "pm5": "B-D-A-E",
                },
            ]
            with open(eval_path, "w", encoding="utf-8") as f:
                for row in eval_rows:
                    f.write(json.dumps(row) + "\n")
            with open(train_path, "w", encoding="utf-8") as f:
                for row in train_rows:
                    f.write(json.dumps(row) + "\n")

            with mock.patch.object(ed, "resolve_backend", return_value=FakeBackend(["PM5: B-D-A-E"])):
                results = ed.run_eval(
                    eval_path,
                    train_path,
                    limit=None,
                    backend_name="claude-cli",
                    model="sonnet",
                    k=5,
                    cache_dir=None,
                )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "8 x 500m, 2 minutes rest")
            self.assertTrue(results[0]["llm"]["exact"])

    def test_summarize_counts(self):
        results = [
            {"llm": {"exact": True, "semantic": True, "unparsable": False}, "pipeline": {"exact": True, "semantic": True}},
            {"llm": {"exact": False, "semantic": True, "unparsable": False}, "pipeline": {"exact": False, "semantic": True}},
            {"llm": {"exact": False, "semantic": False, "unparsable": True}, "pipeline": {"exact": False, "semantic": False}},
        ]
        summary = ed.summarize(results)
        self.assertEqual(summary["n"], 3)
        self.assertEqual(summary["llm_exact"], 1)
        self.assertEqual(summary["llm_semantic"], 2)
        self.assertEqual(summary["llm_unparsable"], 1)
        self.assertEqual(summary["pipeline_exact"], 1)
        self.assertEqual(summary["pipeline_semantic"], 2)


# ---------------------------------------------------------------------------
# eval_extract.py
# ---------------------------------------------------------------------------


class BuildPoolExcludingTest(unittest.TestCase):
    def test_excludes_eval_row_identities(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset_path = os.path.join(tmp, "dataset_unique.jsonl")
            dataset_rows = [
                {
                    "title": "8 x 500m, 2 minutes rest",
                    "description": "8 x 500m intervals with 2 minutes rest.",
                    "machines": "RowErg and SkiErg",
                },
                {
                    "title": "a steady 5k",
                    "description": "5000m steady.",
                    "machines": "All Machines",
                },
            ]
            with open(dataset_path, "w", encoding="utf-8") as f:
                for row in dataset_rows:
                    f.write(json.dumps(row) + "\n")

            eval_rows = [dataset_rows[0]]
            pool = ee.build_pool_excluding(eval_rows, dataset_path=dataset_path)
            titles = {e["title"] for e in pool if e["title"]}
            self.assertNotIn("8 x 500m, 2 minutes rest", titles)
            self.assertIn("a steady 5k", titles)


class EvalExtractRunEvalTest(unittest.TestCase):
    def test_run_eval_excludes_bikeerg_and_scores_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            eval_path = os.path.join(tmp, "eval.jsonl")
            dataset_path = os.path.join(tmp, "dataset_unique.jsonl")

            eval_rows = [
                {
                    "title": "a steady 5k",
                    "description": "5000m steady.",
                    "machines": "All Machines",
                    "pm5": "B-D-A-3B-E",
                },
                {
                    "title": "a bike workout",
                    "description": "excluded",
                    "machines": "BikeErg",
                    "pm5": "B-D-A-E",
                },
            ]
            with open(eval_path, "w", encoding="utf-8") as f:
                for row in eval_rows:
                    f.write(json.dumps(row) + "\n")
            with open(dataset_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(eval_rows[0]) + "\n")

            good_spec = json.dumps(
                {"kind": "single_distance", "work": {"distance_m": 5000}, "notes": "steady"}
            )
            fake_extract = mock.Mock(return_value=json.loads(good_spec) | {"machine": "rower"})

            # Patch the name where eval_extract.py actually looks it up:
            # `from .extract import ... extract_spec` binds `extract_spec`
            # directly into the eval_extract module's namespace, so
            # patching 'pm5keys.llm.extract.extract_spec' (the source
            # module) has no effect on eval_extract's local binding --
            # it must be patched as `ee.extract_spec`.
            with mock.patch.object(ee, "DEFAULT_DATASET_PATH", dataset_path):
                with mock.patch.object(ee, "extract_spec", fake_extract):
                    rows, results = ee.run_eval(eval_path, None, "claude-cli", None, 5, None)

            self.assertEqual(fake_extract.call_count, 1)
            called_text = fake_extract.call_args.args[0]
            self.assertEqual(called_text, "a steady 5k. 5000m steady.")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "a steady 5k")
            self.assertTrue(results[0]["correct"])


if __name__ == "__main__":
    unittest.main()
