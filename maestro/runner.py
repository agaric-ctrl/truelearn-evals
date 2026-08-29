"""CLI + library entry point for running Maestro question checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maestro.check_result import CheckResult, QuestionCheckReport, render_summary
from maestro.checks import DEFAULT_CHECKS, CheckFunction
from maestro.models import EvalConfig, GeneratedQuestion, load_eval_config, load_generated_question


def run_checks(
    question: GeneratedQuestion,
    config: EvalConfig,
    checks: list[CheckFunction] | None = None,
) -> QuestionCheckReport:
    results: list[CheckResult] = []
    for check in checks if checks is not None else DEFAULT_CHECKS:
        results.extend(check(question, config))
    return QuestionCheckReport(unique_name=question.unique_name, results=results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Maestro generated-question checks.")
    parser.add_argument("question", type=Path, help="Path to a GeneratedQuestion JSON file.")
    parser.add_argument("--config", type=Path, default=None,
                         help="Path to an EvalConfig JSON file (defaults to all-unconfirmed).")
    parser.add_argument("--json", action="store_true", help="Emit the JSON report instead of plain text.")
    parser.add_argument("--no-gate", action="store_true",
                         help="Always exit 0 even if a check FAILs (useful while calibrating EvalConfig).")
    args = parser.parse_args()

    question = load_generated_question(json.loads(args.question.read_text(encoding="utf-8")))
    config = (
        load_eval_config(json.loads(args.config.read_text(encoding="utf-8")))
        if args.config else EvalConfig()
    )

    report = run_checks(question, config)
    print(report.to_json() if args.json else render_summary(report))

    return 1 if (report.has_failures and not args.no_gate) else 0


if __name__ == "__main__":
    raise SystemExit(main())
