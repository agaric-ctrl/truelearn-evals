"""Golden-set record schema. A golden example is an SME-approved reference (question, edit, or
article) that other things can eventually be scored against. Stored as JSONL (one object per line,
diff-friendly), one file per exam bank.

review_status mirrors this repo's own evaluations/faithfulness/data/gold_cases.json pattern: a real, known starting state
("pending_sme_review"), not an unconfirmed fact - so it defaults to a literal, not to None the way
EvalConfig's fields do.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from maestro.models import GeneratedQuestion, load_generated_question

QUESTION_SOURCE_TYPES = ("topic", "question_edit")


@dataclass
class SmeVerification:
    verified: bool = False
    reviewer_id: str | None = None
    verified_at: str | None = None


@dataclass
class GoldenExample:
    example_id: str = ""
    source_type: str = ""                                       # "topic" | "question_edit" | "article"
    exam_bank: str = ""                                         # "USMLE" | "COMLEX" | "COMAT"
    question_type: str = ""
    input: dict[str, object] = field(default_factory=dict)      # free-form for every source_type
    expected: dict[str, object] = field(default_factory=dict)   # GeneratedQuestion-shaped iff topic/question_edit
    tags: list[str] = field(default_factory=list)
    ac_ref: str | None = None
    sme_verified: SmeVerification = field(default_factory=SmeVerification)
    review_status: str = "pending_sme_review"                   # | "approved" | "rejected"
    second_reviewer_id: str | None = None
    second_reviewed_at: str | None = None


def load_golden_example(data: dict) -> GoldenExample:
    """Manual field construction, same reasoning as maestro.models.load_eval_config: a naive
    GoldenExample(**data) would leave sme_verified as a raw dict, not an SmeVerification."""

    sme = data.get("sme_verified") or {}
    return GoldenExample(
        example_id=data.get("example_id", ""),
        source_type=data.get("source_type", ""),
        exam_bank=data.get("exam_bank", ""),
        question_type=data.get("question_type", ""),
        input=data.get("input") or {},
        expected=data.get("expected") or {},
        tags=list(data.get("tags") or []),
        ac_ref=data.get("ac_ref"),
        sme_verified=SmeVerification(
            verified=bool(sme.get("verified", False)),
            reviewer_id=sme.get("reviewer_id"),
            verified_at=sme.get("verified_at"),
        ),
        review_status=data.get("review_status", "pending_sme_review"),
        second_reviewer_id=data.get("second_reviewer_id"),
        second_reviewed_at=data.get("second_reviewed_at"),
    )


def dump_golden_example(example: GoldenExample) -> dict:
    return asdict(example)  # safe: dataclass -> dict has no ambiguity, only load needs care


def expected_as_generated_question(example: GoldenExample) -> GeneratedQuestion:
    return load_generated_question(example.expected)


def read_jsonl(path: Path) -> list[GoldenExample]:
    if not path.exists():
        return []
    return [
        load_golden_example(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, examples: list[GoldenExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dump_golden_example(example)) + "\n" for example in examples),
        encoding="utf-8",
    )


def append_jsonl(path: Path, examples: list[GoldenExample]) -> None:
    """Full read+rewrite keeps one clear code path; volumes here are small (dozens-hundreds of rows
    per bank), not a real perf concern."""

    write_jsonl(path, read_jsonl(path) + examples)
