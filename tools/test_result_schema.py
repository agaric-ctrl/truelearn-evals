"""Offline checks for the normalized evaluation result contract."""

import json
import logging
import subprocess
import sys
import unittest
from pathlib import Path

from tools.gold_accuracy import calculate_metrics, join_predictions
from tools.compare_results import compare_results
from tools.retrieval_correctness import evaluate_cases
from tools.eval_result import CaseResult, ClaimResult, EvaluationResult
from tools.run_metadata import summarize_metadata
from tools.html_report import render_report
from tools.provider_usage import estimate_cost, extract_usage, usage_from_objects
from tools.retry import retry_call
from tools.validate_workflows import validate_workflow
from tools.promptfoo_results import normalize_promptfoo
from tools.regression import compare_baseline
from tools.reliability import analyze_reliability
from tools.schema_migrations import migrate_result
from tools.privacy_scan import scan_text


ROOT = Path(__file__).resolve().parents[1]


class ResultSchemaTest(unittest.TestCase):
    def test_serializes_required_case_fields(self):
        result = EvaluationResult(
            framework="test",
            metric="faithfulness",
            cases=[
                CaseResult(
                    "grounded",
                    1.0,
                    True,
                    claims=[
                        ClaimResult(
                            "Inferior wall myocardial infarction",
                            True,
                            ["source passage"],
                        )
                    ],
                )
            ],
        )

        payload = json.loads(result.to_json())

        self.assertEqual(payload["framework"], "test")
        self.assertEqual(payload["cases"][0]["case_id"], "grounded")
        self.assertEqual(payload["cases"][0]["score"], 1.0)
        self.assertTrue(payload["cases"][0]["passed"])
        self.assertEqual(payload["model"], None)
        self.assertEqual(
            payload["cases"][0]["claims"][0]["claim"],
            "Inferior wall myocardial infarction",
        )
        self.assertTrue(payload["cases"][0]["claims"][0]["supported"])
        self.assertEqual(
            payload["cases"][0]["claims"][0]["evidence"],
            ["source passage"],
        )

    def test_runner_help_is_available_without_framework_dependencies(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "run_evals.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("--deepeval-python", completed.stdout)
        self.assertIn("--ragas-python", completed.stdout)

    def test_gold_metrics_report_confusion_counts(self):
        metrics = calculate_metrics(
            [
                {"expected_pass": True, "predicted_pass": True},
                {"expected_pass": False, "predicted_pass": False},
                {"expected_pass": False, "predicted_pass": True},
                {"expected_pass": True, "predicted_pass": False},
            ]
        )

        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["false_negative"], 1)

    def test_retrieval_and_correctness_metrics(self):
        metrics = evaluate_cases(
            [
                {
                    "retrieved_context_ids": ["a"],
                    "relevant_context_ids": ["a"],
                    "answer_correct": True,
                },
                {
                    "retrieved_context_ids": ["b", "c"],
                    "relevant_context_ids": ["b"],
                    "answer_correct": False,
                },
            ]
        )

        self.assertEqual(metrics["retrieval"]["precision"], 0.75)
        self.assertEqual(metrics["retrieval"]["recall"], 1.0)
        self.assertEqual(metrics["answer_correctness"], 0.5)

    def test_gold_labels_join_to_normalized_framework_results(self):
        cases = join_predictions(
            [
                {"case_id": "grounded", "expected_pass": True},
                {"case_id": "hallucinated", "expected_pass": False},
            ],
            [
                {
                    "framework": "deepeval",
                    "cases": [
                        {"case_id": "grounded", "passed": True},
                        {"case_id": "hallucinated", "passed": False},
                    ],
                }
            ],
        )

        self.assertEqual(calculate_metrics(cases)["accuracy"], 1.0)

    def test_comparison_reports_agreement_and_score_spread(self):
        report = compare_results(
            [
                {
                    "framework": "deepeval",
                    "cases": [{"case_id": "case-1", "score": 1.0, "passed": True}],
                },
                {
                    "framework": "ragas",
                    "cases": [{"case_id": "case-1", "score": 0.8, "passed": False}],
                },
            ]
        )

        self.assertEqual(report["disagreement_count"], 1)
        self.assertAlmostEqual(report["cases"][0]["score_spread"], 0.2)

    def test_metadata_summary_tracks_cost_latency_and_models(self):
        summary = summarize_metadata(
            [
                {
                    "model": "judge-a",
                    "latency_ms": 100,
                    "estimated_cost_usd": 0.02,
                },
                {
                    "model": "judge-b",
                    "latency_ms": 300,
                    "estimated_cost_usd": 0.03,
                },
            ]
        )

        self.assertEqual(summary["models"], ["judge-a", "judge-b"])
        self.assertEqual(summary["total_latency_ms"], 400)
        self.assertEqual(summary["total_estimated_cost_usd"], 0.05)
        self.assertEqual(summary["average_latency_ms"], 200)

    def test_html_report_contains_framework_cases_and_escapes_text(self):
        report = render_report(
            [
                {
                    "framework": "test",
                    "cases": [
                        {
                            "case_id": "case-1",
                            "score": 1.0,
                            "passed": True,
                            "reason": "<safe>",
                        }
                    ],
                }
            ]
        )

        self.assertIn("Faithfulness Evaluation Report", report)
        self.assertIn("case-1", report)
        self.assertIn("&lt;safe&gt;", report)

    def test_framework_result_serializes_run_metadata(self):
        result = EvaluationResult(
            framework="deepeval",
            metric="faithfulness",
            cases=[],
            model="claude-sonnet-4-6",
            latency_ms=123.45,
        )

        payload = json.loads(result.to_json())

        self.assertEqual(payload["model"], "claude-sonnet-4-6")
        self.assertEqual(payload["latency_ms"], 123.45)

    def test_provider_usage_supports_anthropic_and_openai_shapes(self):
        anthropic = extract_usage(
            {"usage": {"input_tokens": 1_000, "output_tokens": 200}}
        )
        openai = extract_usage(
            {"usage": {"prompt_tokens": 1_000, "completion_tokens": 200}}
        )

        self.assertEqual(anthropic, {"input_tokens": 1000, "output_tokens": 200})
        self.assertEqual(openai, anthropic)
        self.assertEqual(estimate_cost(anthropic, 3.0, 15.0), 0.006)
        self.assertEqual(
            usage_from_objects(
                type("Response", (), {"usage_metadata": {"input_tokens": 4, "output_tokens": 2}})()
            ),
            {"input_tokens": 4, "output_tokens": 2},
        )

    def test_retry_retries_transient_errors_but_not_permanent_errors(self):
        attempts = 0

        def transient():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise TimeoutError("temporary")
            return "ok"

        self.assertEqual(retry_call(transient, attempts=2, delay_seconds=0), "ok")

        with self.assertRaises(ValueError):
            retry_call(lambda: (_ for _ in ()).throw(ValueError("permanent")), delay_seconds=0)

    def test_retry_logs_structured_event(self):
        attempts = 0
        records = []
        handler = logging.Handler()
        handler.emit = lambda record: records.append(record.getMessage())
        retry_logger = logging.getLogger("faithfulness.retry")
        retry_logger.addHandler(handler)
        try:
            def transient():
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise TimeoutError("temporary")
                return "ok"

            retry_call(
                transient,
                attempts=2,
                delay_seconds=0,
                operation_name="test.operation",
            )
        finally:
            retry_logger.removeHandler(handler)

        event = json.loads(records[0])
        self.assertEqual(event["operation"], "test.operation")
        self.assertEqual(event["event"], "retry")

    def test_live_workflow_has_required_safeguards(self):
        errors = validate_workflow(
            ROOT / ".github" / "workflows" / "live-evaluation.yml",
            live=True,
        )

        self.assertEqual(errors, [])

    def test_promptfoo_results_normalize_to_shared_schema(self):
        payload = json.loads(
            (ROOT / "reference" / "data" / "promptfoo_result_fixture.json").read_text()
        )
        result = normalize_promptfoo(payload)

        self.assertEqual(result["framework"], "promptfoo")
        self.assertEqual([case["case_id"] for case in result["cases"]], ["grounded", "hallucinated"])
        self.assertEqual(result["latency_ms"], 300)
        self.assertEqual(result["input_tokens"], 210)
        self.assertFalse(result["cases"][1]["passed"])

    def test_regression_baseline_accepts_small_changes_and_rejects_large_drops(self):
        baseline = {
            "accuracy": 1.0,
            "latency_ms": 1000,
            "estimated_cost_usd": 0.05,
        }
        self.assertTrue(
            compare_baseline(
                baseline,
                {"accuracy": 0.96, "latency_ms": 1200, "estimated_cost_usd": 0.06},
            )["passed"]
        )
        self.assertFalse(
            compare_baseline(
                baseline,
                {"accuracy": 0.9, "latency_ms": 1000, "estimated_cost_usd": 0.05},
            )["passed"]
        )

    def test_reliability_reports_flips_and_score_variance(self):
        report = analyze_reliability(
            [
                {
                    "cases": [{"case_id": "case-1", "score": 0.4, "passed": False}]
                },
                {
                    "cases": [{"case_id": "case-1", "score": 0.8, "passed": True}]
                },
            ]
        )

        self.assertEqual(report["verdict_flip_count"], 1)
        self.assertEqual(report["verdict_agreement_rate"], 0.0)
        self.assertAlmostEqual(report["cases"][0]["score_mean"], 0.6)

    def test_legacy_result_migrates_to_current_schema(self):
        migrated = migrate_result(
            {
                "framework": "legacy",
                "metric": "faithfulness",
                "cases": [{"case_id": "case-1", "score": 1.0, "passed": True}],
            }
        )

        self.assertEqual(migrated["schema_version"], 1)
        self.assertEqual(migrated["cases"][0]["claims"], [])
        self.assertIsNone(migrated["model"])

    def test_privacy_scan_detects_identifiers_without_printing_values(self):
        findings = scan_text(
            "Contact jane@example.com, phone 555-123-4567, MRN: ABC-1234."
        )

        self.assertEqual(
            [finding["type"] for finding in findings],
            ["email", "phone", "medical_record_number"],
        )
        self.assertNotIn("jane@example.com", str(findings))


if __name__ == "__main__":
    unittest.main()
