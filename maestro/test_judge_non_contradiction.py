"""Tests for Tier 3: the non-contradiction judge wrapper.

Offline only - no live model calls anywhere in this file. What's proven here is that the wrapping
code around the judge is correct (result-building, threshold logic, fixture shape), not that the
judge itself gets the synthetic cases right - that can only be checked by a human running
maestro/judge/run_gold_suite_non_contradiction.py with a real ANTHROPIC_API_KEY and reading the
output.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from maestro.judge.non_contradiction import (
    MAX_ALLOWED_CONTRADICTIONS,
    judge_non_contradiction,
)
from maestro.judge.shared import EXPERIMENTAL_LABEL, parse_json_response

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "maestro" / "judge" / "fixtures" / "non_contradiction_cases.json"


class ParseJsonResponseTests(unittest.TestCase):
    """maestro/judge/shared.py's parse_json_response(), shared by both new judges."""

    def test_parses_plain_json(self):
        self.assertEqual(parse_json_response('{"a": 1}'), {"a": 1})

    def test_strips_markdown_json_fence(self):
        self.assertEqual(parse_json_response('```json\n{"a": 1}\n```'), {"a": 1})

    def test_strips_bare_markdown_fence(self):
        self.assertEqual(parse_json_response('```\n{"a": 1}\n```'), {"a": 1})

    def test_malformed_json_raises_rather_than_silently_returning_empty(self):
        with self.assertRaises(json.JSONDecodeError):
            parse_json_response("not json at all")


class SyntheticFixtureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_exactly_four_cases(self):
        self.assertEqual(len(self.cases), 4)

    def test_every_case_has_required_fields(self):
        for case in self.cases:
            with self.subTest(case_id=case.get("case_id")):
                self.assertIn("expected_pass", case)
                self.assertIn("source", case)
                self.assertIn("generated", case)

    def test_review_status_is_the_synthetic_literal_not_a_real_one(self):
        for case in self.cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(case["review_status"], "synthetic_not_sme_reviewed")

    def test_two_pass_and_two_fail(self):
        passes = [case for case in self.cases if case["expected_pass"] is True]
        fails = [case for case in self.cases if case["expected_pass"] is False]
        self.assertEqual(len(passes), 2)
        self.assertEqual(len(fails), 2)


class JudgeNonContradictionWrappingTests(unittest.TestCase):
    def test_no_contradictions_passes_with_score_one(self):
        fake_call = lambda source, topic, text: (
            {"contradictions": [], "reason": "Consistent with source."},
            None,
        )
        result, usage = judge_non_contradiction(
            "case-1", ["source text"], "topic", "generated text", call_fn=fake_call,
        )
        self.assertEqual(result.case_id, "case-1")
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.reason.startswith(EXPERIMENTAL_LABEL))
        self.assertIsNone(usage)

    def test_one_contradiction_fails_with_score_zero(self):
        fake_call = lambda source, topic, text: (
            {
                "contradictions": [
                    {"statement": "beta-2 selective", "conflicts_with": "beta-1 selective"},
                ],
                "reason": "Selectivity is reversed.",
            },
            None,
        )
        result, _ = judge_non_contradiction(
            "case-2", ["source text"], "topic", "generated text", call_fn=fake_call,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)
        self.assertIn("beta-2 selective", result.reason)
        self.assertIn("beta-1 selective", result.reason)

    def test_threshold_placeholder_is_zero_by_default(self):
        # Documents the current placeholder value so a future recalibration change is a visible,
        # deliberate diff to this test, not a silent behavior change.
        self.assertEqual(MAX_ALLOWED_CONTRADICTIONS, 0)

    def test_usage_is_surfaced_when_raw_response_provided(self):
        class _FakeResponse:
            usage = {"input_tokens": 10, "output_tokens": 5}

        fake_call = lambda source, topic, text: (
            {"contradictions": [], "reason": "ok"}, _FakeResponse(),
        )
        _, usage = judge_non_contradiction(
            "case-3", ["source"], "topic", "text", call_fn=fake_call,
        )
        self.assertEqual(usage, {"input_tokens": 10, "output_tokens": 5})


class RunGoldSuiteNonContradictionCliSmokeTests(unittest.TestCase):
    def test_help_is_available_without_api_key(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "judge" / "run_gold_suite_non_contradiction.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
