"""N-gram-overlap check for sentence-level redundancy within a single field - the deterministic
approximation of "density/padding" named in docs/qa-context/MAESTRO_QA_FINDINGS.md Section 2 (a
dimension previously assumed to need an LLM judge, per the QA lead's own strategy-doc comment).

Compares each sentence's word n-grams against every earlier sentence in the same field; a pair
whose n-gram overlap ratio (Jaccard: |intersection| / |union|) exceeds
EvalConfig.max_ngram_overlap_ratio is flagged as likely restating rather than adding information.

PLACEHOLDER THRESHOLD: max_ngram_overlap_ratio defaults to None (Skip), same convention as every
other not-yet-confirmed rule in this package. Every sentence pair's overlap ratio is always
computed and reported in `details` (even when Skipped), so real calibration has data to start from
once golden-set content exists.
"""

from __future__ import annotations

import re

from maestro.check_result import CheckResult, Status
from maestro.html_text import strip_tags_and_decode
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_WORD_RE = re.compile(r"[a-z0-9']+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def _ngrams(sentence: str, n: int) -> set:
    words = _WORD_RE.findall(sentence.lower())
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _overlap_ratio(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _check_field(field_name: str, fragment: str | None, config: EvalConfig) -> CheckResult:
    text = strip_tags_and_decode(fragment or "")
    sentences = _sentences(text)
    if len(sentences) < 2:
        return CheckResult(
            check_name="density_redundancy", field_name=field_name, status=Status.SKIPPED,
            message="Fewer than 2 sentences - nothing to compare.",
        )

    ngram_sets = [_ngrams(sentence, config.ngram_size) for sentence in sentences]
    pairs = []
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            ratio = _overlap_ratio(ngram_sets[i], ngram_sets[j])
            if ratio > 0:
                pairs.append({"sentence_a": i, "sentence_b": j, "overlap_ratio": round(ratio, 3)})

    details = {"sentence_count": len(sentences), "pairs": pairs}

    if config.max_ngram_overlap_ratio is None:
        return CheckResult(
            check_name="density_redundancy", field_name=field_name, status=Status.SKIPPED,
            message=f"{len(sentences)} sentence(s) compared, but no overlap threshold is "
            "configured - see EvalConfig.max_ngram_overlap_ratio (PLACEHOLDER, not yet calibrated).",
            details=details,
        )

    flagged = [pair for pair in pairs if pair["overlap_ratio"] > config.max_ngram_overlap_ratio]
    if flagged:
        return CheckResult(
            check_name="density_redundancy", field_name=field_name, status=Status.FAIL,
            message=f"{len(flagged)} sentence pair(s) exceed the configured "
            f"{config.max_ngram_overlap_ratio} overlap threshold.",
            details={**details, "flagged": flagged},
        )
    return CheckResult(
        check_name="density_redundancy", field_name=field_name, status=Status.PASS,
        message=f"{len(sentences)} sentence(s) compared, no pair exceeds the configured "
        f"{config.max_ngram_overlap_ratio} overlap threshold.",
        details=details,
    )


def density_redundancy(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    return [
        _check_field(field_name, getattr(question, field_name, None), config)
        for field_name in _HTML_FIELDS
    ]
