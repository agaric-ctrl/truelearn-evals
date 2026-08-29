"""Converts real Maestro generation output into the harness's GoldenExample candidate-batch shape
(see maestro/examples/sample_golden_batch.jsonl) - the seam that golden/generate_pool.py has always
needed and never had; that fixture's own _placeholder note names this exact gap.

Only converts what's confirmed: history[0], via generation.payload.history_entry_as_generated_question().
Everything about *how* a batch is assembled - candidate id, exam bank routing, whether a generation
was a fresh topic or an edit, and what its input looked like - is unconfirmed at the Payload API
level (see payload_api.py), so it's taken as explicit caller-supplied metadata here rather than
guessed out of the raw payload.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from maestro.generation.payload import (
    GenerationPayload,
    history_entry_as_generated_question,
    load_generation_payload,
)
from maestro.golden.models import GoldenExample


@dataclass
class CandidateMetadata:
    """Per-record facts the Payload API boundary doesn't confirm the shape of yet, so they're
    supplied explicitly by whatever calls this rather than derived from the raw payload."""

    example_id: str = ""
    exam_bank: str = ""
    source_type: str = ""
    input_data: dict = field(default_factory=dict)
    ac_ref: str | None = None
    tags: list[str] = field(default_factory=list)


def load_candidate_metadata(data: dict) -> CandidateMetadata:
    return CandidateMetadata(
        example_id=data.get("example_id", ""),
        exam_bank=data.get("exam_bank", ""),
        source_type=data.get("source_type", ""),
        input_data=data.get("input_data") or {},
        ac_ref=data.get("ac_ref"),
        tags=list(data.get("tags") or []),
    )


def generation_payload_to_candidate(
    payload: GenerationPayload, metadata: CandidateMetadata,
) -> GoldenExample | None:
    """None (not a partially-guessed candidate) when history[] is empty or history[0] doesn't parse
    as a well-formed GeneratedQuestion - same "wrong/broken shape returns None" convention as
    history_entry_as_generated_question itself, which this directly reuses rather than duplicating.
    """

    if not payload.history:
        return None
    question = history_entry_as_generated_question(payload.history[0])
    if question is None:
        return None

    return GoldenExample(
        example_id=metadata.example_id,
        source_type=metadata.source_type,
        exam_bank=metadata.exam_bank,
        question_type=question.question_type,
        input=metadata.input_data,
        expected=asdict(question),
        tags=list(metadata.tags),
        ac_ref=metadata.ac_ref,
    )


def load_raw_candidate_record(data: dict) -> tuple[GenerationPayload, CandidateMetadata]:
    """data is one {"payload": <GenerationPayload dict>, "metadata": <CandidateMetadata dict>}
    record - the envelope produced by mock_fetch_raw_candidates() and expected in --in files."""

    return (
        load_generation_payload(data.get("payload") or {}),
        load_candidate_metadata(data.get("metadata") or {}),
    )


def ingest_candidate_batch(
    pairs: list[tuple[GenerationPayload, CandidateMetadata]],
) -> tuple[list[GoldenExample], list[str]]:
    """Returns (candidates, skipped_example_ids) - a record that doesn't convert cleanly is skipped
    and its example_id reported, never silently dropped, matching import_pool.py's "nothing
    vanishes" convention for anything that fails to make it through."""

    candidates: list[GoldenExample] = []
    skipped: list[str] = []
    for payload, metadata in pairs:
        candidate = generation_payload_to_candidate(payload, metadata)
        if candidate is None:
            skipped.append(metadata.example_id)
        else:
            candidates.append(candidate)
    return candidates, skipped
