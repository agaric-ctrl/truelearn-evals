"""Tier 3 judge, RAGAS variant: a second, independently-implemented judge over the exact same
Maestro content shape faithfulness.py judges - see maestro/judge/__init__.py for the EXPERIMENTAL
status this whole subpackage carries, which applies here identically.

Reuses shared.py's build_actual_output()/build_retrieval_context_from_references() unchanged,
rather than duplicating them - both judge modules convert a Maestro GeneratedQuestion the same way.
Kept in its own module (not faithfulness.py) because deepeval and ragas conflict on the click
dependency and must live in separate venvs (requirements-maestro.txt vs
requirements-maestro-ragas.txt) - see the root README's "RAGAS: a second judge" section.

Never imported by faithfulness.py, run_gold_suite.py, judge/__init__.py, or anything that runs in
the default .venv-maestro environment - importing this module requires ragas/langchain-anthropic to
be installed, which requirements-maestro.txt deliberately does not do.

Purpose: not a replacement for the deepeval judge, a cross-check on it. Two independently-mechanized
judges (deepeval's claim-decomposition vs ragas's own statement-decomposition) agreeing on the same
synthetic cases is a mild confidence-builder; disagreeing tells you exactly where the "faithfulness
judge" concept itself is shaky - before either one is ever treated as evidence against real SME
grading. See tools/reliability.py and tools/compare_results.py for the analysis this is meant to
feed once both judges have run against the same cases.
"""

from __future__ import annotations

from typing import Callable

from langchain_anthropic import ChatAnthropic
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness

from maestro.judge.shared import EXPERIMENTAL_LABEL
from tools.eval_result import CaseResult
from tools.provider_usage import usage_from_objects
from tools.retry import async_retry_call

FAITHFULNESS_THRESHOLD = 0.9


async def judge_faithfulness_ragas(
    case_id: str,
    source: list[str],
    topic: str,
    generated_text: str,
    *,
    scorer_factory: Callable[[], object] | None = None,
) -> tuple[CaseResult, dict | None]:
    """Runs ragas's Faithfulness metric on one Maestro explanation. Returns
    (CaseResult, usage_dict_or_None) - same contract as faithfulness.judge_faithfulness().

    Async, not sync, because ragas's single_turn_ascore is async - using it directly (rather than
    the evaluate() batch runner) sidesteps a batch-runner hang seen in ragas 0.4.x, same reasoning
    as evaluations/faithfulness/ragas/ragas_faithfulness.py.

    CaseResult.reason carries only the EXPERIMENTAL_LABEL - unlike deepeval's metric.reason, ragas's
    single_turn_ascore returns a bare float with no per-claim reasoning API. CaseResult.claims is
    left empty for the same reason judge_faithfulness() leaves it empty: callers that already know
    the expected claims (run_gold_suite_ragas.py, from its fixture) set .claims themselves
    afterward - that's recording ground truth, not reporting the judge's own output.

    scorer_factory is a test-only injection point, same role as judge_faithfulness()'s
    metric_factory: when supplied, no ChatAnthropic/LangchainLLMWrapper is constructed at all -
    building a real one requires ANTHROPIC_API_KEY and would defeat the whole point of injecting a
    fake scorer in tests. The returned object only needs an async single_turn_ascore(sample) method.
    """

    llm = None
    if scorer_factory is None:
        llm = LangchainLLMWrapper(ChatAnthropic(model="claude-sonnet-4-6", temperature=0))
        scorer = Faithfulness(llm=llm)
    else:
        scorer = scorer_factory()

    sample = SingleTurnSample(user_input=topic, response=generated_text, retrieved_contexts=source)

    score = await async_retry_call(
        lambda: scorer.single_turn_ascore(sample),
        operation_name=f"maestro.judge_ragas.{case_id}",
    )

    result = CaseResult(
        case_id=case_id,
        score=score,
        passed=score >= FAITHFULNESS_THRESHOLD,
        reason=EXPERIMENTAL_LABEL.strip(),
    )
    usage_sources = (scorer, llm) if llm is not None else (scorer,)
    return result, usage_from_objects(*usage_sources)
