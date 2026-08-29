"""The field-level rules from the CMS data contract: Unique Name shape, Main Topic/Modifier
character restrictions, and the QuestionType/QuestionFormat dependencies.
"""

from __future__ import annotations

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion

_MAX_UNIQUE_NAME_LENGTH = 50
_PATH_SEPARATOR_CHARS = ("/", "\\")

# Observed live: "QuestionFormat is required when QuestionType is a single question." The exact
# string literal TrueLearn uses for that value is unconfirmed - matched case-insensitively so a
# capitalization difference doesn't silently defeat the check.
_SINGLE_QUESTION_TYPE = "single question"


def _unique_name_length(unique_name: str) -> CheckResult:
    sub_check = "unique_name_length"

    if not unique_name:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
            status=Status.SKIPPED,
            message="unique_name is empty - covered by required_fields_present.",
        )

    within_limit = len(unique_name) <= _MAX_UNIQUE_NAME_LENGTH
    return CheckResult(
        check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
        status=Status.PASS if within_limit else Status.FAIL,
        message=f"{len(unique_name)} of {_MAX_UNIQUE_NAME_LENGTH} characters."
        if within_limit
        else f"{len(unique_name)} characters, exceeds the {_MAX_UNIQUE_NAME_LENGTH}-character limit.",
    )


def _unique_name_no_whitespace(unique_name: str) -> CheckResult:
    sub_check = "unique_name_no_whitespace"

    if not unique_name:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
            status=Status.SKIPPED,
            message="unique_name is empty - covered by required_fields_present.",
        )

    has_whitespace = any(ch.isspace() for ch in unique_name)
    return CheckResult(
        check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
        status=Status.FAIL if has_whitespace else Status.PASS,
        message="Contains whitespace." if has_whitespace else "No whitespace.",
    )


def _unique_name_uniqueness(unique_name: str, config: EvalConfig) -> CheckResult:
    sub_check = "unique_name_uniqueness"

    if config.existing_unique_names is None:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
            status=Status.SKIPPED,
            message="No corpus of existing unique names supplied - "
            "set EvalConfig.existing_unique_names.",
        )

    if not unique_name:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
            status=Status.SKIPPED,
            message="unique_name is empty - covered by required_fields_present.",
        )

    is_duplicate = unique_name in config.existing_unique_names
    return CheckResult(
        check_name="field_constraints", sub_check=sub_check, field_name="unique_name",
        status=Status.FAIL if is_duplicate else Status.PASS,
        message=f'"{unique_name}" already exists in the supplied corpus.'
        if is_duplicate
        else "Not found in the supplied corpus.",
    )


def _no_path_separators(field_name: str, value: str) -> CheckResult:
    sub_check = f"{field_name}_no_path_separators"

    if not value:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name=field_name,
            status=Status.PASS, message="Empty - nothing to violate the rule.",
        )

    has_separator = any(ch in value for ch in _PATH_SEPARATOR_CHARS)
    return CheckResult(
        check_name="field_constraints", sub_check=sub_check, field_name=field_name,
        status=Status.FAIL if has_separator else Status.PASS,
        message=f'"{value}" contains a / or \\ character.' if has_separator else "No / or \\ characters.",
    )


def _question_format_required_for_single(question: GeneratedQuestion) -> CheckResult:
    sub_check = "question_format_required_for_single"
    question_type = (question.question_type or "").strip()

    if question_type.lower() != _SINGLE_QUESTION_TYPE:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="question_format",
            status=Status.SKIPPED,
            message=f'question_type is not "{_SINGLE_QUESTION_TYPE}" - rule does not apply.',
        )

    has_format = bool((question.question_format or "").strip())
    return CheckResult(
        check_name="field_constraints", sub_check=sub_check, field_name="question_format",
        status=Status.PASS if has_format else Status.FAIL,
        message="question_format is present."
        if has_format
        else f'question_type is "{_SINGLE_QUESTION_TYPE}" but question_format is empty.',
    )


def _question_format_allowed_for_type(question: GeneratedQuestion, config: EvalConfig) -> CheckResult:
    """New beyond the C# original: EvalConfig.allowed_question_formats_by_type was declared and
    documented there as controlling behavior, but no check ever read it - a real doc/code mismatch
    found in review. Wiring it in here means the field finally does what it claims."""

    sub_check = "question_format_allowed_for_question_type"
    question_type = (question.question_type or "").strip().lower()

    if not config.allowed_question_formats_by_type:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="question_format",
            status=Status.SKIPPED,
            message="allowed_question_formats_by_type is empty - "
            "format/type pairing is not enforced.",
        )

    allowed_formats = config.allowed_question_formats_by_type.get(question_type)
    if allowed_formats is None:
        return CheckResult(
            check_name="field_constraints", sub_check=sub_check, field_name="question_format",
            status=Status.SKIPPED,
            message=f'No allowed-format list configured for question_type "{question.question_type}".',
        )

    format_value = (question.question_format or "").strip()
    is_allowed = format_value in allowed_formats
    return CheckResult(
        check_name="field_constraints", sub_check=sub_check, field_name="question_format",
        status=Status.PASS if is_allowed else Status.FAIL,
        message=f'question_format "{format_value}" is allowed for "{question.question_type}".'
        if is_allowed
        else f'question_format "{format_value}" is not in the allowed set for '
        f'"{question.question_type}": {sorted(allowed_formats)!r}.',
    )


def field_constraints(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    unique_name = question.unique_name or ""

    return [
        _unique_name_length(unique_name),
        _unique_name_no_whitespace(unique_name),
        _unique_name_uniqueness(unique_name, config),
        _no_path_separators("main_topic", question.main_topic or ""),
        _no_path_separators("modifier", question.modifier or ""),
        _question_format_required_for_single(question),
        _question_format_allowed_for_type(question, config),
    ]
