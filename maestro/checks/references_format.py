"""References format: TrueLearn house style for a question's references list.

Five independent sub-checks:
- reference_count: 3-5 references. docs/qa-context/TIER1_CHECKS_TASK.md states this as a firm
  rule, not something pending confirmation - hardcoded, matching field_constraints.py's convention
  for settled numeric rules (e.g. _MAX_UNIQUE_NAME_LENGTH), not an EvalConfig field.
- reverse_chronological_order: references must be ordered newest-first, by the last 4-digit year
  found in each reference string. A reference with no extractable year is excluded from the
  ordering comparison rather than guessed at.
- citation_type_caps / excluded_sources: docs/qa-context/TIER1_CHECKS_TASK.md names "at most one
  of each of two specific citation types" and "excludes certain named non-authoritative sources"
  without saying which types or which sources - genuinely unconfirmed, not guessed at here.
  Skip-gated on EvalConfig, same convention as every other not-yet-confirmed rule in this package,
  until someone supplies the real patterns/names.
- style_pattern: the original stub, unchanged - a full reference string must match a configured
  regex. Still Skipped until EvalConfig.reference_style_pattern is set.
"""

from __future__ import annotations

import re

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion

_MIN_REFERENCES = 3
_MAX_REFERENCES = 5
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _reference_count(references: list[str]) -> CheckResult:
    count = len(references)
    in_range = _MIN_REFERENCES <= count <= _MAX_REFERENCES
    return CheckResult(
        check_name="references_format", sub_check="reference_count",
        status=Status.PASS if in_range else Status.FAIL,
        message=f"{count} reference(s), within the required {_MIN_REFERENCES}-{_MAX_REFERENCES}."
        if in_range
        else f"{count} reference(s), required {_MIN_REFERENCES}-{_MAX_REFERENCES}.",
    )


def _extract_year(reference: str) -> int | None:
    years = _YEAR_RE.findall(reference)
    return int(years[-1]) if years else None  # last match: a citation year usually trails the string


def _reverse_chronological_order(references: list[str]) -> CheckResult:
    dated = [(index, _extract_year(reference)) for index, reference in enumerate(references)]
    dated = [(index, year) for index, year in dated if year is not None]

    if len(dated) < 2:
        return CheckResult(
            check_name="references_format", sub_check="reverse_chronological_order",
            status=Status.SKIPPED,
            message="Fewer than 2 references have an extractable year - nothing to order.",
        )

    years = [year for _, year in dated]
    is_ordered = all(years[i] >= years[i + 1] for i in range(len(years) - 1))
    return CheckResult(
        check_name="references_format", sub_check="reverse_chronological_order",
        status=Status.PASS if is_ordered else Status.FAIL,
        message="References with an extractable year are in reverse-chronological order."
        if is_ordered
        else f"References are not in reverse-chronological order (years found, in order: {years}).",
        details={"years_by_reference_index": dict(dated)},
    )


def _citation_type_caps(references: list[str], config: EvalConfig) -> CheckResult:
    if not config.reference_citation_type_patterns or not config.max_per_citation_type:
        return CheckResult(
            check_name="references_format", sub_check="citation_type_caps", status=Status.SKIPPED,
            message="No citation-type patterns/caps configured - see "
            "EvalConfig.reference_citation_type_patterns / max_per_citation_type.",
        )

    violations = []
    for type_name, pattern in config.reference_citation_type_patterns.items():
        max_allowed = config.max_per_citation_type.get(type_name)
        if max_allowed is None:
            continue
        matches = sum(1 for reference in references if re.search(pattern, reference))
        if matches > max_allowed:
            violations.append(f"{type_name}: {matches} found, max {max_allowed} allowed")

    return CheckResult(
        check_name="references_format", sub_check="citation_type_caps",
        status=Status.FAIL if violations else Status.PASS,
        message="; ".join(violations) if violations else "No citation-type cap exceeded.",
    )


def _excluded_sources(references: list[str], config: EvalConfig) -> CheckResult:
    if config.excluded_reference_sources is None:
        return CheckResult(
            check_name="references_format", sub_check="excluded_sources", status=Status.SKIPPED,
            message="No excluded-source list configured - see EvalConfig.excluded_reference_sources.",
        )

    found = sorted({
        source for source in config.excluded_reference_sources
        for reference in references
        if source.lower() in reference.lower()
    })
    return CheckResult(
        check_name="references_format", sub_check="excluded_sources",
        status=Status.FAIL if found else Status.PASS,
        message=f"Excluded source(s) found: {', '.join(found)}." if found
        else "No excluded sources found.",
    )


def _style_pattern(references: list[str], config: EvalConfig) -> list[CheckResult]:
    if config.reference_style_pattern is None:
        return [CheckResult(
            check_name="references_format", sub_check="style_pattern", status=Status.SKIPPED,
            message="No reference style spec configured - see EvalConfig.reference_style_pattern.",
        )]

    pattern = re.compile(config.reference_style_pattern)
    return [
        CheckResult(
            check_name="references_format", sub_check="style_pattern",
            field_name=f"references[{index}]",
            status=Status.PASS if pattern.fullmatch(reference) else Status.FAIL,
            message="Matches the configured style pattern."
            if pattern.fullmatch(reference)
            else f'"{reference}" does not match the configured style pattern.',
        )
        for index, reference in enumerate(references)
    ]


def references_format(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    references = question.references or []
    return [
        _reference_count(references),
        _reverse_chronological_order(references),
        _citation_type_caps(references, config),
        _excluded_sources(references, config),
        *_style_pattern(references, config),
    ]
