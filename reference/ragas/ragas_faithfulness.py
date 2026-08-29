"""
RAGAS faithfulness demo: grounded vs hallucinated.

Uses single_turn_ascore to score one sample at a time, which sidesteps the
batch-runner hang seen in ragas 0.4.x. Judge is Claude (RAGAS defaults to
OpenAI, so we wrap ChatAnthropic to override it).

PLACEHOLDER: the context/grounded/hallucinated content below is hand-written synthetic
clinical-QA content for exercising the judge mechanism - not TrueLearn content, and not
reviewed by any clinician. See the root README ("Faithfulness-eval reference methodology").

Run:  python3 ragas_faithfulness.py [--json]
Needs: ANTHROPIC_API_KEY in the environment.
"""
import asyncio
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ragas.dataset_schema import SingleTurnSample
from ragas.metrics import Faithfulness
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic
from tools.eval_result import CaseResult, ClaimResult, EvaluationResult
from tools.retry import async_retry_call
from tools.provider_usage import estimate_cost, usage_from_objects

llm = LangchainLLMWrapper(ChatAnthropic(model="claude-sonnet-4-6", temperature=0))
scorer = Faithfulness(llm=llm)

context = [
    "ST elevation in leads II, III, and aVF indicates an inferior wall MI, "
    "most commonly caused by occlusion of the right coronary artery (RCA)."
]

grounded = SingleTurnSample(
    user_input="55-year-old, chest pain, ST elevation in II, III, aVF. Diagnosis and cause?",
    response="Inferior wall myocardial infarction, most commonly caused by "
             "occlusion of the right coronary artery.",
    retrieved_contexts=context,
)

hallucinated = SingleTurnSample(
    user_input="55-year-old, chest pain, ST elevation in II, III, aVF. Diagnosis and cause?",
    response="Inferior wall MI, most commonly caused by occlusion of the left "
             "anterior descending artery, treated with thrombolytics within 90 minutes.",
    retrieved_contexts=context,
)

async def main(json_output: bool):
    started = time.perf_counter()
    g = await async_retry_call(
        lambda: scorer.single_turn_ascore(grounded),
        operation_name="ragas.grounded",
    )
    h = await async_retry_call(
        lambda: scorer.single_turn_ascore(hallucinated),
        operation_name="ragas.hallucinated",
    )
    result = EvaluationResult(
        framework="ragas",
        metric="faithfulness",
        cases=[
            CaseResult(
                case_id="grounded",
                score=g,
                passed=g >= 0.9,
                claims=[
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
                ],
            ),
            CaseResult(
                case_id="hallucinated",
                score=h,
                passed=h >= 0.9,
                claims=[
                    ClaimResult(
                        claim="Inferior wall myocardial infarction",
                        supported=True,
                        evidence=[context[0]],
                    ),
                    ClaimResult(
                        claim="Occlusion of the left anterior descending artery",
                        supported=False,
                    ),
                    ClaimResult(
                        claim="Treatment with thrombolytics within 90 minutes",
                        supported=False,
                    ),
                ],
            ),
        ],
        model="claude-sonnet-4-6",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    usage = usage_from_objects(scorer, llm)
    if usage:
        result.input_tokens = usage["input_tokens"]
        result.output_tokens = usage["output_tokens"]
        result.estimated_cost_usd = estimate_cost(
            usage,
            float(os.getenv("ANTHROPIC_INPUT_USD_PER_MILLION", "0")),
            float(os.getenv("ANTHROPIC_OUTPUT_USD_PER_MILLION", "0")),
        )
    if json_output:
        print(result.to_json())
    else:
        print("\n=== RAGAS Faithfulness ===")
        print("GROUNDED     :", round(g, 3))
        print("HALLUCINATED :", round(h, 3))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit normalized JSON.")
    args = parser.parse_args()
    asyncio.run(main(args.json))
