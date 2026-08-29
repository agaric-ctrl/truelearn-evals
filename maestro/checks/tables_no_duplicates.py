"""Flags a <table> that appears more than once across the item's HTML fields - the "duplicated
tables" failure mode SMEs flagged in early question generation. Compared by normalized inner
content rather than exact markup, since two tables with identical cell text but different
whitespace/attribute ordering are the same duplication bug, not two different tables.

Uses lxml's lenient HTML parser (a different, more forgiving instance than
html_well_formed.py's strict one) - a malformed fragment is html_well_formed's problem to report,
not this check's; this check should best-effort extract whatever tables it can find.
"""

from __future__ import annotations

import re

from lxml import html as lxml_html

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_CELL_SEPARATOR = "|"
_ROW_SEPARATOR = "\n"
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_cell(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip()).lower()


def _table_signature(table_element) -> str:
    """Joins cells with an explicit separator per row, rows with newline - NOT raw concatenated
    inner-text. This is what keeps "Na140" (one cell) distinguishable from "Na"+"140" (two cells)
    after whitespace normalization, while still treating pretty-printed vs. minified copies of the
    same table (whitespace-only differences between tags) as identical."""

    rows = []
    for row in table_element.iter("tr"):
        cells = [child for child in row if child.tag in ("td", "th")]
        rows.append(_CELL_SEPARATOR.join(_normalize_cell(cell.text_content()) for cell in cells))
    return _ROW_SEPARATOR.join(rows)


def _tables_in_field(fragment: str | None) -> list[str]:
    if not fragment or not fragment.strip():
        return []

    try:
        root = lxml_html.fromstring(fragment)
    except Exception:
        return []  # malformed markup is html_well_formed's job, not ours

    return [_table_signature(table) for table in root.iter("table")]


def tables_no_duplicates(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    locations: dict[str, list[str]] = {}
    total_tables = 0

    for field_name in _HTML_FIELDS:
        signatures = _tables_in_field(getattr(question, field_name, None))
        total_tables += len(signatures)
        for signature in signatures:
            locations.setdefault(signature, []).append(field_name)

    if total_tables == 0:
        return [CheckResult(
            check_name="tables_no_duplicates", status=Status.SKIPPED,
            message="No tables found in any field.",
        )]

    duplicate_groups = [fields for fields in locations.values() if len(fields) > 1]
    if not duplicate_groups:
        return [CheckResult(
            check_name="tables_no_duplicates", status=Status.PASS,
            message=f"{total_tables} table(s) found, none duplicated.",
        )]

    return [
        CheckResult(
            check_name="tables_no_duplicates", status=Status.FAIL,
            message=f"The same table appears {len(fields)} times, in: {', '.join(fields)}.",
            details={"fields": fields},
        )
        for fields in duplicate_groups
    ]
