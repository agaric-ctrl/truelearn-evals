"""Deterministic revision-loop checks over a Maestro generation payload (history[] + chat_history[]).

Reuses Tier 1's own CheckResult/Status/run_checks machinery directly rather than inventing
parallel infrastructure - every history[] entry is run through Tier 1's existing 6 checks, so a
regressed older revision surfaces exactly like a broken single question would.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.check_result import CheckResult, QuestionCheckReport, Status, render_summary
from maestro.checks import DEFAULT_CHECKS
from maestro.generation.payload import (
    GenerationPayload,
    history_entry_as_generated_question,
    load_generation_payload,
)
from maestro.models import EvalConfig, load_eval_config
from maestro.runner import run_checks


def _history_head_check(payload: GenerationPayload) -> list[CheckResult]:
    """FAILs (not Skips) on an empty history[] or an unparseable history[0] - unlike every other
    check in this file, this one asserts a confirmed invariant ("history[0] is the latest accepted
    generation"), not an open spec question, so there's nothing to Skip on."""

    if not payload.history:
        return [CheckResult(
            check_name="history_head_present", status=Status.FAIL,
            message="history[] is empty - history[0] should be the latest accepted generation.",
        )]

    parsed = history_entry_as_generated_question(payload.history[0])
    if parsed is None:
        return [CheckResult(
            check_name="history_head_parses", status=Status.FAIL,
            message="history[0] does not parse as a well-formed GeneratedQuestion.",
        )]
    return [CheckResult(
        check_name="history_head_parses", status=Status.PASS,
        message=f"history[0] parses as GeneratedQuestion({parsed.unique_name!r}).",
    )]


def _history_entries_tier1_checks(payload: GenerationPayload, config: EvalConfig) -> list[CheckResult]:
    """Every history[] entry - not just the latest - is run through Tier 1's own DEFAULT_CHECKS.
    Original check_name/sub_check are kept as-is; location is composed into field_name (e.g.
    "history[2].explanation_header") so a report consumer keyed on check_name works unmodified
    regardless of whether a result came from runner.run_checks directly or from here."""

    results: list[CheckResult] = []
    for index, entry in enumerate(payload.history):
        parsed = history_entry_as_generated_question(entry)
        if parsed is None:
            results.append(CheckResult(
                check_name="history_entry_parses", status=Status.FAIL,
                field_name=f"history[{index}]",
                message=f"history[{index}] does not parse as a well-formed GeneratedQuestion.",
            ))
            continue

        for result in run_checks(parsed, config, checks=DEFAULT_CHECKS).results:
            located = f"history[{index}]" + (f".{result.field_name}" if result.field_name else "")
            results.append(CheckResult(
                check_name=result.check_name, status=result.status, message=result.message,
                field_name=located, sub_check=result.sub_check, details=result.details,
            ))
    return results


def _chat_history_alignment_unconfirmed(payload: GenerationPayload) -> list[CheckResult]:
    return [CheckResult(
        check_name="chat_history_alignment", status=Status.SKIPPED,
        message="Relationship between len(chat_history) and len(history), and chat_history's own "
        "entry shape beyond free-text instruction, are unconfirmed - see README Open Questions.",
    )]


def check_generation_payload(payload: GenerationPayload, config: EvalConfig) -> QuestionCheckReport:
    results = [
        *_history_head_check(payload),
        *_history_entries_tier1_checks(payload, config),
        *_chat_history_alignment_unconfirmed(payload),
    ]
    head = history_entry_as_generated_question(payload.history[0]) if payload.history else None
    return QuestionCheckReport(unique_name=head.unique_name if head else None, results=results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Maestro revision-loop checks over a generation payload.")
    parser.add_argument("payload", type=Path, help="Path to a GenerationPayload JSON file.")
    parser.add_argument("--config", type=Path, default=None,
                         help="Path to an EvalConfig JSON file (defaults to all-unconfirmed).")
    parser.add_argument("--json", action="store_true", help="Emit the JSON report instead of plain text.")
    parser.add_argument("--no-gate", action="store_true",
                         help="Always exit 0 even if a check FAILs (useful while calibrating EvalConfig).")
    args = parser.parse_args()

    payload = load_generation_payload(json.loads(args.payload.read_text(encoding="utf-8")))
    config = (
        load_eval_config(json.loads(args.config.read_text(encoding="utf-8")))
        if args.config else EvalConfig()
    )

    report = check_generation_payload(payload, config)
    print(report.to_json() if args.json else render_summary(report))

    return 1 if (report.has_failures and not args.no_gate) else 0


if __name__ == "__main__":
    raise SystemExit(main())
