# Run from repo root: python -m unittest discover -s tests -t .
#
# The Backend passed to extract_spec is always a fake/mock in this
# module -- no real subprocess, HTTP client, or the real `claude`/
# `anthropic` backend is ever exercised.

import json
import os
import tempfile
import unittest
from unittest import mock

from pm5keys.llm import extract as ex
from pm5keys.llm.backends import ExtractError


SIMPLE_POOL = [
    {
        "title": "8 x 500m, 2 minutes rest",
        "description": "8 x 500m intervals with 2 minutes rest.",
        "text": "8 x 500m, 2 minutes rest. 8 x 500m intervals with 2 minutes rest.",
        "spec": {
            "machine": "rower",
            "kind": "intervals_distance",
            "work": {"distance_m": 500},
            "rest_s": 120,
            "count": 8,
            "notes": "",
        },
    },
    {
        "title": "30 minutes",
        "description": "A steady 30 minute row.",
        "text": "30 minutes. A steady 30 minute row.",
        "spec": {
            "machine": "rower",
            "kind": "single_time",
            "work": {"time_s": 1800},
            "notes": "",
        },
    },
]


class FakeBackend:
    """A Backend stand-in whose complete() returns a queued sequence of
    responses (or a fixed one), and records every prompt/model it was
    called with."""

    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, prompt, model):
        self.calls.append((prompt, model))
        return self._responses.pop(0)


class BuildExamplesTest(unittest.TestCase):
    def test_ranks_by_title_similarity(self):
        examples = ex.build_examples("8 x 500m, 90 seconds rest", SIMPLE_POOL, k=1)
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["title"], "8 x 500m, 2 minutes rest")

    def test_respects_k(self):
        examples = ex.build_examples("some text", SIMPLE_POOL, k=1)
        self.assertEqual(len(examples), 1)

    def test_falls_back_to_description_when_title_empty(self):
        pool = [
            {
                "title": "",
                "description": "8 x 500m intervals with 2 minutes rest.",
                "text": "x",
                "spec": SIMPLE_POOL[0]["spec"],
            }
        ]
        examples = ex.build_examples("8 x 500m intervals with 2 minutes rest", pool, k=1)
        self.assertEqual(len(examples), 1)


class PromptTemplateContentTest(unittest.TestCase):
    def test_prompt_template_has_nested_repeat_unroll_rule(self):
        template = ex._load_prompt_template()
        self.assertIn("Nested repeats", template)
        self.assertIn("unroll", template.lower())
        self.assertIn("between-rounds rest", template)


class PromptAssemblyTest(unittest.TestCase):
    def test_prompt_includes_schema_examples_and_text(self):
        prompt = ex.build_prompt("a steady 5k", SIMPLE_POOL, k=2)
        self.assertIn("distance_m", prompt)
        self.assertIn("8 x 500m, 2 minutes rest", prompt)
        self.assertIn(json.dumps(SIMPLE_POOL[0]["spec"]), prompt)
        self.assertIn("30 minutes", prompt)
        self.assertIn("Text: a steady 5k", prompt)

    def test_prompt_uses_k_examples_only(self):
        prompt = ex.build_prompt("8 x 500m, 90 seconds rest", SIMPLE_POOL, k=1)
        self.assertIn("8 x 500m, 2 minutes rest", prompt)
        self.assertNotIn(json.dumps(SIMPLE_POOL[1]["spec"]), prompt)


class ResponseParsingTest(unittest.TestCase):
    def test_strips_code_fences(self):
        raw = (
            "```json\n"
            + json.dumps({"kind": "single_distance", "work": {"distance_m": 2000}, "notes": ""})
            + "\n```"
        )
        spec = ex._parse_response(raw)
        self.assertEqual(spec["kind"], "single_distance")
        self.assertEqual(spec["machine"], "rower")

    def test_error_json_raises_extract_error(self):
        raw = json.dumps({"error": "no rest duration given"})
        with self.assertRaises(ExtractError):
            ex._parse_response(raw)

    def test_machine_forced_to_rower(self):
        raw = json.dumps(
            {
                "machine": "bikeerg",
                "kind": "single_distance",
                "work": {"distance_m": 2000},
                "notes": "",
            }
        )
        spec = ex._parse_response(raw)
        self.assertEqual(spec["machine"], "rower")

    def test_invalid_spec_raises_value_error(self):
        raw = json.dumps({"kind": "single_distance", "work": {}, "notes": ""})
        with self.assertRaises(ValueError):
            ex._parse_response(raw)


class ExtractSpecTest(unittest.TestCase):
    def test_happy_path_no_retry(self):
        good_spec = {
            "kind": "single_distance",
            "work": {"distance_m": 5000},
            "notes": "steady",
        }
        backend = FakeBackend([json.dumps(good_spec)])
        result = ex.extract_spec(
            "a steady 5k", backend=backend, model="sonnet", k=2, cache_dir=None, pool=SIMPLE_POOL
        )
        self.assertEqual(result["kind"], "single_distance")
        self.assertEqual(result["machine"], "rower")
        self.assertEqual(len(backend.calls), 1)

    def test_error_json_raises_extract_error_no_retry(self):
        backend = FakeBackend([json.dumps({"error": "missing rest duration"})])
        with self.assertRaises(ExtractError):
            ex.extract_spec(
                "some text", backend=backend, model="sonnet", k=2, cache_dir=None, pool=SIMPLE_POOL
            )
        self.assertEqual(len(backend.calls), 1)

    def test_invalid_then_valid_retries_once(self):
        bad_spec = json.dumps({"kind": "single_distance", "work": {}, "notes": ""})
        good_spec = json.dumps(
            {"kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""}
        )
        backend = FakeBackend([bad_spec, good_spec])
        result = ex.extract_spec(
            "a steady 5k", backend=backend, model="sonnet", k=2, cache_dir=None, pool=SIMPLE_POOL
        )
        self.assertEqual(result["work"], {"distance_m": 5000})
        self.assertEqual(len(backend.calls), 2)
        retry_prompt = backend.calls[1][0]
        self.assertIn("Your previous answer was invalid", retry_prompt)

    def test_invalid_twice_raises_after_retry(self):
        bad_spec = json.dumps({"kind": "single_distance", "work": {}, "notes": ""})
        backend = FakeBackend([bad_spec, bad_spec])
        with self.assertRaises(ExtractError):
            ex.extract_spec(
                "some text", backend=backend, model="sonnet", k=2, cache_dir=None, pool=SIMPLE_POOL
            )
        self.assertEqual(len(backend.calls), 2)

    def test_malformed_json_then_valid_retries_once(self):
        good_spec = json.dumps(
            {"kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""}
        )
        backend = FakeBackend(["not json at all", good_spec])
        result = ex.extract_spec(
            "a steady 5k", backend=backend, model="sonnet", k=2, cache_dir=None, pool=SIMPLE_POOL
        )
        self.assertEqual(result["work"], {"distance_m": 5000})
        self.assertEqual(len(backend.calls), 2)

    def test_backend_name_string_resolved_via_resolve_backend(self):
        good_spec = json.dumps(
            {"kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""}
        )
        with mock.patch("subprocess.run") as run_mock:
            run_mock.return_value = mock.Mock(
                stdout=json.dumps({"result": good_spec, "is_error": False}),
                stderr="",
                returncode=0,
            )
            result = ex.extract_spec(
                "a steady 5k",
                backend="claude-cli",
                model="sonnet",
                k=2,
                cache_dir=None,
                pool=SIMPLE_POOL,
            )
        self.assertEqual(result["work"], {"distance_m": 5000})

    def test_none_backend_raises_llm_disabled(self):
        with self.assertRaises(ExtractError) as ctx:
            ex.extract_spec("some text", backend="none", cache_dir=None, pool=SIMPLE_POOL)
        self.assertIn("LLM disabled", str(ctx.exception))


class CacheTest(unittest.TestCase):
    def test_cache_hit_avoids_backend_call(self):
        good_spec = json.dumps(
            {"kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""}
        )
        with tempfile.TemporaryDirectory() as tmp:
            backend = FakeBackend([good_spec])
            ex.extract_spec(
                "a steady 5k", backend=backend, model="sonnet", k=2, cache_dir=tmp, pool=SIMPLE_POOL
            )
            self.assertEqual(len(backend.calls), 1)

            backend2 = FakeBackend([])  # would raise IndexError if called
            ex.extract_spec(
                "a steady 5k",
                backend=backend2,
                model="sonnet",
                k=2,
                cache_dir=tmp,
                pool=SIMPLE_POOL,
            )
            self.assertEqual(len(backend2.calls), 0)

    def test_cache_key_depends_on_backend_name_and_model_and_prompt(self):
        key1 = ex._cache_key("claude-cli", "sonnet", "prompt a")
        key2 = ex._cache_key("anthropic", "sonnet", "prompt a")
        key3 = ex._cache_key("claude-cli", "opus", "prompt a")
        key4 = ex._cache_key("claude-cli", "sonnet", "prompt b")
        self.assertEqual(len({key1, key2, key3, key4}), 4)

    def test_default_cache_dir_uses_xdg_cache_home(self):
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": "/tmp/xdgcache"}):
            self.assertEqual(ex._default_cache_dir(), "/tmp/xdgcache/pm5keys")

    def test_default_cache_dir_falls_back_to_home_cache(self):
        env = dict(os.environ)
        env.pop("XDG_CACHE_HOME", None)
        with mock.patch.dict(os.environ, env, clear=True):
            expected = os.path.join(os.path.expanduser("~"), ".cache", "pm5keys")
            self.assertEqual(ex._default_cache_dir(), expected)

    def test_no_cache_dir_calls_backend_every_time(self):
        good_spec = json.dumps(
            {"kind": "single_distance", "work": {"distance_m": 5000}, "notes": ""}
        )
        backend = FakeBackend([good_spec, good_spec])
        ex.extract_spec("a steady 5k", backend=backend, cache_dir=None, pool=SIMPLE_POOL)
        ex.extract_spec("a steady 5k", backend=backend, cache_dir=None, pool=SIMPLE_POOL)
        self.assertEqual(len(backend.calls), 2)


class LoadPoolTest(unittest.TestCase):
    def test_excludes_bikeerg_rows(self):
        rows = [
            {"title": "a bike row", "description": "", "machines": "BikeErg"},
            {
                "title": "8 x 500m, 2 minutes rest",
                "description": "8 x 500m intervals with 2 minutes rest.",
                "machines": "RowErg and SkiErg",
            },
        ]
        pool = ex.load_pool(rows=rows)
        titles = {e["title"] for e in pool if e["title"]}
        self.assertNotIn("a bike row", titles)

    def test_includes_handwritten_examples(self):
        pool = ex.load_pool(rows=[])
        titles = {e["title"] for e in pool}
        self.assertIn("four hard 500s with 90 seconds off", titles)

    def test_skips_unparseable_rows(self):
        rows = [
            {
                "title": "some totally ambiguous nonsense that no rule matches",
                "description": "",
                "machines": "All Machines",
            }
        ]
        pool = ex.load_pool(rows=rows)
        titles = {e["title"] for e in pool}
        self.assertNotIn("some totally ambiguous nonsense that no rule matches", titles)


if __name__ == "__main__":
    unittest.main()
