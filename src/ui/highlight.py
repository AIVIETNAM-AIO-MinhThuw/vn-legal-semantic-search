"""Cắt theo code point; chỉ HTML đã escape được đưa tới Streamlit."""
from html import escape

from src.contracts import Highlight


def render_html(content: str, spans: list[Highlight]) -> str:
    pieces = []
    cursor = 0
    for span in spans:
        pieces.extend((escape(content[cursor:span.start]), "<mark>",
                       escape(content[span.start:span.end]), "</mark>"))
        cursor = span.end
    pieces.append(escape(content[cursor:]))
    return '<div style="white-space: pre-wrap">' + "".join(pieces) + "</div>"


def snippet(content: str, spans: list[Highlight], width=250) -> tuple[str, list[Highlight]]:
    first = spans[0] if spans else None
    start = max(0, first.start - width // 3) if first else 0
    while start > 0 and not content[start - 1].isspace():
        start -= 1
    end = min(len(content), max(start + width, first.end if first else 0))
    while end < len(content) and not content[end].isspace():
        end += 1
    prefix = "…" if start else ""
    text = prefix + content[start:end].replace("\n", " ").replace("\r", " ") + ("…" if end < len(content) else "")
    offset = len(prefix) - start
    shifted = [Highlight(start=max(span.start, start) + offset, end=min(span.end, end) + offset)
               for span in spans if span.start < end and span.end > start]
    return text, shifted
