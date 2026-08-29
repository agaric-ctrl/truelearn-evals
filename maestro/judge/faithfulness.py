"""Tier 3 judge: wraps deepeval's FaithfulnessMetric. See maestro/judge/__init__.py for the
EXPERIMENTAL status this whole subpackage carries - not re-explained here, but this file's
verdicts are exactly what that status applies to.

What gets judged for a Maestro GeneratedQuestion: the explanation content (explanation_header +
explanation_footer + optional bottom_line), never question_text - the stem poses a problem, it
isn't a claim about the world, so there's nothing in it to fact-check.

See faithfulness_ragas.py for a second, independently-implemented judge over the same content
shape - kept in its own module (not here) because deepeval and ragas conflict on the click
dependency and must live in separate venvs. build_actual_output/build_retrieval_context_from_references
live in shared.py, framework-agnostic, so both judge modules use the exact same conversion logic;
re-exported here unchanged for backward compatibility with existing imports of this module.
"""

from __future__ import annotations

from typing import Callable

from deepeval.metrics import FaithfulnessMetric
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase

from maestro.judge.shared import (
    EXPERIMENTAL_LABEL,
    build_actual_output,
    build_retrieval_context_from_references,
)
from tools.eval_result import CaseResult
from tools.provider_usage import usage_from_objects
from tools.retry import retry_call

__all__ = [
    "EXPERIMENTAL_LABEL",
    "build_actual_output",
    "build_retrieval_context_from_references",
    "judge_faithfulness",
]


def judge_faithfulness(
    case_id: str,
    source: list[str],
    topic: str,
    generated_text: str,
    *,
    metric_factory: Callable[[], FaithfulnessMetric] | None = None,
) -> tuple[CaseResult, dict | None]:
    """Runs deepeval's FaithfulnessMetric on one Maestro explanation. Returns
    (CaseResult, usage_dict_or_None).

    CaseResult.claims is left empty - deepeval's public API has no stable per-claim structure
    (the same reason deepeval/faithfulness_demo.py hand-writes its own ClaimResults rather than
    deriving them from the metric). Callers that already know the expected claims (run_gold_suite.py,
    from its fixture) should set .claims themselves afterward - that's recording ground truth, not
    reporting the judge's own output.

    metric_factory is a test-only injection point so the wrapping logic here can be unit-tested
    without a live model call; production callers omit it. When supplied, no AnthropicModel is
    constructed at all - AnthropicModel.__init__ eagerly requires ANTHROPIC_API_KEY even before any
    call is made, so building one unconditionally would defeat the whole point of injecting a fake
    metric in tests.
    """

    judge = None
    if metric_factory is None:
        judge = AnthropicModel(model="claude-sonnet-4-6", temperature=0)
        metric = FaithfulnessMetric(threshold=0.9, model=judge, include_reason=True)
    else:
        metric = metric_factory()

    test_case = LLMTestCase(input=topic, actual_output=generated_text, retrieval_context=source)

    retry_call(lambda: metric.measure(test_case), operation_name=f"maestro.judge.{case_id}")

    result = CaseResult(
        case_id=case_id,
        score=metric.score,
        passed=metric.is_successful(),
        reason=EXPERIMENTAL_LABEL + (metric.reason or ""),
    )
    usage_sources = (metric, judge) if judge is not None else (metric,)
    return result, usage_from_objects(*usage_sources)
