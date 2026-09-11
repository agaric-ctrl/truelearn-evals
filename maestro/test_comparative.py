"""Tests for the comparative (A/B) testing scaffold - docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md.

Offline only - no live model calls, no ANTHROPIC_API_KEY needed anywhere in this file. Every Tier 3
judge call in these tests is a hand-built fake, same discipline as maestro/test_judge.py and
maestro/test_judge_non_contradiction.py/test_judge_source_coverage.py: what's proven here is that
the scaffold's own orchestration/merge/diff/render logic is correct, not that any judge gets a real
generation right.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from maestro.check_result import CheckResult, Status
from maestro.comparative.compare_variants import compare_variant_results
from maestro.comparative.render_variant_diff_report import render_report
from maestro.comparative.run_variant_pair import (
    VariantResult,
    _available_judges,
    evaluate_variant,
    load_variant_result,
    merge_variant_result,
    variant_result_to_dict,
)
from maestro.comparative.variants import load_variant_pair, variant_pair_to_dict
from maestro.models import EvalConfig, GeneratedQuestion
from tools.eval_result import CaseResult

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "maestro" / "comparative" / "fixtures" / "hand_constructed_pair.json"


def _load_fixture_pair():
    return load_variant_pair(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


class VariantPairLoadingTests(unittest.TestCase):
    def test_loads_both_variants_with_free_text_labels(self):
        pair = _load_fixture_pair()
        self.assertEqual(pair.variant_a.label, "terse")
        self.assertEqual(pair.variant_b.label, "verbose")

    def test_variants_carry_their_own_source_independently(self):
        pair = _load_fixture_pair()
        self.assertIsInstance(pair.variant_a.source, list)
        self.assertIsInstance(pair.variant_b.source, list)

    def test_round_trips_through_dict(self):
        pair = _load_fixture_pair()
        round_tripped = variant_pair_to_dict(pair)
        self.assertEqual(round_tripped["variant_a"]["label"], "terse")
        self.assertEqual(round_tripped["pair_id"], pair.pair_id)


class EvaluateVariantTests(unittest.TestCase):
    def test_runs_tier1_checks_against_real_content(self):
        pair = _load_fixture_pair()
        result = evaluate_variant(pair.variant_a, "Mechanism of metoprolol", EvalConfig(), judges={})
        self.assertGreater(len(result.tier1_results), 0)
        self.assertEqual(result.judge_results, {})

    def test_calls_every_supplied_judge_with_variant_label_as_case_id(self):
        calls = []

        def fake_judge(case_id, source, topic, text):
            calls.append((case_id, source, topic, text))
            return CaseResult(case_id=case_id, score=1.0, passed=True, reason="ok"), None

        pair = _load_fixture_pair()
        result = evaluate_variant(
            pair.variant_a, "Mechanism of metoprolol", EvalConfig(), judges={"fake": fake_judge},
        )
        self.assertIn("fake", result.judge_results)
        self.assertEqual(calls[0][0], "terse")


class MergeVariantResultTests(unittest.TestCase):
    def test_merge_adds_new_judges_without_dropping_existing_ones(self):
        existing = VariantResult(
            label="terse",
            tier1_results=[],
            judge_results={"faithfulness_deepeval": CaseResult(case_id="terse", score=0.9, passed=True)},
        )
        new = VariantResult(
            label="terse",
            tier1_results=[CheckResult(check_name="x", status=Status.PASS, message="ok")],
            judge_results={"non_contradiction": CaseResult(case_id="terse", score=1.0, passed=True)},
        )
        merged = merge_variant_result(existing, new)
        self.assertIn("faithfulness_deepeval", merged.judge_results)
        self.assertIn("non_contradiction", merged.judge_results)
        self.assertEqual(len(merged.tier1_results), 1)

    def test_merge_refreshes_tier1_results_from_the_new_run(self):
        existing = VariantResult(label="terse", tier1_results=[
            CheckResult(check_name="old", status=Status.FAIL, message="stale"),
        ])
        new = VariantResult(label="terse", tier1_results=[
            CheckResult(check_name="new", status=Status.PASS, message="fresh"),
        ])
        merged = merge_variant_result(existing, new)
        self.assertEqual([r.check_name for r in merged.tier1_results], ["new"])

    def test_merge_preserves_existing_tier1_results_when_new_run_has_none(self):
        # Simulates a .venv-maestro-ragas run (Tier 1 not importable there - see
        # run_variant_pair.py's _TIER1_AVAILABLE): its tier1_results is always empty, and that must
        # never be mistaken for "Tier 1 now finds nothing" and wipe out a real earlier result.
        existing = VariantResult(label="terse", tier1_results=[
            CheckResult(check_name="real_result", status=Status.FAIL, message="from .venv-maestro"),
        ])
        new = VariantResult(
            label="terse", tier1_results=[],
            judge_results={"faithfulness_ragas": CaseResult(case_id="terse", score=0.9, passed=True)},
        )
        merged = merge_variant_result(existing, new)
        self.assertEqual([r.check_name for r in merged.tier1_results], ["real_result"])
        self.assertIn("faithfulness_ragas", merged.judge_results)


class VariantResultSerializationTests(unittest.TestCase):
    def test_round_trips_through_json(self):
        result = VariantResult(
            label="terse",
            tier1_results=[CheckResult(check_name="x", status=Status.FAIL, message="bad", field_name="question_text")],
            judge_results={"non_contradiction": CaseResult(case_id="terse", score=0.0, passed=False, reason="found one")},
        )
        round_tripped = load_variant_result(json.loads(json.dumps(variant_result_to_dict(result))))
        self.assertEqual(round_tripped.label, "terse")
        self.assertEqual(round_tripped.tier1_results[0].status, Status.FAIL)
        self.assertEqual(round_tripped.judge_results["non_contradiction"].score, 0.0)


class AvailableJudgesTests(unittest.TestCase):
    def test_non_contradiction_and_source_coverage_always_importable(self):
        # Both only need `anthropic`, present in every venv this repo uses (see
        # maestro/judge/shared.py's module docstring) - unlike deepeval/ragas, which are
        # venv-specific, these two should always show up regardless of which venv runs this test.
        judges = _available_judges()
        self.assertIn("non_contradiction", judges)
        self.assertIn("source_coverage", judges)


class CompareVariantResultsTests(unittest.TestCase):
    def test_identical_results_produce_zero_disagreements(self):
        result_a = VariantResult(
            label="a",
            tier1_results=[CheckResult(check_name="x", status=Status.PASS, message="ok")],
            judge_results={"j": CaseResult(case_id="a", score=1.0, passed=True)},
        )
        result_b = VariantResult(
            label="b",
            tier1_results=[CheckResult(check_name="x", status=Status.PASS, message="ok")],
            judge_results={"j": CaseResult(case_id="b", score=1.0, passed=True)},
        )
        diff = compare_variant_results("pair-1", result_a, result_b)
        self.assertEqual(diff.disagreement_count, 0)

    def test_differing_check_status_is_flagged_as_disagreement(self):
        result_a = VariantResult(label="a", tier1_results=[
            CheckResult(check_name="x", status=Status.PASS, message="ok", field_name="f"),
        ])
        result_b = VariantResult(label="b", tier1_results=[
            CheckResult(check_name="x", status=Status.FAIL, message="bad", field_name="f"),
        ])
        diff = compare_variant_results("pair-2", result_a, result_b)
        self.assertEqual(diff.disagreement_count, 1)
        self.assertEqual(diff.check_diffs[0].variant_a_status, "pass")
        self.assertEqual(diff.check_diffs[0].variant_b_status, "fail")

    def test_check_present_on_only_one_side_reports_none_not_a_crash(self):
        result_a = VariantResult(label="a", tier1_results=[
            CheckResult(check_name="only_in_a", status=Status.PASS, message="ok"),
        ])
        result_b = VariantResult(label="b", tier1_results=[])
        diff = compare_variant_results("pair-3", result_a, result_b)
        self.assertEqual(diff.check_diffs[0].variant_a_status, "pass")
        self.assertIsNone(diff.check_diffs[0].variant_b_status)
        self.assertFalse(diff.check_diffs[0].agrees)

    def test_judge_score_delta_computed_when_both_sides_scored(self):
        result_a = VariantResult(label="a", judge_results={"j": CaseResult(case_id="a", score=0.6, passed=False)})
        result_b = VariantResult(label="b", judge_results={"j": CaseResult(case_id="b", score=0.9, passed=True)})
        diff = compare_variant_results("pair-4", result_a, result_b)
        self.assertAlmostEqual(diff.judge_diffs[0].score_delta, 0.3)
        self.assertFalse(diff.judge_diffs[0].agrees)

    def test_judge_missing_on_one_side_does_not_agree_and_has_no_delta(self):
        result_a = VariantResult(label="a", judge_results={"j": CaseResult(case_id="a", score=0.9, passed=True)})
        result_b = VariantResult(label="b", judge_results={})
        diff = compare_variant_results("pair-5", result_a, result_b)
        self.assertFalse(diff.judge_diffs[0].agrees)
        self.assertIsNone(diff.judge_diffs[0].score_delta)

    def test_no_new_judgment_logic_decides_a_winner(self):
        # There is no "winner"/"better_variant" field anywhere on VariantDiff - this test exists so
        # that field's absence is a visible, deliberate assertion, not just an omission nobody checks.
        result_a = VariantResult(label="a")
        result_b = VariantResult(label="b")
        diff = compare_variant_results("pair-6", result_a, result_b)
        self.assertFalse(hasattr(diff, "winner"))
        self.assertFalse(hasattr(diff, "better_variant"))


class RenderVariantDiffReportTests(unittest.TestCase):
    def test_report_contains_both_variant_labels_and_disagreement_count(self):
        pair = _load_fixture_pair()
        result_a = VariantResult(label="terse", tier1_results=[
            CheckResult(check_name="references_format", status=Status.FAIL, message="0-4 refs"),
        ])
        result_b = VariantResult(label="verbose", tier1_results=[
            CheckResult(check_name="references_format", status=Status.PASS, message="ok"),
        ])
        diff = compare_variant_results(pair.pair_id, result_a, result_b)
        report = render_report(pair, diff)
        self.assertIn("terse", report)
        self.assertIn("verbose", report)
        self.assertIn("1 disagreement(s) found", report)
        self.assertIn("DISAGREE", report)


class EndToEndScaffoldTests(unittest.TestCase):
    """Runs the full pipeline (load pair -> evaluate both variants with fake judges -> diff ->
    render) against the real hand-constructed fixture, proving the scaffold works end-to-end on a
    hand-constructed pair per the task's acceptance criteria - without any live judge call."""

    def test_full_pipeline_on_hand_constructed_pair(self):
        pair = _load_fixture_pair()

        def fake_judge(case_id, source, topic, text):
            # A deliberately different fake score per variant so the diff has something real to show.
            score = 1.0 if case_id == "verbose" else 0.5
            return CaseResult(case_id=case_id, score=score, passed=score >= 0.8, reason="fake"), None

        judges = {"fake_faithfulness": fake_judge}
        result_a = evaluate_variant(pair.variant_a, pair.input["topic"], EvalConfig(), judges)
        result_b = evaluate_variant(pair.variant_b, pair.input["topic"], EvalConfig(), judges)

        diff = compare_variant_results(pair.pair_id, result_a, result_b)
        report = render_report(pair, diff)

        self.assertGreater(len(diff.check_diffs), 0)
        self.assertEqual(len(diff.judge_diffs), 1)
        self.assertFalse(diff.judge_diffs[0].agrees)  # 0.5 vs 1.0 -> different passed verdicts
        self.assertIn("<html", report)


class CliSmokeTests(unittest.TestCase):
    def test_run_variant_pair_help_is_available_without_api_key(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "comparative" / "run_variant_pair.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_render_variant_diff_report_help_is_available(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "comparative" / "render_variant_diff_report.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
