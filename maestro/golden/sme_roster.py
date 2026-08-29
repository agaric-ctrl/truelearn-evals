"""Who reviews which exam bank - the human-input surface for Tier 2, kept separate from
EvalConfig since it's a process fact (who reviews bank X) with no relationship to validating a
single GeneratedQuestion. Every field defaults to unconfirmed, same philosophy as EvalConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SmeAssignment:
    reviewer_id: str | None = None
    backup_reviewer_id: str | None = None


@dataclass
class SmeRoster:
    assignments_by_bank: dict[str, SmeAssignment] = field(default_factory=dict)

    def for_bank(self, exam_bank: str) -> SmeAssignment:
        return self.assignments_by_bank.get(exam_bank, SmeAssignment())


def load_sme_roster(data: dict) -> SmeRoster:
    return SmeRoster(assignments_by_bank={
        bank: SmeAssignment(
            reviewer_id=value.get("reviewer_id"),
            backup_reviewer_id=value.get("backup_reviewer_id"),
        )
        for bank, value in (data or {}).items()
    })
