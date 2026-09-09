"""Converts a real Editorial reference-article .docx into the shapes the rest of this task needs:
an HTML body (for feeding into Tier 1's HTML-field checks) and a separately-extracted references
list, both derived from the document's real structure (paragraph styles, bold runs, tables) - not
guessed at. Built against the actual structure of the three Biochemistry reference articles
(Fat-Soluble Vitamins, Water-Soluble Vitamins, Minerals_and_Trace_Elements): a title paragraph,
Heading-1/2/3 sections, "List Paragraph" bullets (often with a bolded lead term), data tables, a
"Teaching Cases" section with "Case N: <title>" Heading-3 subsections whose body paragraph ends in
a bolded inline "Key teaching:" sentence, and a final "References" section of plain paragraphs.

DESIGN DECISION, stated explicitly rather than silently baked in: heading paragraphs (Heading 1/2/3)
are converted to <p> tags, same as any other paragraph - not <h2>/<h3>/etc. Tier 1's existing checks
(built for GeneratedQuestion's flat HTML fields, no heading concept) only look for <p> elements
whose own text starts with "Case N" (see checks/_case_blocks.py) - flattening headings to <p> is
what makes "Case 1: ..." detectable by that existing logic without modifying it. This does lose
heading/body visual distinction if the HTML were ever rendered, which doesn't matter here since
nothing renders it - only the deterministic checks read it.

BUG FOUND AND FIXED against real content, not caught by initial testing: python-docx's
row.cells repeats the same underlying cell (same _tc XML element) once per spanned grid column
for a horizontally-merged cell - confirmed directly against Water-Soluble Vitamins.docx's real
footnote rows, where a single merged cell spanning all 5 columns showed up as 5 identical `cells`
entries. A naive iteration duplicated that text 5x in both the table's HTML and its row-data, which
made table_abbreviation_footnotes.py compare against a garbled repeated string instead of the real
merged footnote content - see _dedup_merged_cells() below.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

_REFERENCES_HEADING = "references"


@dataclass
class ConvertedArticle:
    title: str
    body_html: str
    references: list[str] = field(default_factory=list)
    # Structural data preserved for atomic-fixture decomposition (Teaching Cases / tables /
    # references), separate from body_html which is what Tier 1 checks actually scan.
    teaching_cases: list[dict] = field(default_factory=list)  # [{"label": "Case 1: ...", "body": "..."}]
    tables: list[list[list[str]]] = field(default_factory=list)  # list of tables, each rows x cells


def _run_html(run) -> str:
    text = html.escape(run.text)
    return f"<strong>{text}</strong>" if run.bold else text


def _paragraph_html(paragraph: Paragraph) -> str:
    inner = "".join(_run_html(run) for run in paragraph.runs)
    if not inner.strip():
        inner = html.escape(paragraph.text)
    return f"<p>{inner}</p>"


def _dedup_merged_cells(row) -> list:
    """python-docx's row.cells repeats the same underlying cell (same _tc XML element) once per
    spanned grid column for a horizontally-merged cell - verified directly against the real
    Water-Soluble Vitamins footnote rows: a single merged cell spanning 5 grid columns showed up
    as 5 identical `cells` entries (same id(cell._tc)), which is what made the abbreviation-
    footnote check misread every merged footnote row as N copies of one cell rather than one
    logical cell. Collapses consecutive duplicates by underlying-element identity so a merged cell
    contributes exactly one logical cell, matching what a human reading the table actually sees."""

    result = []
    previous_tc = None
    for cell in row.cells:
        if cell._tc is previous_tc:
            continue
        result.append(cell)
        previous_tc = cell._tc
    return result


def _table_html(table: Table) -> str:
    rows_html = []
    for row in table.rows:
        cells_html = "".join(
            f"<td>{html.escape(cell.text.strip())}</td>" for cell in _dedup_merged_cells(row)
        )
        rows_html.append(f"<tr>{cells_html}</tr>")
    return "<table>" + "".join(rows_html) + "</table>"


def _table_rows(table: Table) -> list[list[str]]:
    return [[cell.text.strip() for cell in _dedup_merged_cells(row)] for row in table.rows]


def convert_docx(path) -> ConvertedArticle:
    document = docx.Document(str(path))

    title = ""
    body_parts: list[str] = []
    references: list[str] = []
    teaching_cases: list[dict] = []
    tables: list[list[list[str]]] = []
    in_references_section = False
    pending_case_label: str | None = None

    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            style = item.style.name if item.style else None

            if style == "Heading 1" and text.lower() == _REFERENCES_HEADING:
                in_references_section = True
                continue  # the heading itself is not a reference entry

            if in_references_section:
                references.append(text)
                continue

            if not title:
                title = text
                continue  # first real paragraph is the article's own title, not body content

            if pending_case_label is not None:
                teaching_cases.append({"label": pending_case_label, "body": text})
                pending_case_label = None
            elif style == "Heading 3" and text.lower().startswith("case "):
                pending_case_label = text

            body_parts.append(_paragraph_html(item))

        elif isinstance(item, Table):
            if in_references_section:
                continue  # no tables expected in the references section; be safe anyway
            tables.append(_table_rows(item))
            body_parts.append(_table_html(item))

    return ConvertedArticle(
        title=title, body_html="".join(body_parts), references=references,
        teaching_cases=teaching_cases, tables=tables,
    )
