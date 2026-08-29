"""CLI: turns a batch of not-yet-verified GoldenExample candidates into an SME review-pool
spreadsheet, plus a mapping file that lets import_pool.py re-associate graded rows back to real
records later.

Blind ordering: example_id, ac_ref, and unique_name are never rendered as spreadsheet columns at
all (blinding by omission), and row order is shuffled with a seed - the SME can't infer identity or
source from row position or from any visible column.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import openpyxl
from openpyxl.styles import Protection
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from maestro.golden.models import GoldenExample, QUESTION_SOURCE_TYPES, dump_golden_example, read_jsonl
from maestro.golden.sme_roster import load_sme_roster
from maestro.html_text import strip_tags_and_decode

HEADERS = [
    "display_id", "source_type", "question_type", "input_preview", "expected_preview",
    "tags", "grade", "reviewer_id", "notes",
]
UNLOCKED_COLUMNS = {"grade", "reviewer_id", "notes"}
GRADE_CHOICES = ("approve", "reject", "needs_revision")


def shuffled_order(n: int, seed: int) -> list[int]:
    """A dedicated Random instance, not the global random module, so this is reproducible for a
    given seed independent of any other in-process randomness."""

    order = list(range(n))
    random.Random(seed).shuffle(order)
    return order


def _preview(payload: dict, source_type: str) -> str:
    """Question-shaped content is rendered through Tier 1's own HTML-to-text helper (direct,
    deliberate cross-tier reuse); anything else (article, or a candidate whose expected/input isn't
    question-shaped) is genuinely unmodeled, so it falls back to a generic JSON dump rather than
    guessing a rendering."""

    if source_type in QUESTION_SOURCE_TYPES and payload:
        parts = []
        for field_name in ("question_text", "explanation_header", "explanation_footer", "bottom_line"):
            value = payload.get(field_name)
            if value:
                parts.append(f"[{field_name}] {strip_tags_and_decode(value)}")
        if parts:
            return "\n\n".join(parts)
    return json.dumps(payload, indent=2, sort_keys=True)


def build_review_pool(candidates: list[GoldenExample], seed: int):
    """Returns (Workbook, mapping dict) without touching disk, so this is independently
    unit-testable with no file I/O - same run_checks()/main() split runner.py already uses."""

    order = shuffled_order(len(candidates), seed)
    width = max(3, len(str(len(candidates))))

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Review Pool"
    sheet.append(HEADERS)

    mapping_rows: dict[str, dict] = {}

    for row_index, candidate_index in enumerate(order, start=1):
        candidate = candidates[candidate_index]
        display_id = f"R{row_index:0{width}d}"

        sheet.append([
            display_id,
            candidate.source_type,
            candidate.question_type,
            _preview(candidate.input, candidate.source_type),
            _preview(candidate.expected, candidate.source_type),
            ", ".join(candidate.tags),
            "",  # grade
            "",  # reviewer_id
            "",  # notes
        ])

        mapping_rows[display_id] = {
            "example_id": candidate.example_id,
            "golden_example": dump_golden_example(candidate),
        }

    sheet.protection.sheet = True
    for row in range(2, sheet.max_row + 1):
        for column_name in UNLOCKED_COLUMNS:
            column_index = HEADERS.index(column_name) + 1
            sheet.cell(row=row, column=column_index).protection = Protection(locked=False)

    sheet.freeze_panes = "A2"

    grade_column_letter = get_column_letter(HEADERS.index("grade") + 1)
    data_validation = DataValidation(
        type="list", formula1=f'"{",".join(GRADE_CHOICES)}"', allow_blank=True,
    )
    sheet.add_data_validation(data_validation)
    data_validation.add(f"{grade_column_letter}2:{grade_column_letter}{sheet.max_row}")

    mapping = {
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": mapping_rows,
    }
    return workbook, mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an SME review-pool spreadsheet from a batch of golden-set candidates.")
    parser.add_argument("--batch", type=Path, required=True, help="Path to a JSONL file of GoldenExample-shaped candidates.")
    parser.add_argument("--seed", type=int, required=True, help="Shuffle seed - required so row order is always auditable.")
    parser.add_argument("--out-xlsx", type=Path, required=True)
    parser.add_argument("--out-mapping", type=Path, required=True)
    parser.add_argument("--sme-roster", type=Path, default=None, help="Optional; only used to print a non-blocking note about unassigned banks.")
    args = parser.parse_args()

    candidates = read_jsonl(args.batch)
    if not candidates:
        print(f"No candidates found in {args.batch}.")
        return 1

    if args.sme_roster:
        roster = load_sme_roster(json.loads(args.sme_roster.read_text(encoding="utf-8")))
        for bank in sorted({candidate.exam_bank for candidate in candidates}):
            if roster.for_bank(bank).reviewer_id is None:
                print(f"Note: no reviewer_id assigned for exam_bank {bank!r} in {args.sme_roster}.")

    workbook, mapping = build_review_pool(candidates, args.seed)

    args.out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(args.out_xlsx)
    args.out_mapping.parent.mkdir(parents=True, exist_ok=True)
    args.out_mapping.write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    print(f"Wrote {len(candidates)} row(s) to {args.out_xlsx} (mapping: {args.out_mapping}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
