"""House style flags a typed "->" where an arrow character (e.g. "→") is required. Always-on -
unlike the Skip-gated placeholder checks in this package, docs/qa-context/TIER1_CHECKS_TASK.md
states this as a firm rule, not something pending confirmation.
"""

from __future__ import annotations

from maestro.check_result import CheckResult, Status
from maestro.html_text import strip_tags_and_decode
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_TYPED_ARROW = "->"


def _check_field(field_name: str, fragment: str | None) -> CheckResult:
    text = strip_tags_and_decode(fragment or "")
    count = text.count(_TYPED_ARROW)
    if count == 0:
        return CheckResult(
            check_name="arrow_style", field_name=field_name, status=Status.PASS,
            message='No typed "->" found.',
        )
    return CheckResult(
        check_name="arrow_style", field_name=field_name, status=Status.FAIL,
        message=f'Found {count} typed "->" - house style requires an arrow character (e.g. "→").',
        details={"count": count},
    )


def arrow_style(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    return [
        _check_field(field_name, getattr(question, field_name, None))
        for field_name in _HTML_FIELDS
    ]
