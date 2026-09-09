"""Enforces sequential, gap-free case numbering (Case 1, Case 2, ... with no gaps) across all of a
question's HTML fields, combined. Shares case-boundary detection with teaching_case_standard.py -
see _case_blocks.py for the placeholder-heuristic caveat (real case markup is unconfirmed).
"""

from __future__ import annotations

from maestro.check_result import CheckResult, Status
from maestro.checks._case_blocks import extract_case_blocks
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")


def case_numbering(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    all_cases = []
    for field_name in _HTML_FIELDS:
        all_cases.extend(extract_case_blocks(field_name, getattr(question, field_name, None)))

    if not all_cases:
        return [CheckResult(
            check_name="case_numbering", status=Status.SKIPPED,
            message='No "Case N" sections found in any field - nothing to check.',
        )]

    unparsed = [case.label_text for case in all_cases if case.number is None]
    if unparsed:
        return [CheckResult(
            check_name="case_numbering", status=Status.FAIL,
            message=f"Case label(s) found that didn't parse a number: {unparsed}.",
        )]

    numbers = [case.number for case in all_cases]
    expected = list(range(1, len(numbers) + 1))
    if numbers == expected:
        return [CheckResult(
            check_name="case_numbering", status=Status.PASS,
            message=f"{len(numbers)} case(s), sequentially numbered 1-{len(numbers)}.",
        )]
    return [CheckResult(
        check_name="case_numbering", status=Status.FAIL,
        message=f"Case numbers are {numbers}, expected sequential 1..{len(numbers)} with no gaps.",
        details={"numbers": numbers},
    )]
