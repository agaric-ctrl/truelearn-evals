"""Tier 3 judge: wraps deepeval's FaithfulnessMetric. See maestro/judge/__init__.py for the
EXPERIMENTAL status this whole subpackage carries - not re-explained here, but this file's
verdicts are exactly what that status applies to.

What gets judged for a Maestro GeneratedQuestion: the explanation content (explanation_header +
explanation_footer + optional bottom_line), never question_text - the stem poses a problem, it
isn't a claim about the world, so there's nothing in it to fact-check.
"""

from __future__ import annotations

from typing import Callable

from deepeval.metrics import FaithfulnessMetric
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase

from maestro.generation.payload import ReferencesPayload
from tools.eval_result import CaseResult
from tools.provider_usage import usage_from_objects
from tools.retry import retry_call

EXPERIMENTAL_LABEL = "[EXPERIMENTAL - NOT VALIDATED AGAINST REAL SME AGREEMENT] "


def build_actual_output(
    explanation_header: str, explanation_footer: str, bottom_line: str | None = None,
) -> str:
    return "\n\n".join(part for part in (explanation_header, explanation_footer, bottom_line) if part)


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


def build_retrieval_context_from_references(references: ReferencesPayload) -> list[str] | None:
    """None (never []) when no result carries captured text - an empty list would read downstream
    as "valid but zero-length context", not "nothing gradable exists yet". Whether the real
    Maestro payload ever populates ReferenceResult.text is UNCONFIRMED; this returns None until it
    does.

    Caller-facing rule: a None return means the caller MUST Skip the judge call entirely, never
    pass an empty/meaningless retrieval_context into judge_faithfulness - deepeval's
    FaithfulnessMetric treats retrieval_context as real evidence to check claims against, and a
    non-empty-but-content-free list would silently produce a meaningless score instead of an
    honest Skip.

    Partial availability (some results have text, some don't) includes only the ones that do,
    rather than nulling out the whole set - a judge can meaningfully grade against partial source
    material; only the fully-empty case has nothing to grade against.

    TODO(once ReferenceResult.text availability is confirmed): a real caller belongs in
    maestro/generation/ - e.g. judge_history_head(payload, topic) would do
    `context = build_retrieval_context_from_references(payload.history[0].references)`, Skip if
    None, otherwise call judge_faithfulness(..., source=context, ...). Not built now - live
    URL-fetching to backfill missing text is explicitly out of scope, and this helper is not wired
    into any gate, script, or CI job by this change.
    """

    texts = [result.text for result in references.results if result.text]
    return texts or None
