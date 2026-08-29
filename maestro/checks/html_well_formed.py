"""Parses each HTML-bearing field and fails on structural markup errors - mismatched/crossing tags
(e.g. "<b><i></b></i>") and stray closing tags with no matching open. This catches the
"broken/invalid table HTML" failure mode SMEs flagged in early question generation, without
knowing anything about tables specifically.

Uses lxml.etree.HTMLParser(recover=False) rather than stdlib html.parser.HTMLParser: stdlib lost
its "strict" mode in Python 3.5+ and can no longer raise on malformed markup at all, and
BeautifulSoup has no raise-on-error mode either - both are always-lenient.

Verified empirically, not assumed, and this shapes what "syntax error" means here: libxml2's HTML
parser (which lxml.etree.HTMLParser wraps) applies real HTML5 tag-inference rules, so a tag left
unclosed at end-of-input is auto-closed exactly like a browser would - NOT a syntax error, by
design. Only genuine structural errors (crossing/mismatched tags, unexpected end tags) raise
etree.XMLSyntaxError. Deliberately NOT using strict XML-mode parsing instead: that WOULD flag a
plain unclosed tag, but it also fatally flags completely ordinary, valid HTML like "<br>" or
"<img src=...>" without a self-closing slash - exactly the markup any non-XHTML generator produces
routinely - which would make the check fail on huge amounts of legitimate content. HTML-mode's
narrower, real-defect-focused definition is the more useful check in practice.
"""

from __future__ import annotations

from lxml import etree

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion

_HTML_FIELDS = ("question_text", "explanation_header", "explanation_footer", "bottom_line")
_STRICT_PARSER = etree.HTMLParser(recover=False)


def _check_field(field_name: str, fragment: str | None) -> CheckResult:
    if not fragment or not fragment.strip():
        return CheckResult(
            check_name="html_well_formed", field_name=field_name,
            status=Status.SKIPPED, message="Field is empty - nothing to parse.",
        )

    try:
        etree.fromstring(fragment, parser=_STRICT_PARSER)
    except etree.XMLSyntaxError as error:
        return CheckResult(
            check_name="html_well_formed", field_name=field_name,
            status=Status.FAIL, message=f"Markup syntax error: {error}",
        )

    return CheckResult(
        check_name="html_well_formed", field_name=field_name,
        status=Status.PASS, message="Parses with no syntax errors.",
    )


def html_well_formed(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    return [_check_field(name, getattr(question, name, None)) for name in _HTML_FIELDS]
