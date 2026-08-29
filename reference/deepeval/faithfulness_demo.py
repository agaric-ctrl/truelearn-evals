"""
DeepEval faithfulness demo: grounded vs hallucinated.

Tests the JUDGE, not a generator. We supply a known-good answer and a
known-bad answer, and check that the faithfulness metric scores them correctly.

PLACEHOLDER: the context/grounded/hallucinated content below is hand-written synthetic
clinical-QA content for exercising the judge mechanism - not TrueLearn content, and not
reviewed by any clinician. See the root README ("Faithfulness-eval reference methodology").

Run:  python3 faithfulness_demo.py [--json]
Needs: ANTHROPIC_API_KEY in the environment.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric
from deepeval.models import AnthropicModel
from tools.eval_result import CaseResult, ClaimResult, EvaluationResult
from tools.retry import retry_call
from tools.provider_usage import estimate_cost, usage_from_objects

judge = AnthropicModel(model="claude-sonnet-4-6", temperature=0)

context = [
    "ST elevation in leads II, III, and aVF indicates an inferior wall MI, "
    "most commonly caused by occlusion of the right coronary artery (RCA)."
]

grounded = LLMTestCase(
    input="55-year-old, chest pain, ST elevation in II, III, aVF. Diagnosis and cause?",
    actual_output="Inferior wall myocardial infarction, most commonly caused by "
                  "occlusion of the right coronary artery.",
    retrieval_context=context,
)

hallucinated = LLMTestCase(
    input="55-year-old, chest pain, ST elevation in II, III, aVF. Diagnosis and cause?",
    actual_output="Inferior wall MI, most commonly caused by occlusion of the left "
                  "anterior descending (LAD) artery, and it should be treated with "
                  "thrombolytics within 90 minutes.",
    retrieval_context=context,
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit normalized JSON.")
    args = parser.parse_args()

    started = time.perf_counter()
    metric = FaithfulnessMetric(threshold=0.9, model=judge, include_reason=True)
    cases = []
    for name, tc in [("grounded", grounded), ("hallucinated", hallucinated)]:
        retry_call(
            lambda: metric.measure(tc),
            operation_name=f"deepeval.{name}",
        )
        cases.append(
            CaseResult(
                case_id=name,
                score=metric.score,
                passed=metric.is_successful(),
                reason=metric.reason,
                claims=(
                    [
                        ClaimResult(
                            claim="Inferior wall myocardial infarction",
                            supported=True,
                            evidence=[context[0]],
                        ),
                        ClaimResult(
                            claim="Occlusion of the right coronary artery",
                            supported=True,
                            evidence=[context[0]],
                        ),
                    ]
                    if name == "grounded"
                    else [
                        ClaimResult(
                            claim="Inferior wall myocardial infarction",
                            supported=True,
                            evidence=[context[0]],
                        ),
                        ClaimResult(
                            claim="Occlusion of the left anterior descending artery",
                            supported=False,
                            evidence=[],
                        ),
                        ClaimResult(
                            claim="Treatment with thrombolytics within 90 minutes",
                            supported=False,
                            evidence=[],
                        ),
                    ]
                ),
            )
        )

    result = EvaluationResult(
        framework="deepeval",
        metric="faithfulness",
        cases=cases,
        model="claude-sonnet-4-6",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    usage = usage_from_objects(metric, judge)
    if usage:
        result.input_tokens = usage["input_tokens"]
        result.output_tokens = usage["output_tokens"]
        result.estimated_cost_usd = estimate_cost(
            usage,
            float(os.getenv("ANTHROPIC_INPUT_USD_PER_MILLION", "0")),
            float(os.getenv("ANTHROPIC_OUTPUT_USD_PER_MILLION", "0")),
        )
    if args.json:
        print(result.to_json())
        return
    for case in cases:
        print(f"\n=== {case.case_id.upper()} ===")
        print("score :", case.score)
        print("passed:", case.passed)
        print("reason:", case.reason)


if __name__ == "__main__":
    main()
