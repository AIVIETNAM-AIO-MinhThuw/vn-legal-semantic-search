"""Tách Điều từ danh sách dòng (SPEC 3.4). Chỉ quy tắc cấu trúc; không lọc theo nội dung ngoài SPEC."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)\s*(?:[.:–-]\s*(.*)|)$")
# Tiêu đề viết "Điều 34 Trách nhiệm…" (không dấu chấm sau số): chỉ nhận khi số liền sau Điều đứng trước.
# Tiêu đề có chữ "Điều" bị lỗi OCR/mã hóa ở đầu dòng ("Điểu 1.", "Ðiều 1."). Từ đầu dòng được kiểm bằng _fold_word;
# chỉ nhận khi số đúng bằng số Điều kế tiếp. Không thay chữ "Điểu" trong nội dung thường.
ARTICLE_OCR_RE = re.compile(r"^\S+\s+(\d+[a-zđ]?)\s*[.:–-]\s*(.*)$")  # nhóm 1: số Điều, nhóm 2: tiêu đề (cùng bố cục với ARTICLE_RE)
ARTICLE_LOOSE_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)\s+([A-ZÀ-ỸĐ][^.;:]{0,150})$")
SECTION_RE = re.compile(r"^(Chương|CHƯƠNG|Mục|MỤC|Phần|PHẦN)\s+([IVXLCDM]+|\d+|thứ\s+\S+|THỨ\s+\S+)\b")
KHOAN_RE = re.compile(r"^\d{1,2}[.)]\s+\S")
POINT_RE = re.compile(r"^[a-zđ]\)\s+\S")
# Phụ lục / biểu mẫu: dòng ngắn, bắt đầu bằng cụm viết hoa (SPEC 3.4: loại khỏi corpus).
APPENDIX_RE = re.compile(r"^(PHỤ LỤC|PHỤ BIỂU|BIỂU MẪU|MẪU SỐ|Mẫu số|BIỂU SỐ|Biểu số)\b")
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
PLACEHOLDER_RE = re.compile(r"…|\.{3,}")  # chỗ trống trong mẫu biểu: "……", "..."
SIGN_TAIL_MAX_LINES = 8
LONG_TITLE_AS_BODY = 60  # tiêu đề Điều hiếm khi dài hơn 60 ký tự khi không có thân
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
    after_signature: bool = False  # Điều đứng sau khối chữ ký / nơi nhận: có thể thuộc phần đính kèm (cần người xem)
    preamble: list[str] = field(default_factory=list)  # dòng bị bỏ ngay trước tiêu đề Điều (chỉ sau chữ ký)
    form_template: bool = False  # bằng chứng biểu mẫu rõ ràng (lời dẫn quyết định + chỗ trống dài): loại như biểu mẫu
    form_uncertain: bool = False  # chỉ có dấu ba chấm thông thường: giữ tạm, gắn cờ cho người xác nhận
    form_evidence: dict = field(default_factory=dict)
    heading_line: int = -1  # chỉ số dòng (0-based, dòng văn bản đã chuẩn hóa) của tiêu đề Điều
    src_lines: list[int] = field(default_factory=list)  # chỉ số dòng nguồn của từng dòng trong `lines`

    @property
    def body(self) -> str:
        return "\n".join(self.lines)


@dataclass
class ParsedDoc:
    articles: list[Article]
    stats: dict
    dropped: list[dict] = field(default_factory=list)  # Điều nằm trong phần bị cắt (phụ lục / biểu mẫu)
    # line_owner[i] = chỉ số Điều (trong `articles`) sở hữu dòng i, hoặc mã âm: OWNER_NONE (đầu văn bản), OWNER_SECTION
    # (dòng Chương/Mục bị bỏ), OWNER_TRAILER (chữ ký / nơi nhận / lời dẫn sau chữ ký), OWNER_CUT (phụ lục / biểu mẫu bị cắt).
    line_owner: list[int] = field(default_factory=list)


OWNER_NONE, OWNER_SECTION, OWNER_TRAILER, OWNER_CUT = -1, -2, -3, -4


def _fold_word(word: str) -> str:
    """Bỏ dấu và hạ chữ thường; Đ/đ/Ð/ð -> d. Dùng để nhận biết 'Điều' bị lỗi OCR/mã hóa (Điểu, Ðiều…)."""
    word = word.replace("Ð", "D").replace("ð", "d").replace("Đ", "D").replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn").lower()


def _num(number: str) -> int:
    m = re.match(r"\d+", number)
    return int(m.group()) if m else -1


def _looks_like_structural(line: str) -> bool:
    return bool(ARTICLE_RE.match(line) or SECTION_RE.match(line) or KHOAN_RE.match(line) or POINT_RE.match(line))


def _is_title_like(line: str) -> bool:
    return len(line) <= 200 and not line.endswith((".", ";", ":")) and not _looks_like_structural(line)


def _heading_is_content(rest: str) -> bool:
    """Phần sau 'Điều N.' là câu nội dung (văn bản cũ không có tiêu đề riêng), không phải tiêu đề."""
    return len(rest) > 200 or (len(rest) > 25 and rest.endswith((".", ";")))


def quote_depths(lines: list[str]) -> tuple[list[int], bool, int]:
    """Độ sâu ngoặc kép “ ” TRƯỚC mỗi dòng. Trả về (depths, mơ_hồ, số_dấu_đóng_thừa).

    ” thừa (không có “ tương ứng) chỉ làm độ sâu về 0 và được đếm. Mơ hồ khi còn “ chưa đóng ở cuối văn bản:
    khi đó không dùng ngữ cảnh đoạn trích (trả về toàn 0) để một dấu mở lẻ không nuốt phần còn lại của văn bản;
    trường hợp được báo cáo."""
    depths, d, stray = [], 0, 0
    for l in lines:
        depths.append(d)
        d += l.count("“") - l.count("”")
        if d < 0:
            d, stray = 0, stray + 1
    if d != 0:
        return [0] * len(lines), True, stray
    return depths, False, stray


FORM_LEAD_RE = re.compile(r"^(Căn cứ|Theo đề nghị|QUYẾT ĐỊNH|Mẫu\b)")
LEAD_IN_RE = re.compile(r"^(QUYẾT ĐỊNH|Căn cứ|Theo đề nghị)")  # lời dẫn của một quyết định mẫu
STRONG_BLANK_RE = re.compile(r"…{2,}|\.{6,}")  # chỗ trống dài để điền: "……", "......"
WEAK_BLANK_RE = re.compile(r"…|\.{3,}")  # dấu ba chấm thông thường: không đủ để kết luận
PAREN_PLACEHOLDER_RE = re.compile(r"\((tên|ngày|số|nếu có)[^)]{0,40}\)", re.I)


def _split_next_form_lead_in(lines: list[str]) -> tuple[list[str], list[str]]:
    """Lời dẫn của mẫu biểu kế tiếp (Mẫu…, Căn cứ…, QUYẾT ĐỊNH:) rò vào cuối Điều đứng trước (trong 8 dòng cuối).
    Trả về (phần thân thật, phần lời dẫn). Chỉ dùng cho phát hiện, không sửa nội dung Điều."""
    for k in range(max(0, len(lines) - 8), len(lines)):
        if FORM_LEAD_RE.match(lines[k]):
            return lines[:k], lines[k:]
    return lines, []


def form_evidence(own_lines: list[str], lead_lines: list[str]) -> dict:
    """Bằng chứng biểu mẫu của một đoạn đính kèm. Dấu ba chấm đơn lẻ không phải bằng chứng."""
    strong = [l for l in own_lines + lead_lines if STRONG_BLANK_RE.search(l)]
    weak = [l for l in own_lines + lead_lines if WEAK_BLANK_RE.search(l) and not STRONG_BLANK_RE.search(l)]
    paren = [l for l in own_lines + lead_lines if PAREN_PLACEHOLDER_RE.search(l)]
    lead = any(LEAD_IN_RE.match(l) for l in lead_lines)
    # Rõ ràng: có lời dẫn của quyết định mẫu VÀ (chỗ trống dài, hoặc >= 2 dòng ba chấm kèm ô "(tên …)").
    clear = lead and (len(strong) >= 1 or (len(weak) >= 2 and len(paren) >= 1))
    return {"lead_in": lead, "strong_blank_lines": len(strong), "weak_ellipsis_lines": len(weak),
            "paren_placeholder_lines": len(paren), "clear": clear, "any_blank": bool(strong or weak)}


def after_signature_segments(arts: list[Article]) -> list[list[Article]]:
    """Chia các Điều sau chữ ký thành các đoạn đính kèm: một đoạn mới bắt đầu khi số Điều quay lại từ đầu."""
    segs: list[list[Article]] = []
    prev = None
    for a in arts:
        if not a.after_signature:
            prev = None
            continue
        n = _num(a.number)
        if prev is None or n <= prev:
            segs.append([])
        segs[-1].append(a)
        prev = n
    return segs


def _mark_form_templates(arts: list[Article], stats: dict) -> None:
    """Phần đứng sau chữ ký gồm nhiều đoạn (số Điều bắt đầu lại từ đầu). Đoạn có bằng chứng biểu mẫu rõ ràng
    thì bị loại (SPEC 3.4); đoạn chỉ có dấu ba chấm thông thường được gắn cờ form_uncertain và giữ tạm."""
    segs = after_signature_segments(arts)
    leaked: list[list[str]] = [[] for _ in segs]  # lời dẫn của đoạn k bị rò vào cuối Điều cuối của đoạn k-1
    own: list[list[str]] = []
    for k, seg in enumerate(segs):
        lines = list(seg[0].preamble)
        for j, x in enumerate(seg):
            body, lead = _split_next_form_lead_in(x.lines)
            lines.append(x.title)
            lines.extend(body)
            if j == len(seg) - 1 and k + 1 < len(segs):
                leaked[k + 1] = lead
        own.append(lines)
    for k, seg in enumerate(segs):
        ev = form_evidence(own[k] + leaked[k], list(seg[0].preamble) + leaked[k])
        for a in seg:
            a.form_evidence = ev
        if ev["clear"]:
            for a in seg:
                a.form_template = True
            stats["form_template_articles"] += len(seg)
        elif ev["any_blank"]:
            for a in seg:
                a.form_uncertain = True
            stats["form_uncertain_articles"] += len(seg)


def parse_articles(lines: list[str]) -> ParsedDoc:
    stats = {"appendix_cut": False, "appendix_lines": 0, "trailer_lines": 0,
             "title_from_next_line": 0, "section_lines_skipped": 0, "dup_numbers": 0,
             "heading_text_as_body": 0, "ambiguous_quote": 0, "quote_stray_closers": 0, "quoted_lines": 0, "straight_quote_article": 0,
             "articles_after_signature": 0, "heading_without_punct": 0, "heading_ocr_variant": 0, "form_template_articles": 0, "form_uncertain_articles": 0}
    depths, ambiguous, stray = quote_depths(lines)
    stats["ambiguous_quote"] = int(ambiguous)
    stats["quote_stray_closers"] = int(stray > 0)
    arts: list[Article] = []
    cur: Article | None = None
    after_sig = False
    pending: list[str] = []
    dropped: list[dict] = []
    i, n = 0, len(lines)
    owner = [OWNER_NONE] * n
    while i < n:
        line = lines[i]
        if depths[i] > 0:  # đang trong đoạn trích: mọi dòng là nội dung của Điều nguồn
            stats["quoted_lines"] += 1
            if cur is not None:
                cur.lines.append(line)
                cur.src_lines.append(i)
                owner[i] = len(arts) - 1
            elif after_sig:
                owner[i] = OWNER_TRAILER
            i += 1
            continue
        if re.match(r'^"\s*Điều\s+\d+', line):
            stats["straight_quote_article"] += 1  # trích bằng ngoặc thẳng: không phân biệt được đóng/mở
        if (APPENDIX_RE.match(line) or APPENDIX_SHORT_RE.match(line)) and len(line) <= 80:
            stats["appendix_cut"] = True
            stats["appendix_lines"] = n - i
            for j in range(i, n):  # ghi nhận Điều bị cắt để log từng Điều bị loại
                owner[j] = OWNER_CUT
                mj = ARTICLE_RE.match(lines[j])
                if mj and depths[j] == 0:
                    dropped.append({"number": mj.group(1), "title": (mj.group(2) or "")[:120], "line": j,
                                    "reason": "appendix_or_form_cut", "marker": line[:60]})
            break
        if TRAILER_RE.match(line):
            # Khối chữ ký / nơi nhận kết thúc nội dung của Điều hiện tại. Dòng đứng sau bị bỏ cho tới Điều kế tiếp;
            # Điều kế tiếp (nếu có) là phần đính kèm (quy chế, quy chuẩn…): giữ lại nhưng gắn cờ after_signature,
            # vì SPEC 3.4 chỉ loại phụ lục và biểu mẫu, không nói rõ về quy chế/quy chuẩn ban hành kèm theo.
            after_sig = True
            cur = None
            pending = []
            stats["trailer_lines"] += 1
            owner[i] = OWNER_TRAILER
            i += 1
            continue
        m = ARTICLE_RE.match(line)
        loose = None
        if not m:
            ml = ARTICLE_LOOSE_RE.match(line)
            expected = _num(arts[-1].number) + 1 if arts else 1  # tiêu đề đầu tiên chỉ nhận khi là Điều 1
            if ml and _num(ml.group(1)) == expected:
                loose = ml
                stats["heading_without_punct"] += 1
            elif not ml:
                # Chữ "Điều" bị lỗi OCR/mã hóa ở ĐẦU dòng (vd. "Điểu 1. …", "Ðiều 1. …"): chỉ nhận khi từ đầu dòng, sau khi bỏ dấu,
                # đúng là "dieu", có số + dấu chấm/hai chấm/gạch, và số đúng bằng số Điều kế tiếp (Điều 1 nếu chưa có Điều nào).
                mo = ARTICLE_OCR_RE.match(line)
                first = line.split(None, 1)[0]
                if mo and first != "Điều" and _fold_word(first) == "dieu" and _num(mo.group(1)) == expected:
                    loose = mo
                    stats["heading_ocr_variant"] += 1
        if m or loose:
            hm = m or loose
            title = (hm.group(2) or "").strip()
            if title and _heading_is_content(title):
                cur = Article(number=hm.group(1), title="", lines=[title], after_signature=after_sig,
                              preamble=pending[-6:], heading_line=i, src_lines=[i])
                pending = []
                stats["articles_after_signature"] += int(after_sig)
                arts.append(cur)
                owner[i] = len(arts) - 1
                stats["heading_text_as_body"] += 1
                i += 1
                continue
            head_i = i
            if not title and i + 1 < n and depths[i + 1] == 0 and _is_title_like(lines[i + 1]):
                title = lines[i + 1]
                owner[i + 1] = len(arts)  # dòng tên Điều thuộc Điều sắp tạo
                i += 1
                stats["title_from_next_line"] += 1
            cur = Article(number=hm.group(1), title=title, after_signature=after_sig, preamble=pending[-6:],
                          heading_line=head_i)
            pending = []
            stats["articles_after_signature"] += int(after_sig)
            arts.append(cur)
            owner[head_i] = len(arts) - 1
        elif SECTION_RE.match(line) and len(line) <= 150:
            # Chương/Mục/Phần không thuộc nội dung Điều đứng trước; bỏ dòng này và dòng tên của nó.
            stats["section_lines_skipped"] += 1
            owner[i] = OWNER_SECTION
            if line == SECTION_RE.match(line).group(0) and i + 1 < n and depths[i + 1] == 0 \
                    and _is_title_like(lines[i + 1]):
                i += 1
                owner[i] = OWNER_SECTION
                stats["section_lines_skipped"] += 1
        elif cur is not None:
            cur.lines.append(line)
            cur.src_lines.append(i)
            owner[i] = len(arts) - 1
        elif after_sig:
            stats["trailer_lines"] += 1
            owner[i] = OWNER_TRAILER
            pending.append(line)
        i += 1
    # Điều không có thân nhưng "tiêu đề" dài bất thường: đó là câu nội dung viết cùng dòng với "Điều N.".
    for a in arts:
        if not a.lines and len(a.title) > LONG_TITLE_AS_BODY:
            a.lines, a.title = [a.title], ""
            a.src_lines = [a.heading_line]
            stats["heading_text_as_body"] += 1
    # Chữ ký viết hoa (chức danh) ở đuôi Điều cuối khi không có "Nơi nhận" / "TM." / "KT." đứng trước.
    if arts and not stats["trailer_lines"]:
        last = arts[-1]
        for k, l in enumerate(last.lines):
            tail = len(last.lines) - k
            if SIGN_TITLE_RE.match(l) and tail <= SIGN_TAIL_MAX_LINES:
                stats["trailer_lines"] = tail
                for idx in last.src_lines[k:]:
                    owner[idx] = OWNER_TRAILER
                last.lines = last.lines[:k]
                last.src_lines = last.src_lines[:k]
                break
    _mark_form_templates(arts, stats)
    seen: set[str] = set()
    for a in arts:
        if a.number in seen:
            stats["dup_numbers"] += 1
        seen.add(a.number)
    return ParsedDoc(arts, stats, dropped, owner)


def article_reject_reason(a: Article) -> str | None:
    if a.form_template:
        return "form_template"
    body = a.body.strip()
    if not body:
        return "title_only"
    probe = re.sub(r"^[\W_]+", "", body.lower())
    if len(body) <= 300 and REPEAL_RE.match(probe):
        return "repeal_note"
    return None
