"""Tests for Tier 3: the LLM-judge faithfulness wrapper.

Offline only - no live model calls anywhere in this file. What's proven here is that the wrapping
code around the judge is correct (result-building, labeling, fixture shape), not that the judge
itself gets the synthetic cases right - that can only be checked by a human running
maestro/judge/run_gold_suite.py with a real ANTHROPIC_API_KEY and reading the output.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from maestro.generation.payload import ReferenceResult, ReferencesPayload
from maestro.judge.faithfulness import (
    EXPERIMENTAL_LABEL,
    build_actual_output,
    build_retrieval_context_from_references,
    judge_faithfulness,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "maestro" / "judge" / "fixtures" / "synthetic_cases.json"


class BuildActualOutputTests(unittest.TestCase):
    def test_joins_header_and_footer(self):
        self.assertEqual(
            build_actual_output("<p>Header.</p>", "<p>Footer.</p>"),
            "<p>Header.</p>\n\n<p>Footer.</p>",
        )

    def test_includes_bottom_line_when_present(self):
        text = build_actual_output("<p>Header.</p>", "<p>Footer.</p>", "<p>Bottom line.</p>")
        self.assertEqual(text, "<p>Header.</p>\n\n<p>Footer.</p>\n\n<p>Bottom line.</p>")

    def test_omits_bottom_line_when_none(self):
        text = build_actual_output("<p>Header.</p>", "<p>Footer.</p>", None)
        self.assertNotIn("Bottom line", text)


class SyntheticFixtureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_exactly_six_cases(self):
        self.assertEqual(len(self.cases), 6)

    def test_every_case_has_required_fields(self):
        for case in self.cases:
            with self.subTest(case_id=case.get("case_id")):
                self.assertIn("expected_pass", case)
                self.assertIn("claims", case)
                self.assertIn("source", case)
                self.assertIn("generated", case)

    def test_review_status_is_the_synthetic_literal_not_a_real_one(self):
        for case in self.cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(case["review_status"], "synthetic_not_sme_reviewed")

    def test_three_pass_and_three_fail(self):
        passes = [case for case in self.cases if case["expected_pass"] is True]
        fails = [case for case in self.cases if case["expected_pass"] is False]
        self.assertEqual(len(passes), 3)
        self.assertEqual(len(fails), 3)


class _FakeMetric:
    """Stands in for deepeval's FaithfulnessMetric so judge_faithfulness()'s wrapping logic can
    be tested with zero network calls."""

    def __init__(self, score: float, passed: bool, reason: str):
        self._score, self._passed, self._reason = score, passed, reason
        self.score = score
        self.reason = reason

    def measure(self, test_case) -> None:
        pass  # no-op: a real FaithfulnessMetric would call the judge here

    def is_successful(self) -> bool:
        return self._passed


class JudgeFaithfulnessWrappingTests(unittest.TestCase):
    def test_builds_case_result_from_metric_and_prefixes_experimental_label(self):
        fake_metric = _FakeMetric(score=0.95, passed=True, reason="All claims supported.")
        result, usage = judge_faithfulness(
            "case-1", ["source text"], "topic", "generated text",
            metric_factory=lambda: fake_metric,
        )

        self.assertEqual(result.case_id, "case-1")
        self.assertEqual(result.score, 0.95)
        self.assertTrue(result.passed)
        self.assertTrue(result.reason.startswith(EXPERIMENTAL_LABEL))
        self.assertIn("All claims supported.", result.reason)

    def test_failed_case_reports_passed_false(self):
        fake_metric = _FakeMetric(score=0.2, passed=False, reason="Unsupported claim found.")
        result, _ = judge_faithfulness(
            "case-2", ["source text"], "topic", "generated text",
            metric_factory=lambda: fake_metric,
        )
        self.assertFalse(result.passed)


class BuildRetrievalContextFromReferencesTests(unittest.TestCase):
    def test_returns_none_when_no_result_has_text(self):
        references = ReferencesPayload(query="q", results=[
            ReferenceResult(url="https://a.com", score=0.9, text=None),
            ReferenceResult(url="https://b.com", score=0.5, text=None),
        ])
        self.assertIsNone(build_retrieval_context_from_references(references))

    def test_returns_only_texts_that_are_present_in_order(self):
        references = ReferencesPayload(query="q", results=[
            ReferenceResult(url="https://a.com", score=0.9, text="first excerpt"),
            ReferenceResult(url="https://b.com", score=0.5, text=None),
            ReferenceResult(url="https://c.com", score=0.3, text="third excerpt"),
        ])
        self.assertEqual(
            build_retrieval_context_from_references(references),
            ["first excerpt", "third excerpt"],
        )

    def test_empty_results_returns_none_not_empty_list(self):
        self.assertIsNone(build_retrieval_context_from_references(ReferencesPayload(query="q", results=[])))


class RunGoldSuiteCliSmokeTests(unittest.TestCase):
    def test_help_is_available_without_api_key(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "judge" / "run_gold_suite.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
