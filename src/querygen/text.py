"""Token hóa âm tiết, độ trùng từ vựng, chép nguyên văn N âm tiết (SPEC 5.3) và kiểm tra tham chiếu số hiệu (SPEC 5.2)."""
from __future__ import annotations

import re
import unicodedata

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_ARTICLE_REF = re.compile(r"\bđiều\s+\d+", re.IGNORECASE)
# số hiệu văn bản kiểu 05/2020/TT-BTC, 12/QĐ-TTg, 144/2020/NĐ-CP
_DOC_REF = re.compile(r"\b\d{1,4}/(?:\d{4}/)?[A-ZĐ][\wĐ\-]*")


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def syllables(text: str) -> list[str]:
    """NFC, chữ thường, tách theo khoảng trắng và dấu câu thành âm tiết; giữ dấu tiếng Việt; không bỏ stopword."""
    return _TOKEN.findall(normalize(text).lower())


def article_text(title: str, body: str) -> str:
    """Điều gồm tiêu đề và nội dung, không gồm tên văn bản (SPEC 5.3)."""
    return f"{title}\n{body}" if title else body


def overlap(query: str, article: str) -> float:
    """Số âm tiết khác nhau của query có mặt trong Điều / số âm tiết khác nhau của query."""
    q = set(syllables(query))
    if not q:
        return 0.0
    return len(q & set(syllables(article))) / len(q)


def has_verbatim_copy(query: str, article: str, n: int = 8) -> bool:
    """Query chứa một chuỗi liên tiếp từ n âm tiết trở lên lấy nguyên từ Điều."""
    q, a = syllables(query), syllables(article)
    if len(q) < n or len(a) < n:
        return False
    grams = {tuple(a[i:i + n]) for i in range(len(a) - n + 1)}
    return any(tuple(q[i:i + n]) in grams for i in range(len(q) - n + 1))


def refers_to_article_or_document_number(query: str) -> bool:
    q = normalize(query)
    return bool(_ARTICLE_REF.search(q) or _DOC_REF.search(q))


def _title_key(title: str) -> str:
    return " ".join(syllables(title))


def is_excluded_title(title: str, excluded: list[str]) -> bool:
    """Tiêu đề thuộc nhóm thi hành (so khớp nguyên cụm sau khi bỏ dấu câu / hoa thường)."""
    return _title_key(title) in {_title_key(t) for t in excluded}
