"""Readability check: approximates the strategy doc's "length/depth/density" calibration concern
with a real, off-the-shelf metric - py-readability-metrics's Flesch-Kincaid grade-level score -
rather than a hand-rolled formula, per docs/qa-context/TIER1_CHECKS_TASK.md's explicit direction.

NAMED readability_check.py, NOT readability.py: verified directly (not assumed) that naming this
module "readability" shadows the third-party "readability" package it imports from whenever this
module's own directory ends up first on sys.path (e.g. running a script directly, rather than via
`python -m`) - causing a circular-import ImportError. The registered check name/function are both
still plain "readability"; only the file/module name differs.

PLACEHOLDER THRESHOLD: EvalConfig.readability_grade_level_range defaults to None (Skip), same
convention as every other not-yet-confirmed rule in this package (see reference_style_pattern,
table_placement). Any illustrative band this repo might configure is NOT validated against real
Maestro content or SME judgment - real calibration needs golden-set data that doesn't exist yet
(see docs/qa-context/MAESTRO_QA_FINDINGS.md). The computed grade level is always reported in
`details` even when Skipped, so it's there for future calibration work.

OFFLINE BY DESIGN: py-readability-metrics's sentence tokenizer (NLTK's punkt_tab) normally fetches
its data from the network via nltk.download() on first use - verified directly, not assumed, by
triggering that failure in this sandbox - which would break this project's offline-CI guardrail.
maestro/checks/data/nltk_data/ bundles just the English tokenizer data (~244KB, English only, not
NLTK's full ~15MB multi-language download) so this check never makes a network call, in CI or
anywhere else. Verified end-to-end with nltk.data.path pointed ONLY at the bundled directory.

VERIFIED, NOT ASSUMED: py-readability-metrics's own FleschKincaid.grade_level is always
str(round(score)) by that library's own implementation - a string, never a number, regardless of
value (confirmed by reading its source after a comparison crashed on a real sample, not caught by
eyeballing one manual test value). Cast to int() before any numeric comparison.
"""

from __future__ import annotations

from pathlib import Path

import nltk
from readability import Readability
from readability.exceptions import ReadabilityException

from maestro.check_result import CheckResult, Status
from maestro.html_text import strip_tags_and_decode
from maestro.models import EvalConfig, GeneratedQuestion

_BUNDLED_NLTK_DATA = str(Path(__file__).resolve().parent / "data" / "nltk_data")
if _BUNDLED_NLTK_DATA not in nltk.data.path:
    nltk.data.path.insert(0, _BUNDLED_NLTK_DATA)

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")


def _score_field(field_name: str, fragment: str | None, config: EvalConfig) -> CheckResult:
    text = strip_tags_and_decode(fragment or "")
    if not text.strip():
        return CheckResult(
            check_name="readability", field_name=field_name, status=Status.SKIPPED,
            message="Field is empty - nothing to score.",
        )

    try:
        # py-readability-metrics's grade_level is always str(round(score)) by its own
        # implementation (verified directly, not assumed) - never a number, regardless of value.
        grade_level = int(Readability(text).flesch_kincaid().grade_level)
    except ReadabilityException as error:
        return CheckResult(
            check_name="readability", field_name=field_name, status=Status.SKIPPED,
            message=f"Not enough text to score reliably: {error}",
        )

    details = {"flesch_kincaid_grade_level": grade_level}

    if config.readability_grade_level_range is None:
        return CheckResult(
            check_name="readability", field_name=field_name, status=Status.SKIPPED,
            message=f"Grade level {grade_level} computed, but no target range is configured - "
            "see EvalConfig.readability_grade_level_range (PLACEHOLDER, not yet calibrated).",
            details=details,
        )

    low, high = config.readability_grade_level_range
    in_range = low <= grade_level <= high
    return CheckResult(
        check_name="readability", field_name=field_name,
        status=Status.PASS if in_range else Status.FAIL,
        message=f"Grade level {grade_level} is within the configured {low}-{high} range."
        if in_range
        else f"Grade level {grade_level} is outside the configured {low}-{high} range.",
        details=details,
    )


def readability(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    return [
        _score_field(field_name, getattr(question, field_name, None), config)
        for field_name in _HTML_FIELDS
    ]
