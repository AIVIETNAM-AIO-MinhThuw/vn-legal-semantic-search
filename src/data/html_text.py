"""HTML -> danh sách dòng văn bản thuần (SPEC 3.5). Bảng: mỗi hàng một dòng, ô nối bằng `|` (SPEC 3.4)."""
from __future__ import annotations

import re
import unicodedata

from lxml import etree, html as lhtml

BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "tr", "table", "thead", "tbody", "tfoot", "h1", "h2", "h3",
    "h4", "h5", "h6", "section", "article", "blockquote", "center", "hr", "pre", "dl", "dt", "dd",
    "caption", "form", "header", "footer", "body", "html",
}
SKIP_TAGS = {"script", "style", "head", "title", "noscript"}
CELL_TAGS = {"td", "th"}
_WS = re.compile(r"[ \t\r\f\v]+")
_ANY_WS = re.compile(r"\s+")
_ODD_SPACES = dict.fromkeys(map(ord, "             　"), " ")
_DROP = dict.fromkeys(map(ord, "​‌‍﻿­"), None)


def normalize_line(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(_ODD_SPACES).translate(_DROP)
    return _WS.sub(" ", s).strip()


def html_to_lines(raw: str, cell_sep: str = " | ") -> list[str]:
    """Trả về các dòng đã chuẩn hóa NFC, bỏ dòng rỗng. Thẻ inline không tạo ngắt dòng."""
    if raw is None or not raw.strip():
        return []
    root = lhtml.fromstring(raw)
    out: list[str] = []          # đoạn văn bản; "\n" là ngắt dòng
    rows: list[list[list[str]]] = []  # ngăn xếp các hàng bảng: mỗi hàng là list ô, mỗi ô là list đoạn
    skip_depth = 0

    def emit(txt: str) -> None:
        if not txt:
            return
        if rows and rows[-1]:
            rows[-1][-1].append(txt)
        else:
            out.append(txt)

    def brk() -> None:
        if rows and rows[-1]:
            rows[-1][-1].append(" ")  # trong ô: ngắt khối chỉ là khoảng trắng, không tách hàng
        elif not rows:
            out.append("\n")

    for event, el in etree.iterwalk(root, events=("start", "end")):
        if not isinstance(el.tag, str):  # comment / PI
            if event == "end" and el.tail and not skip_depth:
                emit(el.tail)
            continue
        tag = el.tag.lower()
        if event == "start":
            if tag in SKIP_TAGS:
                skip_depth += 1
            if skip_depth:
                continue
            if tag == "tr":
                brk()
                rows.append([])
            elif tag in CELL_TAGS and rows:
                rows[-1].append([])
            elif tag in BLOCK_TAGS:
                brk()
            if el.text:
                emit(el.text)
        else:
            if tag in SKIP_TAGS:
                skip_depth -= 1
            elif not skip_depth:
                if tag == "tr" and rows:
                    # Giữ vị trí ô rỗng; mọi khoảng trắng (kể cả xuống dòng) trong ô gộp thành một dấu cách.
                    cells = [normalize_line(_ANY_WS.sub(" ", "".join(c))) for c in rows.pop()]
                    if any(cells):  # hàng toàn ô rỗng bị bỏ
                        line = cell_sep.join(cells)
                        if rows and rows[-1]:
                            rows[-1][-1].append(" " + line + " ")  # bảng lồng trong ô
                        else:
                            out.append("\n" + line + "\n")
                elif tag in BLOCK_TAGS:
                    brk()
            if el.tail and not skip_depth:
                emit(el.tail)
    lines = [normalize_line(x) for x in "".join(out).split("\n")]
    return [x for x in lines if x]
