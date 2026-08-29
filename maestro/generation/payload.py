"""Data model for Maestro's real generation payload - the confirmed subset only.

Confirmed (from a real TrueLearn system-architecture briefing, not invented): question generation
grounds on a live web search (references.query + references.results[], each an external URL with a
relevance score); Maestro keeps a revision/chat-history loop (history[] - history[0] is the latest
accepted generation - and chat_history[], free-text revision instructions).

Explicitly UNCONFIRMED, and deliberately not guessed here: whether results[] entries ever carry
retrieved page text (ReferenceResult.text stays optional, default None); the exact shape of a
history[]/chat_history[] entry beyond what's stated above (kept as raw dict); whether
len(chat_history) has any fixed relationship to len(history).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields

from maestro.models import GeneratedQuestion, load_generated_question


@dataclass
class ReferenceResult:
    url: str = ""
    score: float | None = None
    text: str | None = None  # UNCONFIRMED whether the real payload ever populates this


@dataclass
class ReferencesPayload:
    query: str = ""
    results: list[ReferenceResult] = field(default_factory=list)


@dataclass
class GenerationRecord:
    """One history[] entry. Only 'it has its own references' is confirmed; the rest of its shape
    is unconfirmed, so it stays in raw rather than being modeled."""

    references: ReferencesPayload = field(default_factory=ReferencesPayload)
    raw: dict = field(default_factory=dict)


@dataclass
class GenerationPayload:
    history: list[GenerationRecord] = field(default_factory=list)  # history[0] = latest accepted (confirmed)
    chat_history: list[dict] = field(default_factory=list)  # shape beyond free text unconfirmed
    raw: dict = field(default_factory=dict)


def load_reference_result(data: dict) -> ReferenceResult:
    return ReferenceResult(
        url=data.get("url", ""),
        score=data.get("score"),
        text=data.get("text"),
    )


def load_references_payload(data: dict) -> ReferencesPayload:
    return ReferencesPayload(
        query=data.get("query", ""),
        results=[load_reference_result(item) for item in (data.get("results") or [])],
    )


def load_generation_record(data: dict) -> GenerationRecord:
    return GenerationRecord(
        references=load_references_payload(data.get("references") or {}),
        raw=data,
    )


def load_generation_payload(data: dict) -> GenerationPayload:
    return GenerationPayload(
        history=[load_generation_record(item) for item in (data.get("history") or [])],
        chat_history=list(data.get("chat_history") or []),
        raw=data,
    )


# GeneratedQuestion's own "references" field (house-style citation strings, list[str]) is a
# different concept from this module's ReferencesPayload (web-search query + URL results) that
# happens to share a name. Always excluded below so a real history[] entry that nests question
# fields alongside its own "references" key can never silently assign the wrong-shaped value into
# GeneratedQuestion.references - dataclasses don't enforce types at construction, so that would
# corrupt every downstream Tier 1 check that iterates it as list[str], not raise an error.
_GENERATED_QUESTION_FIELDS = {f.name for f in dataclass_fields(GeneratedQuestion)} - {"references"}


def history_entry_as_generated_question(record: GenerationRecord) -> GeneratedQuestion | None:
    """Returns None when record.raw doesn't look like a GeneratedQuestion at all (zero matching
    keys) - NOT merely when construction "fails". Every GeneratedQuestion field already has a
    default, so load_generated_question({}) would otherwise silently succeed with an all-empty
    object instead of signaling "wrong shape". That distinction matters: a real structural problem
    in actual content should surface as Tier 1 FAILs, not get confused with "we guessed the wrong
    raw shape entirely".
    """

    if not isinstance(record.raw, dict):
        return None

    filtered = {key: value for key, value in record.raw.items() if key in _GENERATED_QUESTION_FIELDS}
    if not filtered:
        return None
    try:
        return load_generated_question(filtered)
    except (TypeError, ValueError):
        return None
