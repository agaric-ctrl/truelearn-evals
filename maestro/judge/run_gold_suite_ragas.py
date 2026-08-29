"""Tier 3, RAGAS variant: runs the ragas faithfulness judge against the same
maestro/judge/fixtures/synthetic_cases.json used by run_gold_suite.py, and reports whether it
agrees with each case's known (hand-crafted, not SME-verified) expected_pass.

Tests the JUDGE, not a generator - same discipline as run_gold_suite.py, applied with a second,
independently-implemented judge (ragas instead of deepeval) over the exact same cases, so the two
can be compared with tools/reliability.py or tools/compare_results.py.

EXPERIMENTAL. See maestro/judge/__init__.py. This script never gates anything - it is meant to be
run by hand and read by a human.

Requires the SEPARATE ragas venv - do not run this with deepeval installed in the same
environment (click conflict, see requirements-maestro-ragas.txt):
    python3 -m venv .venv-maestro-ragas
    .venv-maestro-ragas/bin/pip install -r requirements-maestro-ragas.txt
    .venv-maestro-ragas/bin/python maestro/judge/run_gold_suite_ragas.py [--json]

Needs: ANTHROPIC_API_KEY in the environment. Makes real, paid model calls.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.judge.faithfulness_ragas import judge_faithfulness_ragas
from maestro.judge.shared import build_actual_output
from tools.eval_result import ClaimResult, EvaluationResult
from tools.provider_usage import estimate_cost

BANNER = (
    "=" * 78 + "\n"
    "EXPERIMENTAL - this judge is validated only against 6 hand-crafted synthetic cases,\n"
    "NOT real SME-graded data. Its agreement with real SME judgment has not been measured.\n"
    "Not evidence. Not wired into any gate. RAGAS variant - compare against run_gold_suite.py's\n"
    "deepeval verdicts on the same cases; agreement or disagreement is itself the finding.\n" + "=" * 78
)

DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_cases.json"


def load_fixture(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


async def run(fixture_path: Path) -> tuple[list, dict | None, list[dict]]:
    cases_data = load_fixture(fixture_path)
    cases = []
    usage_total = None
    for case_data in cases_data:
        result, usage = await judge_faithfulness_ragas(
            case_data["case_id"],
            case_data["source"],
            case_data["topic"],
            build_actual_output(**case_data["generated"]),
        )
        result.claims = [ClaimResult(**claim) for claim in case_data["claims"]]
        cases.append(result)
        usage_total = usage or usage_total
    return cases, usage_total, cases_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Maestro faithfulness judge (RAGAS variant) against its synthetic gold suite.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true", help="Emit normalized JSON instead of plain text.")
    args = parser.parse_args()

    print(BANNER, file=sys.stderr)

    cases, usage_total, cases_data = asyncio.run(run(args.fixture))

    evaluation = EvaluationResult(
        framework="maestro_ragas",
        metric="faithfulness_experimental_unvalidated",
        cases=cases,
        model="claude-sonnet-4-6",
    )
    if usage_total:
        evaluation.input_tokens = usage_total["input_tokens"]
        evaluation.output_tokens = usage_total["output_tokens"]
        evaluation.estimated_cost_usd = estimate_cost(
            usage_total,
            float(os.getenv("ANTHROPIC_INPUT_USD_PER_MILLION", "0")),
            float(os.getenv("ANTHROPIC_OUTPUT_USD_PER_MILLION", "0")),
        )

    if args.json:
        print(evaluation.to_json())
    else:
        for case in cases:
            print(f"\n=== {case.case_id} ===")
            print("score :", case.score)
            print("passed:", case.passed)
            print("reason:", case.reason)

    print(BANNER, file=sys.stderr)

    mismatches = [
        case for case, raw in zip(cases, cases_data) if case.passed != raw["expected_pass"]
    ]
    if mismatches:
        print(
            f"\n{len(mismatches)} case(s) disagreed with the known label: "
            f"{[case.case_id for case in mismatches]}",
            file=sys.stderr,
        )
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
