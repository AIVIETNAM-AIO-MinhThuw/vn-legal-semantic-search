"""Ba bảng đối chiếu cho người duyệt corpus trước split (SPEC 3.4, 3.6).

  A. văn bản trong index có “ chưa đóng (parser không dùng ngữ cảnh đoạn trích cho các văn bản này)
  B. văn bản trong index có phần after_signature (đính kèm sau chữ ký / nơi nhận)
  C. văn bản trong index có ” thừa (parser vẫn dùng ngữ cảnh đoạn trích)

Danh sách được xác định lại từ output hiện tại bằng cách parse lại HTML gốc của MỌI văn bản trong index (không đọc
danh sách từ log nên không bỏ sót). Script chuẩn bị tự động bằng chứng và đề xuất; các cột người duyệt để "Chờ xác nhận".
Kết quả tự động không phải kết luận của người.

Quy ước số dòng: dòng văn bản đã chuẩn hóa do `html_to_lines` trả về, đánh số từ 1. Cách truy về HTML gốc:
`python -X utf8 scripts/show_source.py --doc <doc_id> --lines a-b --html`.

Chạy:  python -X utf8 scripts/build_review_tables.py --config configs/data.yaml
Đầu ra:
  .scratch/task_1_review/ (mặc định, --work-dir): ba CSV A/B/C, bảng chi tiết, Markdown, bảng phụ trợ, README (local)
  reports/data_stats/after_filter/review/: README.md, confirmation.json, ba CSV A/B/C đã được người duyệt.
    Script chỉ ĐỌC confirmation.json ở đây; chỉ ghi README và CSV nào còn thiếu khi có --publish,
    không bao giờ ghi đè CSV đã có hay confirmation.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import parse as P  # noqa: E402
from src.data.html_text import html_to_lines  # noqa: E402

PENDING = "Chờ xác nhận"
CONFIRMATION: dict | None = None  # nạp từ review/confirmation.json (người dùng yêu cầu ghi nhận xác nhận của người duyệt)
OK = "Đủ bằng chứng tự động"  # vẫn chờ người xác nhận
LOOK = "Cần người xem"
INSUFF = "Chưa đủ bằng chứng"
RANK = {OK: 0, LOOK: 1, INSUFF: 2}
HUMAN_COLS = ["reviewer_name", "review_date", "review_result", "review_note"]
CONTENT_PARQUET = "data/raw/data/content.parquet"
PUBLISHED_CSVS = ("table_A_unclosed_open_quote.csv", "table_B_after_signature.csv", "table_C_stray_closing_quote.csv")
TAGS = {P.OWNER_NONE: "đầu", P.OWNER_SECTION: "chương", P.OWNER_TRAILER: "ký", P.OWNER_CUT: "cắt"}


def read_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def short(s: str, n: int = 170) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def window(line: str, col: int, before: int = 80, after: int = 140) -> str:
    """Cửa sổ ký tự quanh một cột của dòng (để thấy dấu ngoặc ngay cả khi dòng dài)."""
    a, b = max(0, col - before), min(len(line), col + after)
    return ("…" if a > 0 else "") + line[a:b] + ("…" if b < len(line) else "")


def human_blank() -> dict:
    """Cột người duyệt. Mặc định để trống / PENDING; chỉ được điền khi có confirmation.json do người dùng cung cấp
    (người duyệt, ngày, kết quả nhập theo xác nhận của người duyệt; không tự xác nhận)."""
    if CONFIRMATION:
        c = CONFIRMATION
        return {"reviewer_name": c["reviewer"], "review_date": c["date"], "review_result": c["result"], "review_note": c["note"]}
    return {"reviewer_name": "", "review_date": "", "review_result": PENDING, "review_note": ""}


class Ctx:
    def __init__(self, doc_id: str, title: str, lines: list[str], index_ids: set[str], rejected: dict[str, str]):
        self.doc_id, self.title, self.lines = doc_id, title, lines
        self.parsed = P.parse_articles(lines)
        self.art_ids = [f"{doc_id}_{k + 1:03d}" for k in range(len(self.parsed.articles))]
        self.status = []
        for aid in self.art_ids:
            if aid in rejected:
                self.status.append("loại: " + rejected[aid])
            elif aid not in index_ids:
                self.status.append("loại do trùng (dedup)")
            else:
                self.status.append("trong index")

    def tag(self, i: int) -> str:
        o = self.parsed.line_owner[i]
        if o >= 0:
            a = self.parsed.articles[o]
            return f"Đ{a.number}" + ("*" if a.after_signature else "")
        return TAGS[o]

    def is_heading(self, i: int) -> bool:
        o = self.parsed.line_owner[i]
        return o >= 0 and self.parsed.articles[o].heading_line == i

    def art_label(self, k: int) -> str:
        a = self.parsed.articles[k]
        return f"Điều {a.number}{' (sau chữ ký)' if a.after_signature else ''} — {short(a.title or '<nội dung>', 50)} [{self.art_ids[k]}; {self.status[k]}]"

    def owner_label(self, i: int) -> str:
        o = self.parsed.line_owner[i]
        if o >= 0:
            return self.art_label(o)
        return {P.OWNER_NONE: "không thuộc Điều nào (đầu văn bản)", P.OWNER_SECTION: "dòng Chương/Mục bị bỏ",
                P.OWNER_TRAILER: "chữ ký / nơi nhận / lời dẫn sau chữ ký (bị bỏ)",
                P.OWNER_CUT: "phụ lục / biểu mẫu bị cắt"}[o]

    def fmt(self, a: int, b: int, width: int = 170) -> list[str]:
        out = []
        for i in range(max(0, a), min(len(self.lines), b + 1)):
            out.append(f"{'▶' if self.is_heading(i) else ' '}L{i + 1} [{self.tag(i)}] {short(self.lines[i], width)}")
        return out


def quote_scan(lines: list[str]) -> dict:
    """Quét ngoặc “ ” giống quote_depths của parser, nhưng giữ lại vị trí."""
    d, region_start, last_open = 0, None, None
    strays, before = [], []
    for i, l in enumerate(lines):
        before.append(d)
        o, c = l.count("“"), l.count("”")
        nd = d + o - c
        if d == 0 and nd > 0:
            region_start = i
            last_open = i
        stray = None
        if nd < 0:
            pos = [k for k, ch in enumerate(l) if ch == "”"]
            excess = -nd
            stray = {"line": i, "excess": excess, "char_offset": pos[-excess] if excess <= len(pos) else pos[-1],
                     "region_start": region_start if d > 0 else (i if o > 0 else None), "depth_before": d}
            nd = 0
        if nd == 0:
            if stray is not None:
                strays.append(stray)
            region_start = None
        d = nd
    return {"before": before, "strays": strays, "final_depth": d, "last_open": last_open if d > 0 else None}


def region_scan(ctx: Ctx) -> list[dict]:
    """Mọi vùng trích dẫn (độ sâu > 0) mà parser dùng làm ngữ cảnh, kèm tiêu đề Điều nằm trong vùng và nguy cơ
    'Điều thật bị nuốt' (số tiêu đề = Điều top-level liền trước + 1)."""
    if ctx.parsed.stats["ambiguous_quote"]:
        return []
    depths, _, _ = P.quote_depths(ctx.lines)
    out, i, n = [], 0, len(ctx.lines)
    while i < n:
        if depths[i] > 0:
            j = i
            while j + 1 < n and depths[j + 1] > 0:
                j += 1
            inner = [(k, P.ARTICLE_RE.match(ctx.lines[k])) for k in range(i, j + 1) if P.ARTICLE_RE.match(ctx.lines[k])]
            prev = last_top_heading_before(ctx, i)
            pn = P._num(prev[1].number) if prev else 0
            for k, m in inner:
                out.append({"doc_id": ctx.doc_id, "region": f"L{i + 1}–L{j + 1}", "heading_line": k + 1, "heading_number": m.group(1),
                            "previous_top_level_number": pn, "possible_real_article": P._num(m.group(1)) == pn + 1,
                            "heading_text": short(ctx.lines[k], 100), "context": chr(10).join(ctx.fmt(k - 1, k + 1))})
            i = j + 1
        else:
            i += 1
    return out


def last_top_heading_before(ctx: Ctx, i: int):
    best = None
    for k, a in enumerate(ctx.parsed.articles):
        if a.heading_line < i and not a.after_signature:
            best = (k, a)
    return best


def headings_after(ctx: Ctx, i: int, limit: int = 8):
    out, prev = [], last_top_heading_before(ctx, i)
    prev_num = P._num(prev[1].number) if prev else 0
    for k, a in enumerate(ctx.parsed.articles):
        if a.heading_line > i and not a.after_signature:
            n = P._num(a.number)
            out.append({"line": a.heading_line + 1, "number": a.number, "title": short(a.title or "<nội dung>", 60),
                        "article_id": ctx.art_ids[k], "consecutive_with_previous": n == prev_num + 1,
                        "previous_line": short(ctx.lines[a.heading_line - 1], 110) if a.heading_line > 0 else ""})
            prev_num = n
            if len(out) >= limit:
                break
    return out


def boundary_loss(ctx: Ctx) -> dict:
    """Mất nội dung giữa các Điều: dòng không thuộc Điều nào nằm trong khoảng từ tiêu đề đầu tiên tới dòng cuối của Điều cuối."""
    arts = ctx.parsed.articles
    if not arts:
        return {"lost_lines": 0, "section_lines": 0}
    h0 = min(a.heading_line for a in arts)
    last = max((max(a.src_lines) if a.src_lines else a.heading_line) for a in arts)
    owner = ctx.parsed.line_owner
    return {"lost_lines": sum(1 for i in range(h0, last + 1) if owner[i] == P.OWNER_NONE),
            "section_lines": sum(1 for i in range(h0, last + 1) if owner[i] == P.OWNER_SECTION)}


def common_row(ctx: Ctx, group: str, groups: str) -> dict:
    return {"doc_id": ctx.doc_id, "title": ctx.title, "warning_groups": groups,
            "source_path": f"{CONTENT_PARQUET} (id = {ctx.doc_id}, cột content_html); bản trích: data/processed/review_cache/{ctx.doc_id}.html",
            "output_path": f"data/processed/articles_index.jsonl và articles.jsonl (doc_id = {ctx.doc_id}); logs/parse_anomalies.jsonl; logs/rejected.jsonl"}


# ---------------------------------------------------------------- A: “ chưa đóng
def analyse_A(ctx: Ctx, groups: str) -> tuple[dict, list[dict]]:
    qs = quote_scan(ctx.lines)
    start = qs["last_open"]
    row = common_row(ctx, "A", groups)
    after = headings_after(ctx, start) if start is not None else []
    loss = boundary_loss(ctx)
    opener = ctx.lines[start]
    starts_with_quote = opener.lstrip().startswith("“")
    after_text = opener[opener.rfind("“") + 1:]
    closed_straight = '"' in after_text[:100]  # đóng bằng ngoặc thẳng ngay sau dấu mở (thuật ngữ ngắn)
    n_open, n_close = sum(l.count("“") for l in ctx.lines), sum(l.count("”") for l in ctx.lines)
    first_next = after[0]["line"] - 1 if after else None
    span = (first_next - start) if first_next is not None else len(ctx.lines) - start
    owner = ctx.parsed.line_owner[start]
    outside = owner < 0
    inner_suspect = [h for h in after if not h["consecutive_with_previous"]]
    if not after:
        level, why = OK, "không có Điều nào đứng sau dấu mở, nên không Điều thật nào có thể bị ảnh hưởng"
        if outside:
            why += "; dấu mở nằm ngoài các Điều trong index (" + ctx.owner_label(start) + ")"
    elif closed_straight:
        level, why = OK, 'dấu “ được đóng bằng ngoặc thẳng " trong vòng 100 ký tự cùng dòng (thuật ngữ/cụm trong ngoặc), không kéo qua các Điều sau'
    elif inner_suspect:
        level, why = LOOK, f"{len(inner_suspect)} tiêu đề sau dấu mở có số không liền sau Điều trước (có thể là Điều trích dẫn bị tách)"
    elif span > 120:
        level, why = INSUFF, f"khoảng từ dấu mở tới tiêu đề kế tiếp dài {span} dòng, bản trích chỉ hiện đầu/cuối; cần mở nguồn"
    else:
        level, why = LOOK, ("dấu mở nằm ở đầu đoạn (có thể là đoạn trích) và còn Điều đứng sau; số Điều liên tục nhưng chưa đủ để kết luận "
                            "không có Điều bị nuốt hay tách; cần xem khoảng từ dấu mở tới tiêu đề kế tiếp"
                            if starts_with_quote else
                            "dấu “ lẻ giữa câu, không tìm thấy dấu đóng cùng dòng; cần xem khoảng từ dấu mở tới tiêu đề kế tiếp")
    ev = ctx.fmt(start - 3, start + 3)
    col = opener.rfind("“")
    ev.append(f"  ⌖ cửa sổ quanh “ cuối cùng của L{start + 1} (cột {col}): {window(opener, col)}")
    if first_next is not None:
        ev += ["  …"] + ctx.fmt(first_next - 2, first_next + 1)
    row.update({
        "compared_range": f"dòng 1–{len(ctx.lines)}; {len(ctx.parsed.articles)} Điều parse; dấu mở L{start + 1}; vùng sau dấu mở "
                          f"L{start + 1}–L{len(ctx.lines)} ({len(after)} tiêu đề Điều top-level, hiển thị tối đa 8)",
        "source_evidence": "\n".join(ev),
        "parser_result": (f"Dòng dấu mở thuộc: {ctx.owner_label(start)}. Số “={n_open}, ”={n_close}. "
                          f"Parser không dùng ngữ cảnh đoạn trích cho văn bản này (có “ chưa đóng), nên mọi tiêu đề sau dấu mở đều thành Điều. "
                          f"Tiêu đề sau dấu mở: " + "; ".join(f"L{h['line']} Điều {h['number']}{'' if h['consecutive_with_previous'] else ' (số không liền)'}" for h in after)
                          + f". Mất nội dung giữa các Điều: {loss['lost_lines']} dòng; dòng Chương/Mục bị bỏ: {loss['section_lines']}."),
        "issue": ("Đoạn trích mở bằng “ nhưng không có ” tương ứng" if starts_with_quote else
                  "Dấu “ lẻ giữa câu (tên đề án, tiêu chuẩn, thuật ngữ hoặc mẫu biểu)") + f". {why}",
        "possible_impact": "Nếu phần sau dấu mở thật ra là đoạn trích, các Điều trích dẫn bị tách thành Điều độc lập (thừa Điều, sai số Điều, ảnh hưởng dedup và số Điều của luật B). "
                           "Nếu dấu mở chỉ là ngoặc lẻ trong câu thì không ảnh hưởng.",
        "automated_proposal": ("Đề xuất giữ nguyên parser." if level == OK else
                        "Người xem khoảng từ dấu mở tới tiêu đề kế tiếp (lệnh show_source ở README); nếu là đoạn trích không đóng, đề xuất thêm quy tắc đóng đoạn trích tại tiêu đề Điều liền kế."),
        "automated_evidence_level": level, "opener_line": start + 1,
        "opener_category": "đoạn trích/thuật ngữ mở đầu dòng" if starts_with_quote else "dấu lẻ giữa câu",
        "headings_after_count": len(after), **human_blank(),
    })
    detail = [{"doc_id": ctx.doc_id, "opener_line": start + 1, **h} for h in after]
    return row, detail


# ---------------------------------------------------------------- C: ” thừa
def analyse_C(ctx: Ctx, groups: str) -> tuple[dict, list[dict]]:
    qs = quote_scan(ctx.lines)
    ambiguous = qs["final_depth"] > 0
    row = common_row(ctx, "C", groups)
    positions, worst = [], OK
    for n, s in enumerate(qs["strays"], 1):
        i = s["line"]
        rs = s["region_start"]
        inner, owners = [], set()
        if rs is not None:
            for j in range(rs, i + 1):
                if ctx.parsed.line_owner[j] >= 0:
                    owners.add(ctx.parsed.line_owner[j])
                if j > rs or not ctx.lines[j].lstrip().startswith("“"):
                    pass
                if P.ARTICLE_RE.match(ctx.lines[j]):
                    inner.append(j)
        prev = last_top_heading_before(ctx, rs if rs is not None else i)
        prev_num = P._num(prev[1].number) if prev else 0
        inner_info = []
        swallow = False
        for j in inner:
            m = P.ARTICLE_RE.match(ctx.lines[j])
            num = P._num(m.group(1))
            as_article = ctx.is_heading(j)
            maybe_real = num == prev_num + 1 and not as_article
            swallow = swallow or maybe_real
            inner_info.append(f"L{j + 1} Điều {m.group(1)} ({'thành Điều độc lập' if as_article else 'giữ làm nội dung'}"
                              f"{'; số = Điều trước + 1: có thể là Điều thật bị nuốt' if maybe_real else ''})")
        length = (i - rs + 1) if rs is not None else 0
        if rs is None:
            level, why = OK, "dấu ” thừa không có vùng trích dẫn mở trước đó; không có vùng nào bị parser coi là đoạn trích"
        elif not inner and length <= 60 and len(owners) <= 1:
            level, why = OK, f"vùng trích dẫn L{rs + 1}–L{i + 1} ({length} dòng) không chứa tiêu đề Điều và thuộc một Điều"
        elif length > 120:
            level, why = INSUFF, f"vùng trích dẫn dài {length} dòng, bản trích chỉ hiện đầu/cuối; cần mở nguồn"
        elif swallow:
            level, why = LOOK, "trong vùng trích dẫn có tiêu đề có số = Điều trước + 1 chưa thành Điều: có thể là Điều thật bị nuốt"
        elif inner:
            level, why = LOOK, f"vùng trích dẫn chứa {len(inner)} tiêu đề Điều được giữ làm nội dung: cần xác nhận đây là Điều trích dẫn, không phải Điều thật"
        else:
            level, why = LOOK, f"vùng trích dẫn có {len(owners)} Điều sở hữu; cần xem ranh giới"
        worst = max(worst, level, key=lambda x: RANK[x])
        ctx_lines = []
        ctx_lines.append(f"  ⌖ cửa sổ quanh ” thừa của L{i + 1} (cột {s['char_offset']}): {window(ctx.lines[i], s['char_offset'])}")
        if rs is not None and length > 14:
            ctx_lines += ctx.fmt(rs, rs + 2) + ["  … (rút gọn) …"] + [f for j in inner[:6] for f in ctx.fmt(j - 1, j + 1)] + ctx.fmt(i - 2, i + 2)
        else:
            ctx_lines += ctx.fmt((rs if rs is not None else i) - 2, i + 2)
        after_h = headings_after(ctx, i, 2)
        positions.append({
            "doc_id": ctx.doc_id, "stray_no": n, "stray_line": i + 1, "char_offset_0based": s["char_offset"],
            "excess_closers": s["excess"], "line_text": window(ctx.lines[i], s["char_offset"], 100, 120),
            "parser_assigned_article": ctx.owner_label(i),
            "quote_region": f"L{rs + 1}–L{i + 1}" if rs is not None else "không có",
            "inner_headings": " | ".join(inner_info),
            "next_headings_top_level": "; ".join(f"L{h['line']} Điều {h['number']}{'' if h['consecutive_with_previous'] else ' (số không liền)'}" for h in after_h),
            "context": "\n".join(ctx_lines), "automated_evidence_level": level, "automated_reason": why,
            "parser_uses_quote_context": "không (có “ chưa đóng)" if ambiguous else "có", **human_blank(),
        })
    loss = boundary_loss(ctx)
    row.update({
        "compared_range": f"dòng 1–{len(ctx.lines)}; {len(ctx.parsed.articles)} Điều parse; {len(positions)} vị trí ” thừa: "
                          + ", ".join(f"L{p['stray_line']}" for p in positions),
        "source_evidence": "\n\n".join(f"[vị trí {p['stray_no']}] L{p['stray_line']} cột {p['char_offset_0based']}\n{p['context']}" for p in positions[:3])
                           + ("\n… (xem file vị trí chi tiết)" if len(positions) > 3 else ""),
        "parser_result": "; ".join(f"L{p['stray_line']} → {p['parser_assigned_article']}; vùng trích {p['quote_region']}" for p in positions[:4])
                         + f". Mất nội dung giữa các Điều: {loss['lost_lines']} dòng.",
        "issue": "; ".join(f"L{p['stray_line']}: {p['automated_reason']}" for p in positions[:3]),
        "possible_impact": "Nếu vùng trích dẫn bị xác định sai, Điều trích dẫn thành Điều độc lập hoặc Điều thật bị nuốt vào đoạn trích; "
                           "số Điều, dedup và tỷ lệ Điều của họ (luật B) có thể đổi.",
        "automated_proposal": "Đề xuất giữ nguyên parser." if worst == OK else "Người xem từng vị trí (README) và xác nhận ranh giới Điều; nếu sai, nêu dòng và lỗi để sửa parser.",
        "automated_evidence_level": worst, "n_stray_positions": len(positions), **human_blank(),
    })
    return row, positions


# ---------------------------------------------------------------- B: after_signature
def analyse_B(ctx: Ctx, groups: str) -> tuple[dict, list[dict]]:
    row = common_row(ctx, "B", groups)
    arts = ctx.parsed.articles
    main = [(k, a) for k, a in enumerate(arts) if not a.after_signature]
    segs = P.after_signature_segments(arts)
    idx_of = {id(a): k for k, a in enumerate(arts)}
    loss = boundary_loss(ctx)
    seg_rows, levels = [], []
    for n, seg in enumerate(segs, 1):
        first, ev = seg[0], seg[0].form_evidence
        lines_all = [x for a in seg for x in a.src_lines] + [a.heading_line for a in seg]
        lo, hi = min(lines_all), max(lines_all)
        removed = any(a.form_template for a in seg)
        uncertain = any(a.form_uncertain for a in seg)
        pre_lo = first.heading_line - len(first.preamble)
        strong = [(a.src_lines[j] + 1, l) for a in seg for j, l in enumerate(a.lines) if P.STRONG_BLANK_RE.search(l)][:3]
        decision = "Loại (form_template)" if removed else ("Giữ, gắn cờ form_uncertain" if uncertain else "Giữ")
        kept_lines = sum(len(a.lines) + 1 for a in seg)
        lead_text = " ⏎ ".join(short(x, 90) for x in first.preamble[-4:])
        title_hint = any(k in " ".join(first.preamble).lower() for k in ("quy chế", "quy chuẩn", "qcvn", "kèm theo", "quy định"))
        if removed:
            if ev.get("clear"):
                lvl, why = OK, "có lời dẫn quyết định mẫu và chỗ trống dài/ô (tên …); không dựa vào dấu ba chấm đơn lẻ"
            else:
                lvl, why = LOOK, "bị loại nhưng bằng chứng không thỏa quy tắc rõ ràng"
        else:
            if ev.get("any_blank"):
                lvl, why = LOOK, "giữ nhưng có dấu ba chấm; cần người xác nhận không phải biểu mẫu"
            elif title_hint and not ev.get("lead_in"):
                lvl, why = OK, "không có lời dẫn quyết định, không có chỗ trống; tên đoạn gợi ý quy chế/quy chuẩn kèm theo"
            elif not ev.get("lead_in"):
                lvl, why = LOOK, "giữ vì không có bằng chứng biểu mẫu nhưng tên đoạn không rõ là quy chế/quy chuẩn"
            else:
                lvl, why = LOOK, "có lời dẫn nhưng không có chỗ trống; cần người xem"
        levels.append(lvl)
        heads = ", ".join(f"Đ{a.number}" for a in seg[:12]) + ("…" if len(seg) > 12 else "")
        ctx_lines = ctx.fmt(pre_lo - 2, pre_lo + 6) + ["  …"] + ctx.fmt(hi - 2, hi + 1)
        seg_rows.append({
            "doc_id": ctx.doc_id, "segment_no": n, "articles": heads, "n_articles": len(seg),
            "line_range": f"tiêu đề đầu L{first.heading_line + 1}; nội dung tới L{hi + 1}; lời dẫn/tên đoạn bị bỏ L{pre_lo + 1}–L{first.heading_line}", "decision": decision,
            "evidence": json.dumps(ev, ensure_ascii=False), "lead_in_lines": lead_text,
            "blank_line_samples": " ⏎ ".join(f"L{ln}: {short(t, 100)}" for ln, t in strong),
            "context": "\n".join(ctx_lines), "automated_evidence_level": lvl, "automated_reason": why,
            "article_status": "; ".join(sorted({ctx.status[idx_of[id(a)]] for a in seg})), **human_blank(),
        })
    worst = max(levels, key=lambda x: RANK[x]) if levels else OK
    first_seg_line = min((r for r in [a.heading_line for s in segs for a in s]), default=len(ctx.lines))
    main_lo = min((a.heading_line for _, a in main), default=0)
    main_hi = max((max(a.src_lines) if a.src_lines else a.heading_line for _, a in main), default=0)
    trailer_at = next((i for i, o in enumerate(ctx.parsed.line_owner) if o == P.OWNER_TRAILER), None)
    ev_lines = ctx.fmt(main_hi - 2, main_hi + 1) if main else []
    if trailer_at is not None:
        ev_lines += ["  … (ranh giới chữ ký) …"] + ctx.fmt(trailer_at - 1, trailer_at + 3)
    row.update({
        "compared_range": f"phần chính: {len(main)} Điều, L{main_lo + 1}–L{main_hi + 1}; chữ ký/nơi nhận bắt đầu L{(trailer_at or 0) + 1}; "
                          f"{len(segs)} đoạn đính kèm (L{first_seg_line + 1}–L{len(ctx.lines)})",
        "source_evidence": "\n".join(ev_lines),
        "parser_result": f"Phần chính giữ {len(main)} Điều; mất nội dung giữa các Điều: {loss['lost_lines']} dòng. "
                         f"Dòng bị bỏ: {sum(1 for o in ctx.parsed.line_owner if o == P.OWNER_TRAILER)} dòng chữ ký/nơi nhận/lời dẫn "
                         f"(trong đó {sum(1 for i, o in enumerate(ctx.parsed.line_owner) if o == P.OWNER_TRAILER and trailer_at is not None and i < first_seg_line)} dòng nằm trước tiêu đề đầu tiên của phần đính kèm: tên/lời nói đầu của quy chế hay quy chuẩn), "
                         f"{sum(1 for o in ctx.parsed.line_owner if o == P.OWNER_CUT)} dòng phụ lục/biểu mẫu bị cắt"
                         + (" (Điều trong phần cắt: " + "; ".join(f"L{d['line'] + 1} Điều {d['number']} — {short(d['title'], 40)} [dấu hiệu cắt: {d['marker']}]" for d in ctx.parsed.dropped[:6]) + ")" if ctx.parsed.dropped else "")
                         + ". " + "; ".join(f"đoạn {r['segment_no']} ({r['n_articles']} Điều, {r['line_range']}): {r['decision']}" for r in seg_rows),
        "issue": "; ".join(f"đoạn {r['segment_no']}: {r['automated_reason']}" for r in seg_rows),
        "possible_impact": "Giữ nhầm biểu mẫu: thêm Điều không phải quy phạm vào corpus và dedup. Loại nhầm quy chế/quy chuẩn: mất nội dung pháp lý, đổi số Điều của họ (luật B). "
                           "Điều đính kèm được giữ mang tiền tố tên văn bản chính (tên quy chế/quy chuẩn nằm sau chữ ký bị bỏ), có thể làm truy hồi nhầm ngữ cảnh.",
        "automated_proposal": "Đề xuất giữ nguyên quyết định hiện tại." if worst == OK else "Người xem các đoạn gắn 'Cần người xem' (README).",
        "automated_evidence_level": worst, "n_segments": len(segs),
        "segments_kept": sum(1 for r in seg_rows if r["decision"].startswith("Giữ")),
        "segments_removed": sum(1 for r in seg_rows if r["decision"].startswith("Loại")), **human_blank(),
    })
    return row, seg_rows


# ---------------------------------------------------------------- xuất
DOC_COLS = ["doc_id", "title", "warning_groups", "source_path", "output_path", "compared_range", "source_evidence",
            "parser_result", "issue", "possible_impact", "automated_proposal", "automated_evidence_level"]


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def render_md(path: Path, title: str, intro: str, docs: list[dict], details: dict[str, list[dict]], detail_fields: list[tuple[str, str]]) -> None:
    out = [f"# {title}", "", intro, ""]
    out += ["| Văn bản | Nhóm | Mức bằng chứng tự động | Người duyệt | Kết quả | Ngày |", "|---|---|---|---|---|---|"]
    for r in docs:
        out.append(f"| `{r['doc_id']}` {short(r['title'], 60).replace('|', '/')} | {r['warning_groups']} | {r['automated_evidence_level']} | {r['reviewer_name'] or '—'} | {r['review_result']} | {r['review_date'] or '—'} |")
    for r in docs:
        out += ["", f"## `{r['doc_id']}` — {r['title']}", "",
                f"- **Nhóm cảnh báo:** {r['warning_groups']}", f"- **Nguồn:** {r['source_path']}", f"- **Output parser:** {r['output_path']}",
                f"- **Phần đã đối chiếu:** {r['compared_range']}", f"- **Kết quả parser:** {r['parser_result']}",
                f"- **Vấn đề:** {r['issue']}", f"- **Ảnh hưởng có thể có:** {r['possible_impact']}", f"- **Đề xuất tự động:** {r['automated_proposal']}",
                f"- **Mức bằng chứng tự động:** {r['automated_evidence_level']}",
                f"- **Người xác nhận / ngày / kết quả / ghi chú:** {r['reviewer_name'] or '(trống)'} / {r['review_date'] or '(trống)'} / {r['review_result']} / {r['review_note'] or '(trống)'}",
                "", "Bằng chứng nguồn (`▶` = tiêu đề Điều parser nhận; `[Đn]` = Điều parser gán, `*` = sau chữ ký):", "", "```text", r["source_evidence"], "```"]
        for d in details.get(r["doc_id"], []):
            out += ["", "- " + " · ".join(f"**{lab}:** {d[k]}" for k, lab in detail_fields if d.get(k) not in (None, ""))]
            if d.get("context"):
                out += ["", "```text", d["context"], "```"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    global CONFIRMATION
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--work-dir", default=".scratch/task_1_review", help="nơi ghi mọi output (local)")
    ap.add_argument("--publish", action="store_true",
                    help="ghi README và CSV A/B/C còn thiếu vào review/; không ghi đè CSV đã có")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    proc, review_dir = Path(cfg["processed"]["dir"]), Path(cfg["processed"]["after_filter_dir"]) / "review"
    outdir = Path(args.work_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    conf_path = review_dir / "confirmation.json"
    if conf_path.exists():
        CONFIRMATION = json.loads(conf_path.read_text(encoding="utf-8"))
        missing = [k for k in ("reviewer", "date", "result", "note", "entered_by") if not CONFIRMATION.get(k)]
        if missing:
            raise SystemExit(f"confirmation.json thiếu {missing}")
    cache = proc / "review_cache"
    cache.mkdir(parents=True, exist_ok=True)

    docs_index = {d["doc_id"]: d for d in read_jsonl(proc / "docs_index.jsonl")}
    index_ids = {a["article_id"] for a in read_jsonl(proc / "articles_index.jsonl")}
    pipeline_arts = defaultdict(list)
    for a in read_jsonl(proc / "articles.jsonl"):
        pipeline_arts[a["doc_id"]].append(a)
    rejected = {r["article_id"]: r["reason"] for r in read_jsonl(Path(cfg["processed"]["rejected_log"])) if r.get("article_id")}

    ctxs: dict[str, Ctx] = {}
    raws: dict[str, str] = {}
    pf = pq.ParquetFile(Path(cfg["paths"]["raw_dir"]) / cfg["dataset"]["files"]["content"])
    for batch in pf.iter_batches(batch_size=500, columns=["id", "content_html"]):
        for doc_id, html in zip(batch.column("id").to_pylist(), batch.column("content_html").to_pylist()):
            if doc_id in docs_index:
                ctxs[doc_id] = Ctx(doc_id, docs_index[doc_id]["title"], html_to_lines(html), index_ids, rejected)
                raws[doc_id] = html

    # nhất quán với output pipeline
    mismatch = []
    for doc_id, c in ctxs.items():
        parsed_ok = [(a.number, a.body) for a in c.parsed.articles if P.article_reject_reason(a) is None]
        out_ok = [(a["number"], a["body"]) for a in pipeline_arts[doc_id]]
        if parsed_ok != out_ok:
            mismatch.append(doc_id)

    A = {d for d, c in ctxs.items() if c.parsed.stats["ambiguous_quote"]}
    B = {d for d, c in ctxs.items() if any(a.after_signature for a in c.parsed.articles)}
    C = {d for d, c in ctxs.items() if c.parsed.stats["quote_stray_closers"]}
    straight = {d for d, c in ctxs.items() if c.parsed.stats["straight_quote_article"]}

    def groups_of(d: str) -> str:
        return "+".join(n for n, s in (("A", A), ("B", B), ("C", C)) if d in s)

    rowsA, detA, rowsB, detB, rowsC, detC = [], [], [], [], [], []
    for d in sorted(A):
        r, dt = analyse_A(ctxs[d], groups_of(d)); rowsA.append(r); detA += dt
    for d in sorted(B):
        r, dt = analyse_B(ctxs[d], groups_of(d)); rowsB.append(r); detB += dt
    for d in sorted(C):
        r, dt = analyse_C(ctxs[d], groups_of(d)); rowsC.append(r); detC += dt
    for d in A | B | C:
        (cache / f"{d}.html").write_text(raws[d], encoding="utf-8")

    n_ok = lambda rows: sum(1 for r in rows if CONFIRMATION and r["review_result"] == CONFIRMATION["result"])
    summ = f"A: {n_ok(rowsA)}/{len(rowsA)}, B: {n_ok(rowsB)}/{len(rowsB)}, C: {n_ok(rowsC)}/{len(rowsC)}" if CONFIRMATION else ""
    for rows in (rowsA, rowsB, rowsC):
        for r in rows:
            r["table_summary"] = summ
    if CONFIRMATION:
        with open(outdir / "confirmation_summary.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["table", "confirmed", "total", "reviewer", "date", "result", "entered_by"])
            for nm, rows in (("A", rowsA), ("B", rowsB), ("C", rowsC)):
                w.writerow([nm, n_ok(rows), len(rows), CONFIRMATION["reviewer"], CONFIRMATION["date"], CONFIRMATION["result"], CONFIRMATION["entered_by"]])
    extraA = ["opener_line", "opener_category", "headings_after_count", "table_summary"]
    extraB = ["n_segments", "segments_kept", "segments_removed", "table_summary"]
    extraC = ["n_stray_positions", "table_summary"]
    write_csv(outdir / "table_A_unclosed_open_quote.csv", rowsA, DOC_COLS + extraA + HUMAN_COLS)
    write_csv(outdir / "table_A_headings_after_opener.csv", detA, ["doc_id", "opener_line", "line", "number", "title", "article_id", "consecutive_with_previous", "previous_line"])
    write_csv(outdir / "table_B_after_signature.csv", rowsB, DOC_COLS + extraB + HUMAN_COLS)
    segcols = ["doc_id", "segment_no", "articles", "n_articles", "line_range", "decision", "evidence", "lead_in_lines", "blank_line_samples", "article_status", "context", "automated_evidence_level", "automated_reason"] + HUMAN_COLS
    write_csv(outdir / "table_B_segments.csv", detB, segcols)
    write_csv(outdir / "table_C_stray_closing_quote.csv", rowsC, DOC_COLS + extraC + HUMAN_COLS)
    poscols = ["doc_id", "stray_no", "stray_line", "char_offset_0based", "excess_closers", "line_text", "parser_assigned_article", "quote_region",
               "inner_headings", "next_headings_top_level", "parser_uses_quote_context", "context", "automated_evidence_level", "automated_reason"] + HUMAN_COLS
    write_csv(outdir / "table_C_stray_positions.csv", detC, poscols)

    byd = lambda rows: defaultdict(list, {k: [x for x in rows if x["doc_id"] == k] for k in {x["doc_id"] for x in rows}})
    conv = ("Quy ước: số dòng = dòng văn bản đã chuẩn hóa (`html_to_lines`), đánh số từ 1; mở nguồn bằng `scripts/show_source.py` (xem README). "
            "Script chuẩn bị tự động bằng chứng và đề xuất; kết luận do người duyệt.")
    if CONFIRMATION:
        conv += (f"\n\n**Tổng kết xác nhận: {summ}.** Người duyệt: {CONFIRMATION['reviewer']}; ngày: {CONFIRMATION['date']}; "
                 f"kết quả: {CONFIRMATION['result']}. {CONFIRMATION['entered_by']}.")
    else:
        conv += " Cột người duyệt để trống / \"Chờ xác nhận\"."
    render_md(outdir / "table_A_unclosed_open_quote.md", f"Bảng A — văn bản có “ chưa đóng còn trong index ({len(rowsA)})", conv, rowsA, byd(detA),
              [("line", "Dòng"), ("number", "Điều"), ("title", "Tiêu đề"), ("consecutive_with_previous", "Số liền sau Điều trước"), ("previous_line", "Dòng ngay trước")])
    render_md(outdir / "table_B_after_signature.md", f"Bảng B — văn bản có phần sau chữ ký (after_signature) còn trong index ({len(rowsB)})", conv, rowsB, byd(detB),
              [("segment_no", "Đoạn"), ("articles", "Điều"), ("line_range", "Dòng"), ("decision", "Quyết định"), ("evidence", "Bằng chứng biểu mẫu"),
               ("blank_line_samples", "Dòng chỗ trống dài"), ("article_status", "Trạng thái Điều"), ("automated_evidence_level", "Mức bằng chứng"), ("automated_reason", "Lý do")])
    render_md(outdir / "table_C_stray_closing_quote.md", f"Bảng C — văn bản có ” thừa còn trong index ({len(rowsC)})", conv, rowsC, byd(detC),
              [("stray_no", "Vị trí"), ("stray_line", "Dòng"), ("char_offset_0based", "Cột"), ("parser_assigned_article", "Điều parser gán"),
               ("quote_region", "Vùng trích"), ("inner_headings", "Tiêu đề trong vùng"), ("automated_evidence_level", "Mức bằng chứng"), ("automated_reason", "Lý do")])

    scan = [r for c in ctxs.values() for r in region_scan(c)]
    write_csv(outdir / "global_quote_region_scan.csv", scan,
              ["doc_id", "region", "heading_line", "heading_number", "previous_top_level_number", "possible_real_article", "heading_text", "context"])
    sets = {"A": A, "B": B, "C": C}
    pair = lambda x, y: sorted(sets[x] & sets[y])
    overlap = {
        "sizes": {k: len(v) for k, v in sets.items()}, "union_unique_docs": len(A | B | C), "sum_of_three_groups": len(A) + len(B) + len(C),
        "A_and_B": pair("A", "B"), "A_and_C": pair("A", "C"), "B_and_C": pair("B", "C"), "A_and_B_and_C": sorted(A & B & C),
        "only_A": sorted(A - B - C), "only_B": sorted(B - A - C), "only_C": sorted(C - A - B),
        "straight_quote_docs_in_index_not_in_tables": len(straight), "pipeline_vs_review_parse_mismatch_docs": mismatch,
        "docs_in_index": len(docs_index),
        "global_region_scan": {"quoted_headings": len(scan), "docs": len({r["doc_id"] for r in scan}),
                               "possible_real_article": sum(1 for r in scan if r["possible_real_article"]),
                               "possible_real_article_docs": sorted({r["doc_id"] for r in scan if r["possible_real_article"]})},
        "evidence_levels": {n: dict(Counter(r["automated_evidence_level"] for r in rows)) for n, rows in (("A", rowsA), ("B", rowsB), ("C", rowsC))},
    }
    (outdir / "group_overlap.json").write_text(json.dumps(overlap, ensure_ascii=False, indent=1), encoding="utf-8")
    def lst(rows: list[dict]) -> str:
        return "\n".join(f"  - `{r['doc_id']}` — {short(r['title'], 70)} — **{r['automated_evidence_level']}** — nhóm {r['warning_groups']}" for r in rows)

    needs = {n: [r for r in rows if r["automated_evidence_level"] != OK] for n, rows in (("A", rowsA), ("B", rowsB), ("C", rowsC))}
    if CONFIRMATION:
        status_line = (f"**Trạng thái xác nhận:** {summ}. Người duyệt: {CONFIRMATION['reviewer']}; ngày: {CONFIRMATION['date']}; "
                       f"kết quả: {CONFIRMATION['result']}. {CONFIRMATION['entered_by']}. Xem `confirmation.json`.")
        section3 = (f"## 3. Kết quả xác nhận\n\nMọi ca trong ba bảng ghi: "
                    f"người duyệt `{CONFIRMATION['reviewer']}`, ngày `{CONFIRMATION['date']}`, kết quả `{CONFIRMATION['result']}` — chỉ áp dụng cho phần đã đối chiếu "
                    f"(cột `compared_range`). Tổng kết: {summ}. Bản ghi nhập theo xác nhận của người duyệt. "
                    f"Mức bằng chứng tự động (cột `automated_evidence_level`) là phần chuẩn bị, không thay cho kết quả của người duyệt.")
        closing = f"Toàn bộ {len(A | B | C)} văn bản duy nhất: {summ}."
    else:
        status_line = (f'Mọi cột người duyệt (`reviewer_name`, `review_date`, `review_result`, `review_note`) để trống hoặc "{PENDING}".\n'
                       "Mặc định giải quyết các ca còn chờ **trước khi chạy split**.")
        section3 = ("## 3. Cách điền kết quả (người duyệt)\n\n`review_result` chọn một trong:\n"
                    "- **Đã xác nhận** — chỉ áp dụng cho phần đã đối chiếu (cột `compared_range`).\n"
                    "- **Cần sửa** — ghi vị trí (số dòng) và lỗi trong `review_note`.\n- **Chưa đủ bằng chứng** — ghi cần xem thêm gì.\n\n"
                    "Điền thêm `reviewer_name`, `review_date`. Kết quả tự động (\"Đủ bằng chứng tự động\") **không** đổi trạng thái người duyệt.")
        closing = f'Toàn bộ {len(A | B | C)} văn bản duy nhất đều **{PENDING}** (kể cả ca script tự động báo "Đủ bằng chứng").'
    readme = f"""# Hướng dẫn đối chiếu ba bảng cảnh báo (đọc trước)

Tạo bởi `scripts/build_review_tables.py` từ output hiện tại. **Script chuẩn bị tự động bằng chứng và đề xuất; không phải người đã xem.**
{status_line}

## 0. Tệp được commit và cách sinh lại

Thư mục `reports/data_stats/after_filter/review/` chỉ gồm: `README.md`, `confirmation.json` và ba bảng mức văn bản `table_A_unclosed_open_quote.csv`, `table_B_after_signature.csv`, `table_C_stray_closing_quote.csv` (đã được người duyệt). Bảng C là bảng mức văn bản, không chứa chi tiết từng vị trí.
Bảng chi tiết (từng vị trí/đoạn), bản Markdown và bảng phụ trợ không commit; sinh lại vào `.scratch/task_1_review/` bằng:

```bash
python -X utf8 scripts/build_review_tables.py --config configs/data.yaml
```

Script chỉ đọc `confirmation.json`. Với `--publish`, script ghi lại README này và chỉ ghi CSV A/B/C nào còn thiếu; không ghi đè CSV đã duyệt hay `confirmation.json`.

## 1. Ba nhóm (xác định lại từ output, parse lại HTML gốc của {len(docs_index)} văn bản trong index)

| Nhóm | Điều kiện | Số văn bản | Bảng |
|---|---|---|---|
| A | có “ chưa đóng (parser **không** dùng ngữ cảnh đoạn trích) | {len(A)} | `table_A_unclosed_open_quote.csv` |
| B | có Điều/phần sau chữ ký (`after_signature`) | {len(B)} | `table_B_after_signature.csv` |
| C | có ” thừa (parser vẫn dùng ngữ cảnh đoạn trích) | {len(C)} | `table_C_stray_closing_quote.csv` ({len(detC)} vị trí) |

Giao nhau: A∩B = {len(A & B)}, A∩C = {len(A & C)} ({", ".join(f"`{d}`" for d in sorted(A & C)) or "—"}), B∩C = {len(B & C)}, A∩B∩C = {len(A & B & C)}.
Tổng ba nhóm = {len(A) + len(B) + len(C)}, **số văn bản duy nhất = {len(A | B | C)}** (không cộng trùng).
Lưu ý: số nhóm C là {len(C)}, khác con số 14 trong báo cáo trước; 14 được suy ra từ `parse_anomalies.jsonl`, chỉ ghi văn bản có thêm cờ khác, nên bỏ sót văn bản chỉ có ” thừa. `prepare_data.py` nay ghi cả cờ này. Nhóm ngoặc thẳng ({len(straight)} văn bản) không nằm trong ba bảng.

## 2. Quy ước số dòng và cách mở nguồn

- Số dòng = dòng **văn bản đã chuẩn hóa** do `html_to_lines` trả về (HTML → text, NFC, bảng thành `ô | ô`), đánh số từ **1**. Nhãn: `[Đn]` = Điều parser gán (`*` = sau chữ ký), `[đầu]` = trước Điều đầu tiên, `[chương]` = dòng Chương/Mục bị bỏ, `[ký]` = chữ ký/nơi nhận/lời dẫn sau chữ ký bị bỏ, `[cắt]` = phụ lục/biểu mẫu bị cắt; `▶` = tiêu đề Điều parser nhận.
- HTML gốc: `{CONTENT_PARQUET}`, cột `id` = `doc_id`, cột `content_html`; bản trích để mở nhanh: `data/processed/review_cache/<doc_id>.html` (không commit).
- Xem dòng a–b kèm đoạn HTML gốc tương ứng:

```bash
python -X utf8 scripts/show_source.py --doc <doc_id> --lines 36-48 --html
```

- Liệt kê Điều parser nhận (số dòng, trạng thái) và xem nội dung Điều trong output:

```bash
python -X utf8 scripts/show_source.py --doc <doc_id> --articles
python -X utf8 scripts/show_source.py --doc <doc_id> --article-id <doc_id>_005
```

- Output parser: `data/processed/articles_index.jsonl` (sau loại trùng), `articles.jsonl` (trước loại trùng), `chunks_index.jsonl`; log loại bỏ: `logs/rejected.jsonl`; cờ: `logs/parse_anomalies.jsonl`. `article_id` = `<doc_id>_<thứ tự Điều parse, 3 chữ số>`.

{section3}

## 4. Ca cần chú ý (mức tự động khác "Đủ bằng chứng")

- Bảng A ({len(needs['A'])}/{len(rowsA)}):
{lst(needs['A']) or '  - (không có)'}
- Bảng B ({len(needs['B'])}/{len(rowsB)}):
{lst(needs['B']) or '  - (không có)'}
- Bảng C ({len(needs['C'])}/{len(rowsC)}):
{lst(needs['C']) or '  - (không có)'}

{closing}

## 5. Quét vùng trích dẫn toàn cục

Trong {len(docs_index)} văn bản, parser dùng ngữ cảnh đoạn trích cho các văn bản có ngoặc cân bằng. Có {len(scan)} tiêu đề Điều nằm trong vùng trích dẫn (ở {len({r['doc_id'] for r in scan})} văn bản); {sum(1 for r in scan if r['possible_real_article'])} tiêu đề có số bằng Điều top-level liền trước + 1 (nguy cơ Điều thật bị nuốt). Bảng chi tiết sinh lại local (mục 0).
"""
    (outdir / "README.md").write_text(readme, encoding="utf-8")
    if args.publish:
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "README.md").write_text(readme, encoding="utf-8")
        for name in PUBLISHED_CSVS:
            dst = review_dir / name
            if dst.exists():
                print(f"giữ nguyên {dst} (đã có; không ghi đè bảng đã duyệt)")
            else:
                dst.write_bytes((outdir / name).read_bytes())
    print(json.dumps({k: v for k, v in overlap.items() if not k.startswith(("only", "A_and", "B_and"))}, ensure_ascii=False))
    print({k: (len(v) if isinstance(v, list) else v) for k, v in overlap.items() if k.startswith(("only", "A_and", "B_and"))})


if __name__ == "__main__":
    main()
