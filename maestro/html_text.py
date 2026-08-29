"""Lenient, dependency-free HTML-to-text extraction for emptiness checks.

Deliberately forgiving: answers "is there visible text here?", never "is this markup
well-formed?" - that is checks/html_well_formed.py's job, which needs a strict parser (lxml).
This module never raises.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    @property
    def text(self) -> str:
        return "".join(self._chunks)


def strip_tags_and_decode(fragment: str) -> str:
    """Strip HTML tags and decode entities, e.g. "<p>&nbsp;</p>" -> "\\xa0" (a real space
    character), not the literal text "&nbsp;". A naive tag-stripping regex leaves entities
    undecoded, so an entity-only field misreads as "has content" when it's visually empty -
    convert_charrefs=True decodes references while extracting text; html.unescape() is then
    applied again as cheap, idempotent defense-in-depth."""

    parser = _TextExtractor()
    parser.feed(fragment)
    parser.close()
    return html.unescape(parser.text)
