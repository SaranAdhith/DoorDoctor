"""Chandra's layout HTML, as plain text and as tables (Stage 2).

Chandra OCR 2 answers in its own trained format whatever it is asked:
`<div data-label="Table"><table>…</table></div><div data-label="Text"><p>…</p></div>`.
Two readers need it differently:

- the **LLM extractor** wants clean text, with tables as `a | b | c` rows so
  their columns survive, and without a thousand characters of `data-bbox`;
- the **table extractor** wants the tables themselves, cell by cell, because a
  lab table's columns *are* its meaning and can be read without any model.

`html.parser` from the standard library, not a new dependency. It never
executes anything; it only reports tags and text. A PDF's own text layer has no
tags and passes through `to_text` unchanged.
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

_BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "ul", "ol", "section"}
_DROP = {"script", "style", "noscript", "template"}
_TAG_HINT = re.compile(r"</?(div|p|table|tr|td|th|br|h[1-6]|ul|ol|li)\b", re.IGNORECASE)


def looks_like_html(text: str) -> bool:
    return bool(_TAG_HINT.search(text))


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._drop = 0
        self._table_depth = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    # -- text ------------------------------------------------------------------
    def _emit(self, text: str) -> None:
        if self._drop:
            return
        if self._cell is not None:
            self._cell.append(text)
        else:
            self.parts.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in _DROP:
            self._drop += 1
            return
        if tag == "br":
            self._emit("\n")
        elif tag == "img":
            alt = dict(attrs).get("alt") or ""
            if alt.strip():
                self._emit(f"[Image: {alt.strip()}]")
        elif tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self.tables.append([])
                self.parts.append("\n")
        elif tag == "tr" and self._table_depth:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP:
            self._drop = max(0, self._drop - 1)
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_squash("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._table_depth and self.tables and any(self._row):
                self.tables[-1].append(self._row)
                self.parts.append(" | ".join(self._row) + "\n")
            self._row = None
        elif tag == "table":
            self._table_depth = max(0, self._table_depth - 1)
            self.parts.append("\n")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._emit(data)


def _squash(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text.replace("\n", " ")).strip()


def _parse(html: str) -> _Reader:
    reader = _Reader()
    reader.feed(html)
    reader.close()
    return reader


def to_text(page_text: str) -> str:
    """Readable plain text. Plain text in, the same text out."""
    if not looks_like_html(page_text):
        return page_text.strip()
    joined = "".join(_parse(page_text).parts)
    lines = [_squash(line) for line in unescape(joined).split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def tables(page_text: str) -> list[list[list[str]]]:
    """Every table on the page as rows of cell strings. Empty for plain text."""
    if not looks_like_html(page_text):
        return []
    return [table for table in _parse(page_text).tables if table]
