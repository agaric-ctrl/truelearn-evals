"""Adopts a real markdown-linting tool (pymarkdownlnt - a Python port of the same rule-set idea as
the Node markdownlint tool named in docs/qa-context/TIER1_CHECKS_TASK.md) to catch payload
formatting-hygiene problems in a field: hard tabs, excess consecutive blank lines, trailing
whitespace, malformed/unlabeled code fences.

VERIFIED, HONEST SCOPE - two real findings from directly testing this tool against Maestro's
actual field shape (HTML), not assumed:

1. pymarkdownlnt is a CommonMark parser at heart. Content that starts with (or contains, with no
   blank line before it) a raw HTML tag gets absorbed into a single opaque "HTML block" per the
   CommonMark spec - none of the markdown-structural rules (headings, lists, ...) evaluate the
   lines inside it at all, regardless of which rules are enabled/disabled. Since every Maestro
   field is HTML-wrapped by contract, running the linter against the raw field would make MD033
   ("no inline HTML") fire on every single field - not a real defect, just the confirmed data
   contract - while simultaneously suppressing every other rule's ability to see anything past
   that first tag. Stripping tags first (reusing html_text.strip_tags_and_decode(), the same
   helper readability.py and density_redundancy.py already use) avoids this dead end entirely.
2. Even so, this does NOT reliably catch a "leaked" markdown token sitting inline in otherwise
   clean prose (e.g. literal "**not**" or a lone "#" mid-sentence) - verified directly: valid
   markdown emphasis syntax parses successfully (that's not a lint violation, it's correct
   markdown), and a "#" not at the start of its own line was never a heading attempt to begin
   with. That failure mode isn't this check's job; arrow_style.py is the model for a check that
   goes after one specific literal token pattern directly, if a similar rule is ever wanted here.

MD041 (first line must be a top-level heading) and MD047 (file must end with one newline) are
always disabled - both are whole-file assumptions that don't apply to one field's content. MD013
(line length) is also disabled - not meaningful for a field that may be one long flowing sentence.
"""

from __future__ import annotations

from pymarkdown.api import PyMarkdownApi

from maestro.check_result import CheckResult, Status
from maestro.html_text import strip_tags_and_decode
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_DISABLED_RULES = ("md041", "md047", "md013")


def _scan_field(field_name: str, fragment: str | None) -> list[CheckResult]:
    text = strip_tags_and_decode(fragment or "")
    if not text.strip():
        return [CheckResult(
            check_name="markdown_structural_compatibility", field_name=field_name,
            status=Status.SKIPPED, message="Field is empty - nothing to scan.",
        )]

    api = PyMarkdownApi()
    for rule_id in _DISABLED_RULES:
        api = api.disable_rule_by_identifier(rule_id)
    result = api.scan_string(text)

    if not result.scan_failures:
        return [CheckResult(
            check_name="markdown_structural_compatibility", field_name=field_name,
            status=Status.PASS, message="No stray markdown syntax detected.",
        )]

    return [
        CheckResult(
            check_name="markdown_structural_compatibility", field_name=field_name,
            sub_check=failure.rule_id, status=Status.FAIL,
            message=f"{failure.rule_description} (line {failure.line_number}).",
        )
        for failure in result.scan_failures
    ]


def markdown_structural_compatibility(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    for field_name in _HTML_FIELDS:
        results.extend(_scan_field(field_name, getattr(question, field_name, None)))
    return results
