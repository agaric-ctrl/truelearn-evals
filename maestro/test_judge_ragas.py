"""Tests for the RAGAS-variant Tier 3 judge (maestro/judge/faithfulness_ragas.py).

Offline only - no live model calls anywhere in this file, same discipline as test_judge.py. What's
proven here is that the wrapping code around the judge is correct, not that the judge itself gets
the synthetic cases right - that can only be checked by a human running
maestro/judge/run_gold_suite_ragas.py with a real ANTHROPIC_API_KEY and reading the output.

REQUIRES THE SEPARATE RAGAS VENV - do not run this in .venv-maestro (deepeval installed there
conflicts with ragas on the click dependency):
    python3 -m venv .venv-maestro-ragas
    .venv-maestro-ragas/bin/pip install -r requirements-maestro-ragas.txt
    .venv-maestro-ragas/bin/python -m unittest maestro/test_judge_ragas.py
Not part of the default maestro/test_*.py command documented in the root README's Quickstart.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from maestro.judge.faithfulness_ragas import FAITHFULNESS_THRESHOLD, judge_faithfulness_ragas
from maestro.judge.shared import EXPERIMENTAL_LABEL

ROOT = Path(__file__).resolve().parents[1]


class _FakeScorer:
    """Test-only stand-in for ragas's Faithfulness metric - has just enough surface
    (an async single_turn_ascore(sample)) for judge_faithfulness_ragas() to call, with no real LLM
    involved, matching the metric_factory injection pattern in faithfulness.judge_faithfulness()."""

    def __init__(self, score: float):
        self._score = score

    async def single_turn_ascore(self, sample) -> float:  # noqa: ANN001 - sample is a real SingleTurnSample
        return self._score


class JudgeFaithfulnessRagasWrappingTests(unittest.IsolatedAsyncioTestCase):
    async def test_passing_case_reports_passed_true_and_experimental_label(self):
        result, usage = await judge_faithfulness_ragas(
            "case-1", ["Some source sentence."], "Some topic", "Some grounded answer.",
            scorer_factory=lambda: _FakeScorer(0.95),
        )
        self.assertEqual(result.case_id, "case-1")
        self.assertEqual(result.score, 0.95)
        self.assertTrue(result.passed)
        self.assertEqual(result.reason, EXPERIMENTAL_LABEL.strip())
        self.assertIsNone(usage)  # _FakeScorer carries no provider usage metadata

    async def test_failing_case_reports_passed_false(self):
        result, _usage = await judge_faithfulness_ragas(
            "case-2", ["Some source sentence."], "Some topic", "An unfaithful answer.",
            scorer_factory=lambda: _FakeScorer(0.2),
        )
        self.assertFalse(result.passed)

    async def test_score_exactly_at_threshold_passes(self):
        result, _usage = await judge_faithfulness_ragas(
            "case-3", ["Source."], "Topic", "Answer.",
            scorer_factory=lambda: _FakeScorer(FAITHFULNESS_THRESHOLD),
        )
        self.assertTrue(result.passed)

    async def test_claims_left_empty_for_caller_to_fill_in(self):
        result, _usage = await judge_faithfulness_ragas(
            "case-4", ["Source."], "Topic", "Answer.",
            scorer_factory=lambda: _FakeScorer(0.9),
        )
        self.assertEqual(result.claims, [])


class RunGoldSuiteRagasCliSmokeTests(unittest.TestCase):
    def test_help_is_available_without_api_key(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "judge" / "run_gold_suite_ragas.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
