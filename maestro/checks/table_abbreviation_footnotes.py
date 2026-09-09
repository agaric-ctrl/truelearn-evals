"""Cross-checks every table's abbreviations against a final merged footnote row - the "table
abbreviation footnote" rule named in docs/qa-context/TIER1_CHECKS_TASK.md: every abbreviation used
anywhere in a table (headers, row headers, data cells) must appear in a final merged footnote row.

The last <tr> in each table is treated as its footnote row; every abbreviation found in any
earlier row must appear as a whole word somewhere in that row's text.

FALSE-POSITIVE FIXES (per the task doc - "fix known limitations, don't inherit them silently"),
each verified against real content (Biochemistry reference articles), not assumed. An
"abbreviation" is a 2-6 letter all-caps word, excluding:
1. Digit-adjacent fragments: a chemical-formula fragment ("CO2", "H2O") or a vitamin/label name
   ("B12", "B6") - the letter cluster sits directly next to a digit, which a genuine abbreviation
   like "COPD" or "CBC" never does.
2. Roman numerals used as a classifying suffix - "complex II" (electron transport chain), "factor
   IX" (clotting factor), "type IV" (hypersensitivity), "stage III" (cancer), etc. - see
   _is_guarded_roman_numeral() below for exactly what's excluded and why the guard exists.
EvalConfig.abbreviation_allowlist is a further, always-available safety valve for specific terms
(e.g. "DNA") that should never require a footnote definition regardless of either heuristic.

KNOWN, NOT-YET-FIXED remaining false-positive class, found while verifying fix #2 against real
content (Minerals_and_Trace_Elements.docx's real table): chemical oxidation-state notation like
"Cr(VI)" (hexavalent chromium) is also a genuine Roman numeral, structurally different from the
"complex/factor/type X" pattern this fix targets (a parenthetical suffix directly after an element
symbol, not a preceding classifying word) - out of scope for this fix, left flagged rather than
guessed at.
"""

from __future__ import annotations

import re

from lxml import html as lxml_html

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_ABBREVIATION_RE = re.compile(r"\b[A-Z]{2,6}\b")

# Standard subtractive-notation Roman numerals (1-3999) - a real regex, not a hardcoded list of
# "II"/"IV" strings, since board content reasonably uses others ("Type I" reactions, cranial
# nerves up to XII, etc.). fullmatch-only (anchored ^...$): the token must be ENTIRELY valid
# Roman-numeral characters in valid order, not just contain some.
_ROMAN_NUMERAL_RE = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")

# CONTEXT-GUARD CHOSEN over excluding bare Roman numerals outright, per a real collision found
# while verifying this fix: the general Roman-numeral pattern above also matches real, ordinary
# abbreviations that happen to be spelled from Roman-numeral letters - "MI" (myocardial
# infarction, an extremely common real abbreviation) parses as M=1000 + I=1 = 1001, a
# syntactically valid (if unusual) numeral. A bare-exclusion approach would wrongly suppress "MI"
# (and similarly "CD", "CM", "LI", ...) everywhere, not just where it's actually being used as a
# numeral. Requiring one of these classifying words immediately before the token is what
# distinguishes "the two real board-content contexts this shows up in" (complex/factor, per the
# task) - extended to type/class/stage/grade/phase, the same "word labels a numbered category"
# pattern in board-exam content (hypersensitivity types, drug classes, cancer/injury staging and
# grading, trial phases) - from an incidental collision.
_ROMAN_NUMERAL_CONTEXT_WORDS = {"complex", "factor", "type", "class", "stage", "grade", "phase"}
_PRECEDING_WORD_RE = re.compile(r"([A-Za-z]+)\s*$")


def _is_guarded_roman_numeral(text: str, start: int, term: str) -> bool:
    """True only when `term` is Roman-numeral-shaped AND immediately preceded by a classifying
    word (see module docstring for the full "MI" collision reasoning behind requiring this).
    Otherwise - no preceding classifying word, or not Roman-numeral-shaped at all - this returns
    False and the caller falls back to flagging the token, per the task's explicit instruction:
    "a bare 'IV' with no preceding context is genuinely ambiguous" (and, confirmed against real
    content, sometimes is a genuine abbreviation - "give IV thiamine" means intravenous, not the
    numeral 4)."""

    if not _ROMAN_NUMERAL_RE.match(term):
        return False
    preceding_match = _PRECEDING_WORD_RE.search(text[:start])
    if not preceding_match:
        return False
    return preceding_match.group(1).lower() in _ROMAN_NUMERAL_CONTEXT_WORDS


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
        if _is_guarded_roman_numeral(text, start, term):
            continue  # e.g. "complex II", "factor IX" - a Roman numeral, not an abbreviation
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
