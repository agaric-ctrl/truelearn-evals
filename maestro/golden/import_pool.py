"""CLI: reads a graded review-pool spreadsheet plus its mapping file and promotes approved,
Tier-1-clean rows into maestro/golden_data/<bank>.jsonl. Every non-promoted row (rejected,
needs_revision, ungraded, or SME-approved-but-Tier-1-blocked) is written to
<bank>.blocked.jsonl with a reason - nothing is silently discarded.

Trust boundary: only display_id, grade, reviewer_id, and notes are read from the graded sheet (the
things the SME actually produced). Golden content is always re-fetched from the mapping file by
display_id, never reconstructed from the sheet's read-only preview columns.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import openpyxl

from maestro.golden.models import (
    GoldenExample,
    QUESTION_SOURCE_TYPES,
    SmeVerification,
    dump_golden_example,
    expected_as_generated_question,
    load_golden_example,
    read_jsonl,
    write_jsonl,
)
from maestro.models import EvalConfig
from maestro.runner import run_checks


@dataclass
class ImportOutcome:
    example_id: str
    display_id: str
    grade: str | None
    promoted: bool
    reason: str | None = None  # "sme_rejected" | "sme_needs_revision" | "tier1_check_failed" | "collision" | "ungraded"
    exam_bank: str = ""  # added for import_summary.py's per-bank grouping - was computed locally
    # in the loop below but never attached to the outcome object before now


def read_graded_rows(xlsx_path: Path) -> dict[str, dict[str, str | None]]:
    """Reads by header name, not fixed column letters, so an SME accidentally reordering a column
    doesn't silently misread it. Returns display_id -> {grade, reviewer_id, notes}."""

    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    column_index = {name: index for index, name in enumerate(headers)}

    rows: dict[str, dict[str, str | None]] = {}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        display_id = row[column_index["display_id"]]
        if not display_id:
            continue
        rows[display_id] = {
            "grade": row[column_index["grade"]] or None,
            "reviewer_id": row[column_index["reviewer_id"]] or None,
            "notes": row[column_index["notes"]] or None,
        }
    return rows


def tier1_gate(example: GoldenExample):
    """A Tier 1 FAIL hard-blocks promotion for question-shaped source_types - a golden example's
    whole purpose is to be a trusted reference other things get scored against, so a structurally
    broken 'expected' must not enter as SME-approved. Uses a bare EvalConfig() (all-unconfirmed
    default): the importer has no legitimate source for a richer config, and guessing one risks
    spurious blocks on checks never meant to run here. article skips this - nothing to run it against."""

    if example.source_type not in QUESTION_SOURCE_TYPES:
        return None
    return run_checks(expected_as_generated_question(example), EvalConfig())


def import_pool(
    mapping: dict,
    graded_rows: dict[str, dict[str, str | None]],
    *,
    golden_dir: Path,
    blocked_dir: Path,
    run_tier1_gate: bool = True,
    allow_overwrite: bool = False,
) -> list[ImportOutcome]:
    outcomes: list[ImportOutcome] = []
    promotions_by_bank: dict[str, list[GoldenExample]] = {}
    blocked_by_bank: dict[str, list[dict]] = {}

    mismatched_display_ids = set(mapping["rows"]) ^ set(graded_rows)
    if mismatched_display_ids:
        print(f"Warning: display_id present on only one side (mapping vs. graded sheet): {sorted(mismatched_display_ids)}")

    for display_id, row in mapping["rows"].items():
        if display_id not in graded_rows:
            continue

        example = load_golden_example(row["golden_example"])
        graded = graded_rows[display_id]
        grade = graded["grade"]
        bank = example.exam_bank

        def _block(reason: str, report=None) -> None:
            blocked_by_bank.setdefault(bank, []).append({
                "example_id": example.example_id,
                "display_id": display_id,
                "blocked_reason": reason,
                "sme_reviewer_id": graded["reviewer_id"],
                "sme_notes": graded["notes"],
                "golden_example": dump_golden_example(example),
                **({"tier1_report": json.loads(report.to_json())} if report is not None else {}),
            })
            outcomes.append(ImportOutcome(example.example_id, display_id, grade, False, reason, exam_bank=bank))

        if grade is None:
            _block("ungraded")
            continue
        if grade == "reject":
            _block("sme_rejected")
            continue
        if grade == "needs_revision":
            _block("sme_needs_revision")
            continue

        report = tier1_gate(example) if run_tier1_gate else None
        if report is not None and report.has_failures:
            _block("tier1_check_failed", report)
            continue

        existing = read_jsonl(golden_dir / f"{bank.lower()}.jsonl")
        collision = next((existing_example for existing_example in existing if existing_example.example_id == example.example_id), None)
        if collision is not None and not allow_overwrite:
            print(
                f"Collision: {example.example_id!r} already exists in {bank.lower()}.jsonl "
                f"(existing reviewer={collision.sme_verified.reviewer_id!r}, "
                f"new reviewer={graded['reviewer_id']!r}) - skipped. Use --allow-overwrite to replace."
            )
            outcomes.append(ImportOutcome(example.example_id, display_id, grade, False, "collision", exam_bank=bank))
            continue
        if collision is not None and allow_overwrite:
            print(
                f"Overwriting {example.example_id!r} in {bank.lower()}.jsonl "
                f"(previous reviewer={collision.sme_verified.reviewer_id!r} at {collision.sme_verified.verified_at!r} "
                f"-> new reviewer={graded['reviewer_id']!r})."
            )

        example.review_status = "approved"
        example.sme_verified = SmeVerification(
            verified=True,
            reviewer_id=graded["reviewer_id"],
            verified_at=datetime.now(timezone.utc).isoformat(),
        )
        promotions_by_bank.setdefault(bank, []).append(example)
        outcomes.append(ImportOutcome(example.example_id, display_id, grade, True, exam_bank=bank))

    for bank, promoted in promotions_by_bank.items():
        path = golden_dir / f"{bank.lower()}.jsonl"
        existing = read_jsonl(path)
        by_id = {example.example_id: example for example in existing}
        for example in promoted:
            by_id[example.example_id] = example  # insert new, or overwrite in place (allow_overwrite path)
        write_jsonl(path, list(by_id.values()))

    for bank, blocked_rows in blocked_by_bank.items():
        blocked_path = blocked_dir / f"{bank.lower()}.blocked.jsonl"
        blocked_path.parent.mkdir(parents=True, exist_ok=True)
        with blocked_path.open("a", encoding="utf-8") as handle:
            for row in blocked_rows:
                handle.write(json.dumps(row) + "\n")

    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a graded SME review-pool spreadsheet into the golden set.")
    parser.add_argument("--graded-xlsx", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--golden-dir", type=Path, required=True)
    parser.add_argument("--blocked-dir", type=Path, default=None,
                         help="Where <bank>.blocked.jsonl files go. Defaults to the mapping file's own directory - the pool's working directory, where its other artifacts already live.")
    parser.add_argument("--no-run-checks", action="store_true", help="Skip the Tier 1 promotion gate.")
    parser.add_argument("--allow-overwrite", action="store_true", help="Replace an existing golden record with the same example_id instead of skipping it.")
    parser.add_argument("--outcomes-json", type=Path, default=None,
                         help="Optional: write this run's outcomes (one object per graded row - "
                         "example_id, display_id, grade, promoted, exam_bank, reason) as a JSON "
                         "list to this path. This is the per-run artifact golden/import_summary.py "
                         "reads from; omit if you don't need a summary of this run.")
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    graded_rows = read_graded_rows(args.graded_xlsx)

    outcomes = import_pool(
        mapping, graded_rows,
        golden_dir=args.golden_dir,
        blocked_dir=args.blocked_dir or args.mapping.parent,
        run_tier1_gate=not args.no_run_checks,
        allow_overwrite=args.allow_overwrite,
    )

    promoted = [outcome for outcome in outcomes if outcome.promoted]
    blocked = [outcome for outcome in outcomes if not outcome.promoted]
    print(f"Promoted {len(promoted)}, blocked {len(blocked)} (of {len(outcomes)} graded row(s)).")
    for outcome in blocked:
        print(f"  [{outcome.reason}] {outcome.example_id} (display_id={outcome.display_id})")

    if args.outcomes_json:
        args.outcomes_json.parent.mkdir(parents=True, exist_ok=True)
        args.outcomes_json.write_text(
            json.dumps([asdict(outcome) for outcome in outcomes], indent=2), encoding="utf-8",
        )
        print(f"Wrote {len(outcomes)} outcome(s) to {args.outcomes_json}.")

    return 1 if any(outcome.reason == "collision" for outcome in blocked) else 0


if __name__ == "__main__":
    raise SystemExit(main())
