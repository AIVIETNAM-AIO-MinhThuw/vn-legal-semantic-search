"""Tách Điều từ danh sách dòng (SPEC 3.4). Chỉ quy tắc cấu trúc; không lọc theo nội dung ngoài SPEC."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)\s*(?:[.:–-]\s*(.*)|)$")
SECTION_RE = re.compile(r"^(Chương|CHƯƠNG|Mục|MỤC|Phần|PHẦN)\s+([IVXLCDM]+|\d+|thứ\s+\S+|THỨ\s+\S+)\b")
KHOAN_RE = re.compile(r"^\d{1,2}[.)]\s+\S")
POINT_RE = re.compile(r"^[a-zđ]\)\s+\S")
# Phụ lục / biểu mẫu: dòng ngắn, bắt đầu bằng cụm viết hoa (SPEC 3.4: loại khỏi corpus).
APPENDIX_RE = re.compile(r"^(PHỤ LỤC|PHỤ BIỂU|BIỂU MẪU|MẪU SỐ)\b")
APPENDIX_SHORT_RE = re.compile(r"^Phụ lục\s+[IVXLC\d]+\s*$")
TRAILER_RE = re.compile(
    r"^(Nơi nhận\s*:?|TM\.|T/M|KT\.|TL\.|TUQ\.|Q\.\s"
    r"|(Luật|Bộ luật|Pháp lệnh|Nghị quyết)\s+này\s+(đã\s+)?được\s+(Quốc hội|Ủy ban Thường vụ).*thông qua)"
)
# Chức danh ký (viết hoa) chỉ được coi là chữ ký khi nằm ở đuôi Điều cuối: dòng viết hoa ngắn khác là nội dung.
SIGN_TITLE_RE = re.compile(
    r"^(CHỦ TỊCH|PHÓ CHỦ TỊCH|THỦ TƯỚNG|PHÓ THỦ TƯỚNG|BỘ TRƯỞNG|THỨ TRƯỞNG|TỔNG|GIÁM ĐỐC|PHÓ GIÁM ĐỐC"
    r"|CHỦ NHIỆM|TRƯỞNG BAN|CHÁNH VĂN PHÒNG|QUYỀN|PHÓ TỔNG)\b"
)
SIGN_TAIL_MAX_LINES = 8
# Ghi chú "Điều này đã bị bãi bỏ / hết hiệu lực" (tự nói về Điều). Điều có nội dung tác nghiệp kiểu
# "Bãi bỏ Thông tư X" là nội dung thật, không khớp mẫu này.
REPEAL_RE = re.compile(
    r"^(?:(?:điều\s+này\s+)?(?:đã\s+)?(?:được|bị)\s+(?:bãi bỏ|hết hiệu lực)"
    r"|điều\s+này\s+(?:đã\s+)?(?:bãi bỏ|hết hiệu lực)"
    r"|đã\s+(?:bị\s+)?(?:bãi bỏ|hết hiệu lực)"
    r"|(?:bãi bỏ|hết hiệu lực|bỏ)[\W_]*$)"
)


@dataclass
class Article:
    number: str
    title: str
    lines: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return "\n".join(self.lines)


@dataclass
class ParsedDoc:
    articles: list[Article]
    stats: dict


def _looks_like_structural(line: str) -> bool:
    return bool(ARTICLE_RE.match(line) or SECTION_RE.match(line) or KHOAN_RE.match(line) or POINT_RE.match(line))


def _is_title_like(line: str) -> bool:
    return len(line) <= 200 and not line.endswith((".", ";", ":")) and not _looks_like_structural(line)


def _heading_is_content(rest: str) -> bool:
    """Phần sau 'Điều N.' là câu nội dung (văn bản cũ không có tiêu đề riêng), không phải tiêu đề."""
    return len(rest) > 200 or (len(rest) > 25 and rest.endswith((".", ";")))


def quote_depths(lines: list[str]) -> tuple[list[int], bool]:
    """Độ sâu ngoặc kép “ ” TRƯỚC mỗi dòng. Trả về (depths, mơ_hồ).

    Mơ hồ khi ngoặc không cân bằng (còn mở ở cuối văn bản, hoặc có ” thừa). Khi đó không dùng ngữ cảnh
    đoạn trích (trả về toàn 0) để một dấu ngoặc lẻ không nuốt cả văn bản; trường hợp được báo cáo."""
    depths, d, ambiguous = [], 0, False
    for l in lines:
        depths.append(d)
        d += l.count("“") - l.count("”")
        if d < 0:
            d, ambiguous = 0, True
    if d != 0:
        ambiguous = True
    return ([0] * len(lines) if ambiguous else depths), ambiguous


def parse_articles(lines: list[str]) -> ParsedDoc:
    stats = {"appendix_cut": False, "appendix_lines": 0, "trailer_lines": 0,
             "title_from_next_line": 0, "section_lines_skipped": 0, "dup_numbers": 0,
             "heading_text_as_body": 0, "ambiguous_quote": 0, "quoted_lines": 0, "straight_quote_article": 0}
    depths, ambiguous = quote_depths(lines)
    stats["ambiguous_quote"] = int(ambiguous)
    arts: list[Article] = []
    cur: Article | None = None
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if depths[i] > 0:  # đang trong đoạn trích: mọi dòng là nội dung của Điều nguồn
            stats["quoted_lines"] += 1
            if cur is not None:
                cur.lines.append(line)
            i += 1
            continue
        if re.match(r'^"\s*Điều\s+\d+', line):
            stats["straight_quote_article"] += 1  # trích bằng ngoặc thẳng: không phân biệt được đóng/mở
        if (APPENDIX_RE.match(line) or APPENDIX_SHORT_RE.match(line)) and len(line) <= 80:
            stats["appendix_cut"] = True
            stats["appendix_lines"] = n - i
            break
        m = ARTICLE_RE.match(line)
        if m:
            title = (m.group(2) or "").strip()
            if title and _heading_is_content(title):
                cur = Article(number=m.group(1), title="", lines=[title])
                arts.append(cur)
                stats["heading_text_as_body"] += 1
                i += 1
                continue
            if not title and i + 1 < n and depths[i + 1] == 0 and _is_title_like(lines[i + 1]):
                title = lines[i + 1]
                i += 1
                stats["title_from_next_line"] += 1
            cur = Article(number=m.group(1), title=title)
            arts.append(cur)
        elif SECTION_RE.match(line) and len(line) <= 150:
            # Chương/Mục/Phần không thuộc nội dung Điều đứng trước; bỏ dòng này và dòng tên của nó.
            stats["section_lines_skipped"] += 1
            if line == SECTION_RE.match(line).group(0) and i + 1 < n and depths[i + 1] == 0 \
                    and _is_title_like(lines[i + 1]):
                i += 1
                stats["section_lines_skipped"] += 1
        elif cur is not None:
            cur.lines.append(line)
        i += 1
    # Cắt phần chữ ký / nơi nhận ở Điều cuối.
    if arts:
        last = arts[-1]
        for k, l in enumerate(last.lines):
            tail = len(last.lines) - k
            if TRAILER_RE.match(l) or (SIGN_TITLE_RE.match(l) and tail <= SIGN_TAIL_MAX_LINES):
                stats["trailer_lines"] = tail
                last.lines = last.lines[:k]
                break
    seen: set[str] = set()
    for a in arts:
        if a.number in seen:
            stats["dup_numbers"] += 1
        seen.add(a.number)
    return ParsedDoc(arts, stats)


def article_reject_reason(a: Article) -> str | None:
    body = a.body.strip()
    if not body:
        return "title_only"
    probe = re.sub(r"^[\W_]+", "", body.lower())
    if len(body) <= 300 and REPEAL_RE.match(probe):
        return "repeal_note"
    return None
