"""CLI: summarizes one or more golden-set import runs (import_pool.py --outcomes-json output) into
a plain-language markdown report - promoted/blocked counts, blocked reasons, and a per-exam-bank
breakdown. Fills the gap docs/qa-context/REPORTING_SUMMARY_TASK.md names: import_pool.py already
computes an outcome (promoted/blocked/reason) for every graded row, but nothing previously read
that output after the print statements - it was computed and discarded.

Audience: SME/editorial leads, not engineering (already served by CI pass/fail) and not a
leadership trend view (which needs real historical data this doesn't have yet - see the findings
doc). Plain counts and reasons, no jargon, no dashboard.

Destination: a committed markdown file (maestro/golden_data/import_summary.md by default) - the
only "already exists" lightweight option in this repo. No chat integration or cloud storage is
wired up anywhere in maestro/ to push to instead (checked directly, not assumed); if one exists
elsewhere in the org, redirect this script's output there rather than building a new integration.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REASON_LABELS = {
    "ungraded": "Not yet graded",
    "sme_rejected": "Rejected by reviewer",
    "sme_needs_revision": "Needs revision",
    "tier1_check_failed": "Failed structural checks (Tier 1)",
    "collision": "Already exists (duplicate example_id)",
}


def _reason_label(reason: str | None) -> str:
    return _REASON_LABELS.get(reason, reason or "(no reason recorded)")


@dataclass
class BankSummary:
    exam_bank: str
    promoted: int = 0
    blocked: int = 0
    blocked_by_reason: Counter = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return self.promoted + self.blocked


def load_outcomes(paths: list[Path]) -> list[dict]:
    """Reads one or more import_pool.py --outcomes-json files and concatenates them - summarizing
    several runs together (e.g. a week's worth of review-pool imports) is just as valid as one."""

    outcomes: list[dict] = []
    for path in paths:
        outcomes.extend(json.loads(path.read_text(encoding="utf-8")))
    return outcomes


def summarize(outcomes: list[dict]) -> dict:
    """Groups by exam_bank (the one grouping dimension that already exists in ImportOutcome data -
    there is no content-area/subject tag on a GoldenExample or ImportOutcome today, so that
    dimension is correctly absent here rather than invented)."""

    by_bank: dict[str, BankSummary] = {}
    overall_reason_counts: Counter = Counter()
    promoted_total = 0

    for outcome in outcomes:
        bank = outcome.get("exam_bank") or "(unknown bank)"
        summary = by_bank.setdefault(bank, BankSummary(exam_bank=bank))
        if outcome["promoted"]:
            summary.promoted += 1
            promoted_total += 1
        else:
            summary.blocked += 1
            reason = outcome.get("reason")
            summary.blocked_by_reason[reason] += 1
            overall_reason_counts[reason] += 1

    return {
        "total": len(outcomes),
        "promoted": promoted_total,
        "blocked": len(outcomes) - promoted_total,
        "blocked_by_reason": overall_reason_counts,
        "by_bank": dict(sorted(by_bank.items())),
    }


def render_markdown(summary: dict, *, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    lines = [
        "# Golden-set import summary",
        "",
        f"_Generated {generated_at}._",
        "",
        "This summarizes what happened the last time graded review-pool rows were imported: how "
        "many were promoted to the golden set, how many were blocked, and why. It does not judge "
        "content quality itself - that's what the SME grading and Tier 1 checks already did before "
        "this summary ever runs.",
        "",
    ]

    if summary["total"] == 0:
        lines.append("No import runs found - nothing to summarize yet.")
        return "\n".join(lines) + "\n"

    lines += [
        "## Overall",
        "",
        f"- **{summary['total']}** row(s) graded across all runs summarized here.",
        f"- **{summary['promoted']}** promoted into the golden set.",
        f"- **{summary['blocked']}** blocked.",
        "",
    ]

    if summary["blocked_by_reason"]:
        lines.append("Blocked, by reason:")
        lines.append("")
        for reason, count in summary["blocked_by_reason"].most_common():
            lines.append(f"- {_reason_label(reason)}: **{count}**")
        lines.append("")

    lines += ["## By exam bank", ""]
    lines += ["| Exam bank | Promoted | Blocked | Blocked reasons |", "|---|---|---|---|"]
    for bank, bank_summary in summary["by_bank"].items():
        reasons = ", ".join(
            f"{_reason_label(reason)}: {count}"
            for reason, count in bank_summary.blocked_by_reason.most_common()
        ) or "—"
        lines.append(f"| {bank} | {bank_summary.promoted} | {bank_summary.blocked} | {reasons} |")
    lines.append("")

    lines += [
        "---",
        "",
        "_This is a throughput summary, not a quality signal - a low promotion rate might mean "
        "content needs work, or might mean rows are still awaiting review (\"Not yet graded\" isn't "
        "a rejection). See `docs/qa-context/MAESTRO_QA_FINDINGS.md` for what this harness does and "
        "doesn't measure yet._",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize golden-set import outcomes (import_pool.py --outcomes-json output) "
        "into a plain-language markdown report for SME/editorial-lead visibility.",
    )
    parser.add_argument(
        "--outcomes-json", type=Path, nargs="+", required=True,
        help="One or more paths written by import_pool.py --outcomes-json.",
    )
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parents[1] / "golden_data" / "import_summary.md",
        help="Output path for the markdown summary (default: maestro/golden_data/import_summary.md, "
        "the committed, human-relevant home for golden-set metadata this repo already uses for "
        "sme_roster.json).",
    )
    args = parser.parse_args()

    outcomes = load_outcomes(args.outcomes_json)
    summary = summarize(outcomes)
    report = render_markdown(summary)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote {args.out} ({summary['total']} outcome(s) summarized).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
