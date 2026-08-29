"""CLI: compares Tier 3 judge verdicts (deepeval vs RAGAS, or any EvaluationResult-shaped JSON
files) on the same synthetic_cases.json cases, via tools/compare_results.py.

Input: two or more paths to previously-saved --json output from run_gold_suite.py,
run_gold_suite_ragas.py, or tools/promptfoo_results.py's normalized Promptfoo output - each one a
single EvaluationResult object. Never runs a judge itself: this only combines and compares
already-produced results, so it has no model-calling dependency of its own and needs only stdlib +
tools/compare_results.py - it runs identically in .venv-maestro, .venv-maestro-ragas, or a bare
interpreter with no maestro/ deps installed at all.

Purpose, not mechanism: two (or three) independently-implemented judges agreeing on the same
synthetic cases is a mild confidence signal; disagreeing is itself the finding - it flags exactly
where the "faithfulness judge" concept is shaky, before any of them is treated as evidence against
real SME grading. See maestro/judge/faithfulness_ragas.py's module docstring for the fuller
rationale. Not wired into any gate - this is read-by-a-human tooling, same as run_gold_suite.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.compare_results import compare_results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Tier 3 judge verdicts across two or more --json EvaluationResult files.",
    )
    parser.add_argument(
        "results", type=Path, nargs="+",
        help="Paths to EvaluationResult JSON files (e.g. deepeval + ragas run_gold_suite output).",
    )
    args = parser.parse_args()

    if len(args.results) < 2:
        parser.error("at least two result files are required to compare.")

    results = [json.loads(path.read_text(encoding="utf-8")) for path in args.results]
    report = compare_results(results)
    print(json.dumps(report, indent=2))

    if report["disagreement_count"]:
        disagreeing_ids = [case["case_id"] for case in report["cases"] if not case["agreement"]]
        print(
            f"\n{report['disagreement_count']} case(s) disagreed across judges: {disagreeing_ids}",
            file=sys.stderr,
        )

    return 1 if report["disagreement_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
