"""Shared "Case N: ..." section extraction for teaching_case_standard.py and case_numbering.py -
both operate on the same numbered case sections within an explanation field, so the splitting
logic lives in one place rather than drifting between two copies (the same private-shared-module
precedent as maestro/judge/shared.py).

PLACEHOLDER HEURISTIC: a case section is detected by a paragraph whose text starts with "Case N"
(case-insensitive). The real Maestro markup for a case section is unconfirmed - this is a
best-effort structural guess, not a confirmed data contract. Revisit once real payloads exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import html as lxml_html

_CASE_LABEL_RE = re.compile(r"^\s*Case\s+(\d+)\b", re.IGNORECASE)


@dataclass
class CaseBlock:
    field_name: str
    number: int | None            # None if the label's number failed to parse as an integer
    label_text: str               # e.g. "Case 1"
    paragraphs: list = field(default_factory=list)   # lxml elements belonging to this case


def _iter_paragraphs(root):
    paragraphs = list(root.iter("p"))
    # Falls back to the root itself so a case written without <p> tags at all is still
    # inspectable, rather than silently producing zero case blocks.
    return paragraphs if paragraphs else [root]


def extract_case_blocks(field_name: str, html_fragment: str | None) -> list[CaseBlock]:
    if not html_fragment or not html_fragment.strip():
        return []
    try:
        root = lxml_html.fromstring(html_fragment)
    except Exception:
        return []  # malformed markup is html_well_formed's job, not ours

    blocks: list[CaseBlock] = []
    current: CaseBlock | None = None
    for paragraph in _iter_paragraphs(root):
        text = paragraph.text_content().strip()
        match = _CASE_LABEL_RE.match(text)
        if match:
            current = CaseBlock(
                field_name=field_name, number=int(match.group(1)),
                label_text=match.group(0).strip(), paragraphs=[paragraph],
            )
            blocks.append(current)
        elif current is not None:
            current.paragraphs.append(paragraph)
        # Text before any "Case N" label (e.g. a lead-in sentence) belongs to no case block.
    return blocks
