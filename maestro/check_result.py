"""Tri-state (Pass/Fail/Skipped) result schema for Maestro question checks.

Skipped means: the rule exists, but the fact needed to enforce it is not yet confirmed in
EvalConfig, so this check deliberately declines to guess.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Status(str, Enum):
    """FAIL < SKIPPED < PASS is the render_summary() sort order, not enum declaration order -
    a report sorted in natural Pass/Fail/Skipped order buried failures at the bottom of a long
    summary, which is exactly what a human skimming the report needs to see first."""

    FAIL = "fail"
    SKIPPED = "skipped"
    PASS = "pass"


_STATUS_SORT_ORDER = {Status.FAIL: 0, Status.SKIPPED: 1, Status.PASS: 2}
_STATUS_LABEL = {Status.FAIL: "FAIL", Status.SKIPPED: "SKIPPED", Status.PASS: "PASS"}


@dataclass
class CheckResult:
    check_name: str
    status: Status
    message: str
    field_name: str | None = None   # GeneratedQuestion field this concerns, if applicable
    sub_check: str | None = None    # finer-grained constraint name within a multi-part check
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class QuestionCheckReport:
    unique_name: str | None
    results: list[CheckResult]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def has_failures(self) -> bool:
        return any(result.status is Status.FAIL for result in self.results)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def render_summary(report: QuestionCheckReport) -> str:
    """A pass/fail/skip tally plus one line per finding, ordered Fail -> Skipped -> Pass so the
    things that need attention are readable without opening the JSON. to_json() deliberately does
    NOT apply this sort - it keeps natural per-check registration order, which is stable and
    diff-friendly for a machine consumer. Only this human-facing rendering re-sorts."""

    ordered = sorted(report.results, key=lambda result: _STATUS_SORT_ORDER[result.status])
    counts = {status: 0 for status in Status}
    for result in ordered:
        counts[result.status] += 1

    lines = [
        f"Maestro check report for {report.unique_name or '(unnamed)'}",
        f"{counts[Status.FAIL]} failed, {counts[Status.SKIPPED]} skipped, "
        f"{counts[Status.PASS]} passed ({len(ordered)} total).",
        "",
    ]
    for result in ordered:
        location = f" [{result.field_name}]" if result.field_name else ""
        sub = f" ({result.sub_check})" if result.sub_check else ""
        lines.append(
            f"[{_STATUS_LABEL[result.status]}] {result.check_name}{sub}{location} "
            f"— {result.message}"
        )
    return "\n".join(lines)
