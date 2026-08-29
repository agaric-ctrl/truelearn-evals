"""Unique Name, Question Text, Explanation Header and Explanation Footer are required in the
CMS data contract. Bottom Line's rule is unconfirmed (EvalConfig.require_bottom_line), so it's
checked only once that's set.
"""

from __future__ import annotations

from maestro.check_result import CheckResult, Status
from maestro.html_text import strip_tags_and_decode
from maestro.models import EvalConfig, GeneratedQuestion

_UNCONDITIONALLY_REQUIRED_FIELDS = (
    "unique_name",
    "question_text",
    "explanation_header",
    "explanation_footer",
)


def _emptiness_result(field_name: str, raw_value: str | None) -> CheckResult:
    text = strip_tags_and_decode(raw_value or "")
    is_present = bool(text.strip())
    return CheckResult(
        check_name="required_fields_present",
        field_name=field_name,
        status=Status.PASS if is_present else Status.FAIL,
        message=(
            f"{field_name} has visible content."
            if is_present
            else f"{field_name} is empty after stripping HTML tags and decoding entities."
        ),
    )


def required_fields_present(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    results = [
        _emptiness_result(name, getattr(question, name))
        for name in _UNCONDITIONALLY_REQUIRED_FIELDS
    ]

    if config.require_bottom_line is None:
        results.append(CheckResult(
            check_name="required_fields_present",
            field_name="bottom_line",
            status=Status.SKIPPED,
            message="require_bottom_line is unconfirmed - set EvalConfig.require_bottom_line.",
        ))
    elif config.require_bottom_line is False:
        results.append(CheckResult(
            check_name="required_fields_present",
            field_name="bottom_line",
            status=Status.PASS,
            message="Optional per current config.",
        ))
    else:
        results.append(_emptiness_result("bottom_line", question.bottom_line))

    return results
