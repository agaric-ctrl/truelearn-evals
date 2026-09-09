"""Cross-checks every table's abbreviations against a final merged footnote row - the "table
abbreviation footnote" rule named in docs/qa-context/TIER1_CHECKS_TASK.md: every abbreviation used
anywhere in a table (headers, row headers, data cells) must appear in a final merged footnote row.

The last <tr> in each table is treated as its footnote row; every abbreviation found in any
earlier row must appear as a whole word somewhere in that row's text.

FALSE-POSITIVE FIX (per the task doc - "fix known limitations, don't inherit them silently"): an
"abbreviation" is a 2-6 letter all-caps word that is NOT immediately touching a digit. That
digit-adjacency exclusion is what keeps a chemical-formula fragment ("CO2", "H2O") or a
vitamin/label name ("B12", "B6") from being misread as an undefined abbreviation - the letter
cluster in those sits directly next to a digit, which a genuine abbreviation like "COPD" or "CBC"
never does. EvalConfig.abbreviation_allowlist is a further, always-available safety valve for
specific terms (e.g. "DNA", "IV") that should never require a footnote definition regardless of
this heuristic.
"""

from __future__ import annotations

import re

from lxml import html as lxml_html

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_ABBREVIATION_RE = re.compile(r"\b[A-Z]{2,6}\b")


def _find_abbreviations(text: str, allowlist: set[str]) -> set[str]:
    found = set()
    for match in _ABBREVIATION_RE.finditer(text):
        term = match.group(0)
        if term in allowlist:
            continue
        start, end = match.span()
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        if before.isdigit() or after.isdigit():
            continue  # e.g. "CO2", "B12" - a formula/label fragment, not an abbreviation
        found.add(term)
    return found


def _check_table(field_name: str, table_index: int, table_element, allowlist: set[str]) -> CheckResult:
    rows = list(table_element.iter("tr"))
    if not rows:
        return CheckResult(
            check_name="table_abbreviation_footnotes", field_name=field_name,
            sub_check=f"table[{table_index}]", status=Status.SKIPPED,
            message="Table has no rows.",
        )

    body_rows, footnote_row = rows[:-1], rows[-1]
    body_abbreviations: set[str] = set()
    for row in body_rows:
        body_abbreviations |= _find_abbreviations(row.text_content(), allowlist)

    if not body_abbreviations:
        return CheckResult(
            check_name="table_abbreviation_footnotes", field_name=field_name,
            sub_check=f"table[{table_index}]", status=Status.PASS,
            message="No abbreviations found in this table.",
        )

    footnote_text = footnote_row.text_content()
    missing = sorted(
        abbr for abbr in body_abbreviations
        if not re.search(rf"\b{re.escape(abbr)}\b", footnote_text)
    )
    if missing:
        return CheckResult(
            check_name="table_abbreviation_footnotes", field_name=field_name,
            sub_check=f"table[{table_index}]", status=Status.FAIL,
            message=f"Abbreviation(s) not defined in the footnote row: {', '.join(missing)}.",
            details={"missing": missing},
        )
    return CheckResult(
        check_name="table_abbreviation_footnotes", field_name=field_name,
        sub_check=f"table[{table_index}]", status=Status.PASS,
        message=f"All {len(body_abbreviations)} abbreviation(s) defined in the footnote row.",
    )


def table_abbreviation_footnotes(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    table_count = 0
    for field_name in _HTML_FIELDS:
        fragment = getattr(question, field_name, None)
        if not fragment or not fragment.strip():
            continue
        try:
            root = lxml_html.fromstring(fragment)
        except Exception:
            continue  # malformed markup is html_well_formed's job, not ours

        for table_element in root.iter("table"):
            results.append(
                _check_table(field_name, table_count, table_element, config.abbreviation_allowlist)
            )
            table_count += 1

    if table_count == 0:
        return [CheckResult(
            check_name="table_abbreviation_footnotes", status=Status.SKIPPED,
            message="No tables found in any field.",
        )]
    return results
