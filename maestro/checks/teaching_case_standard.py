"""Enforces two style rules named in docs/qa-context/TIER1_CHECKS_TASK.md for numbered teaching
cases within an explanation field: a hard 3-sentence ceiling per case, and a bolded "Key teaching:"
lead-in that must appear inline within the case - never as its own separate paragraph.

Shares case-boundary detection with case_numbering.py - see _case_blocks.py for the
placeholder-heuristic caveat (real case markup is unconfirmed).
"""

from __future__ import annotations

import re

from maestro.check_result import CheckResult, Status
from maestro.checks._case_blocks import extract_case_blocks
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_MAX_SENTENCES_PER_CASE = 3
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_KEY_TEACHING_RE = re.compile(r"^\s*key teaching\s*:", re.IGNORECASE)


def _sentence_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return len([s for s in _SENTENCE_SPLIT_RE.split(stripped) if s.strip()])


def _find_key_teaching(paragraph) -> tuple[bool, bool]:
    """Returns (found, starts_paragraph) for a bolded "Key teaching:" lead-in in one paragraph -
    "bolded" meaning inside a <strong>/<b> element, "starts_paragraph" meaning that element is the
    very first content of the paragraph (no preceding text or sibling)."""

    for bold in list(paragraph.iter("strong")) + list(paragraph.iter("b")):
        text = (bold.text or "").strip()
        if not _KEY_TEACHING_RE.match(text):
            continue
        preceding_text = (paragraph.text or "").strip()
        first_child = next(iter(paragraph), None)
        starts_paragraph = not preceding_text and first_child is bold
        return True, starts_paragraph
    return False, False


def _check_case(case) -> list[CheckResult]:
    results = []
    full_text = " ".join(p.text_content().strip() for p in case.paragraphs)
    sentence_count = _sentence_count(full_text)

    results.append(CheckResult(
        check_name="teaching_case_standard", sub_check="sentence_ceiling", field_name=case.field_name,
        status=Status.PASS if sentence_count <= _MAX_SENTENCES_PER_CASE else Status.FAIL,
        message=f"{case.label_text}: {sentence_count} sentence(s) (limit {_MAX_SENTENCES_PER_CASE})."
        if sentence_count <= _MAX_SENTENCES_PER_CASE
        else f"{case.label_text}: {sentence_count} sentences, exceeds the "
             f"{_MAX_SENTENCES_PER_CASE}-sentence limit.",
    ))

    found, starts_paragraph = False, False
    for paragraph in case.paragraphs:
        found, starts_paragraph = _find_key_teaching(paragraph)
        if found:
            break

    if not found:
        results.append(CheckResult(
            check_name="teaching_case_standard", sub_check="key_teaching_present",
            field_name=case.field_name, status=Status.FAIL,
            message=f'{case.label_text}: no bolded "Key teaching:" sentence found.',
        ))
    elif starts_paragraph:
        results.append(CheckResult(
            check_name="teaching_case_standard", sub_check="key_teaching_inline",
            field_name=case.field_name, status=Status.FAIL,
            message=f'{case.label_text}: "Key teaching:" starts its own paragraph; '
            "it must appear inline within the case.",
        ))
    else:
        results.append(CheckResult(
            check_name="teaching_case_standard", sub_check="key_teaching_inline",
            field_name=case.field_name, status=Status.PASS,
            message=f'{case.label_text}: "Key teaching:" appears inline.',
        ))
    return results


def teaching_case_standard(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    found_any = False
    for field_name in _HTML_FIELDS:
        for case in extract_case_blocks(field_name, getattr(question, field_name, None)):
            found_any = True
            results.extend(_check_case(case))

    if not found_any:
        return [CheckResult(
            check_name="teaching_case_standard", status=Status.SKIPPED,
            message='No "Case N" sections found in any field - nothing to check.',
        )]
    return results
