"""Test cho scripts/build_review_tables.py và scripts/show_source.py (dữ liệu giả, không đọc dữ liệu thật)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


brt = _load("build_review_tables")


def ctx(lines, doc="D1"):
    return brt.Ctx(doc, "Tên văn bản giả", lines, set(), {})


def test_quote_scan_records_stray_closer_position():
    qs = brt.quote_scan(["Điều 1. A", "“Điều 5. X", "nd”", "thừa ”", "Điều 2. B"])
    assert [s["line"] for s in qs["strays"]] == [3] and qs["final_depth"] == 0
    assert qs["strays"][0]["char_offset"] == 5 and qs["strays"][0]["region_start"] is None


def test_table_c_names_every_stray_position_and_assigned_article():
    lines = ["Điều 1. Phạm vi", "nội dung", "câu có dấu đóng thừa ”", "Điều 2. Hiệu lực", "hết ”"]
    row, pos = brt.analyse_C(ctx(lines), "C")
    assert [p["stray_line"] for p in pos] == [3, 5]
    assert "Điều 1" in pos[0]["parser_assigned_article"] and "Điều 2" in pos[1]["parser_assigned_article"]
    assert row["n_stray_positions"] == 2 and "L3" in row["compared_range"] and "L5" in row["compared_range"]
    assert all(p["context"] and "⌖" in p["context"] for p in pos)


def test_table_c_flags_quoted_heading_that_could_be_a_real_article():
    # tiêu đề "Điều 2" có số = Điều 1 + 1 nằm trong vùng trích: không được kết luận đúng chỉ vì số liên tục
    lines = ["Điều 1. A", "“Điều 5. X", "Điều 2. B", "nd” ”"]
    row, pos = brt.analyse_C(ctx(lines), "C")
    assert pos[0]["automated_evidence_level"] == brt.LOOK
    assert "Điều thật" in pos[0]["automated_reason"] and "L3" in pos[0]["inner_headings"]
    assert row["automated_evidence_level"] == brt.LOOK


def test_table_a_unclosed_quote_paragraph_with_following_articles_needs_human():
    lines = ["Điều 1. A", "“Điều 5. đoạn trích không đóng", "Điều 2. B", "nội dung"]
    row, detail = brt.analyse_A(ctx(lines), "A")
    assert row["opener_line"] == 2 and row["automated_evidence_level"] == brt.LOOK
    assert detail and detail[0]["number"] == "2" and detail[0]["consecutive_with_previous"] is True
    assert "Điều 2" in row["parser_result"] and "L2" in row["compared_range"]


def test_table_a_term_closed_by_straight_quote_is_sufficient_but_still_pending():
    lines = ["Điều 1. A", "1. Trong đó “hợp đồng sòng phẳng\" là hợp đồng giao dịch.", "Điều 2. B", "nd"]
    row, _ = brt.analyse_A(ctx(lines), "A")
    assert row["automated_evidence_level"] == brt.OK
    assert row["review_result"] == brt.PENDING and row["reviewer_name"] == "" and row["review_date"] == ""


def test_table_a_without_following_article_is_sufficient():
    row, detail = brt.analyse_A(ctx(["Điều 1. A", "nd", "Mẫu: Số /…… “Vv cấp"]), "A")
    assert row["automated_evidence_level"] == brt.OK and detail == []


def test_table_b_kept_quy_che_and_removed_form_are_both_reported():
    lines = ["Điều 1. Ban hành", "nd", "Nơi nhận:", "- Như trên;", "Quy chế làm việc", "Điều 1. Phạm vi", "Quy chế này quy định.",
             "Điều 2. Thi hành", "x", "Căn cứ Luật X;", "QUYẾT ĐỊNH:", "Điều 1. Phê duyệt", "Họ tên ……………",
             "Điều 2. Thi hành", "Có hiệu lực."]
    row, segs = brt.analyse_B(ctx(lines), "B")
    assert [s["decision"] for s in segs] == ["Giữ", "Loại (form_template)"]
    assert segs[0]["automated_evidence_level"] == brt.OK and "tên đoạn gợi ý quy chế" in segs[0]["automated_reason"]
    assert row["n_segments"] == 2 and row["segments_kept"] == 1 and row["segments_removed"] == 1
    assert "…" in segs[1]["blank_line_samples"] and segs[1]["context"]


def test_table_b_ordinary_ellipsis_is_never_treated_as_form_evidence():
    lines = ["Điều 1. A", "nd", "Nơi nhận:", "- Như trên;", "Quy chế", "Điều 1. Phạm vi", "Chi gồm: ... theo quy định.", "Điều 2. B", "x"]
    row, segs = brt.analyse_B(ctx(lines), "B")
    assert segs[0]["decision"] == "Giữ, gắn cờ form_uncertain" and segs[0]["automated_evidence_level"] == brt.LOOK


def test_no_row_is_ever_preconfirmed_by_automation():
    for lines, fn in ((["Điều 1. A", "x ”"], brt.analyse_C), (["Điều 1. A", "“q", "Điều 2. B"], brt.analyse_A),
                      (["Điều 1. A", "Nơi nhận:", "Điều 1. B", "y"], brt.analyse_B)):
        row, _ = fn(ctx(lines), "X")
        assert row["review_result"] == brt.PENDING and not row["reviewer_name"] and not row["review_date"]
        assert "Đã xác nhận" not in str(row["review_result"])


def test_window_shows_quote_even_for_long_lines():
    line = "a" * 300 + "“Hợp đồng\" b" + "c" * 300
    w = brt.window(line, 300)
    assert "“Hợp đồng\"" in w and w.startswith("…") and w.endswith("…")


def test_show_source_html_trace_finds_line_in_raw_html():
    show = _load("show_source")
    raw = "<p>Điều 1. <b>Phạm vi</b></p><p>“Hợp đồng sòng phẳng\" là hợp đồng</p>"
    assert "vị trí ký tự" in show.html_trace(raw, "“Hợp đồng sòng phẳng\" là hợp đồng")
    assert "không tìm thấy" in show.html_trace(raw, "Dòng hoàn toàn không có trong HTML")
