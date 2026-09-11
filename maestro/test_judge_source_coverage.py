"""Tests for Tier 3: the source-coverage judge wrapper.

Offline only - no live model calls anywhere in this file. What's proven here is that the wrapping
code around the judge is correct (result-building, threshold logic, fixture shape), not that the
judge itself gets the synthetic cases right - that can only be checked by a human running
maestro/judge/run_gold_suite_source_coverage.py with a real ANTHROPIC_API_KEY and reading the
output.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from maestro.judge.shared import EXPERIMENTAL_LABEL
from maestro.judge.source_coverage import COVERAGE_THRESHOLD, judge_source_coverage

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "maestro" / "judge" / "fixtures" / "source_coverage_cases.json"


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


class JudgeSourceCoverageWrappingTests(unittest.TestCase):
    def test_full_coverage_passes_with_score_one(self):
        fake_call = lambda source, topic, text: (
            {
                "source_statements": [
                    {"statement": "fact one", "covered": True},
                    {"statement": "fact two", "covered": True},
                ],
                "reason": "Both facts restated.",
            },
            None,
        )
        result, usage = judge_source_coverage(
            "case-1", ["source text"], "topic", "generated text", call_fn=fake_call,
        )
        self.assertEqual(result.case_id, "case-1")
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.reason.startswith(EXPERIMENTAL_LABEL))
        self.assertIsNone(usage)

    def test_partial_coverage_below_threshold_fails(self):
        fake_call = lambda source, topic, text: (
            {
                "source_statements": [
                    {"statement": "fact one", "covered": True},
                    {"statement": "fact two", "covered": False},
                    {"statement": "fact three", "covered": False},
                ],
                "reason": "Two of three facts omitted.",
            },
            None,
        )
        result, _ = judge_source_coverage(
            "case-2", ["source text"], "topic", "generated text", call_fn=fake_call,
        )
        self.assertAlmostEqual(result.score, 1 / 3)
        self.assertFalse(result.passed)
        self.assertIn("fact two", result.reason)
        self.assertIn("fact three", result.reason)

    def test_no_source_statements_is_vacuously_covered(self):
        fake_call = lambda source, topic, text: (
            {"source_statements": [], "reason": "No source statements to check."}, None,
        )
        result, _ = judge_source_coverage(
            "case-3", [], "topic", "generated text", call_fn=fake_call,
        )
        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.passed)

    def test_threshold_placeholder_matches_documented_value(self):
        # Documents the current placeholder value so a future recalibration change is a visible,
        # deliberate diff to this test, not a silent behavior change.
        self.assertEqual(COVERAGE_THRESHOLD, 0.8)

    def test_score_exactly_at_threshold_passes(self):
        fake_call = lambda source, topic, text: (
            {
                "source_statements": [
                    {"statement": "a", "covered": True},
                    {"statement": "b", "covered": True},
                    {"statement": "c", "covered": True},
                    {"statement": "d", "covered": False},
                    {"statement": "e", "covered": True},
                ],
                "reason": "4 of 5 covered.",
            },
            None,
        )
        result, _ = judge_source_coverage(
            "case-4", ["source"], "topic", "text", call_fn=fake_call,
        )
        self.assertEqual(result.score, 0.8)
        self.assertTrue(result.passed)


class RunGoldSuiteSourceCoverageCliSmokeTests(unittest.TestCase):
    def test_help_is_available_without_api_key(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "judge" / "run_gold_suite_source_coverage.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
