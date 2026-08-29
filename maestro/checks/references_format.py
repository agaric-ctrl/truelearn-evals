"""'References not formatted to TrueLearn house style' was flagged as a real Maestro failure mode,
but the style spec itself is not written down anywhere this harness can read (HUMAN INPUT NEEDED -
reference style spec). Reports Skipped rather than guessing a pattern, until
EvalConfig.reference_style_pattern carries something confirmed.
"""

from __future__ import annotations

import re

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion


def references_format(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    if config.reference_style_pattern is None:
        return [CheckResult(
            check_name="references_format", status=Status.SKIPPED,
            message="No reference style spec configured - see EvalConfig.reference_style_pattern.",
        )]

    if not question.references:
        return [CheckResult(
            check_name="references_format", status=Status.PASS, message="No references present.",
        )]

    pattern = re.compile(config.reference_style_pattern)
    results = []
    for index, reference in enumerate(question.references):
        matches = pattern.fullmatch(reference) is not None
        results.append(CheckResult(
            check_name="references_format", field_name=f"references[{index}]",
            status=Status.PASS if matches else Status.FAIL,
            message="Matches the configured style pattern."
            if matches
            else f'"{reference}" does not match the configured style pattern.',
        ))
    return results
