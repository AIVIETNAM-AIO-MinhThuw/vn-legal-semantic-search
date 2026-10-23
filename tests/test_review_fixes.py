"""Test tái hiện/bảo vệ 6 phát hiện của code review (parse viết hoa, đoạn trích, bảng, validate, dedup, log lọc)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.html_text import html_to_lines  # noqa: E402
from src.data.parse import article_reject_reason, parse_articles  # noqa: E402


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- 1. nội dung viết hoa không bị coi là chữ ký ----
def test_caps_content_is_preserved_in_last_article():
    p = parse_articles(["Điều 1. Mức thu", "MỨC THU PHÍ"])
    a = p.articles[0]
    assert a.lines == ["MỨC THU PHÍ"] and article_reject_reason(a) is None


def test_caps_content_mid_article_preserved():
    p = parse_articles(["Điều 3. Quy định", "THU PHÍ NHƯ SAU", "1. Mức A", "Điều 4. Khác", "nd"])
    assert p.articles[0].lines == ["THU PHÍ NHƯ SAU", "1. Mức A"]


def test_real_signature_blocks_are_still_cut():
    p = parse_articles(["Điều 1. X", "Nội dung.", "CHỦ TỊCH QUỐC HỘI", "(Đã ký)", "Nguyễn Văn A"])
    assert p.articles[0].lines == ["Nội dung."]
    p = parse_articles(["Điều 1. X", "Nội dung.", "Nơi nhận:", "- Như trên;"])
    assert p.articles[0].lines == ["Nội dung."]


# ---- 2. đoạn trích nhiều Điều ----
def test_multi_article_quote_is_kept_inside_source_article():
    lines = ["Điều 1. Sửa đổi", "Sửa đổi, bổ sung như sau:", "“Điều 5. A", "nội dung 5", "Điều 6. B", "nội dung 6”",
             "Điều 2. Hiệu lực", "nội dung 2"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1", "2"]
    assert "Điều 6. B" in p.articles[0].lines and "nội dung 6”" in p.articles[0].lines
    assert p.stats["ambiguous_quote"] == 0


def test_section_line_inside_quote_is_content():
    lines = ["Điều 1. Sửa đổi", "“Điều 5. A", "Chương II", "nội dung”", "Điều 2. B", "x"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1", "2"] and "Chương II" in p.articles[0].lines


def test_unbalanced_quote_is_reported_not_guessed():
    lines = ["Điều 1. Sửa đổi", "“Điều 5. A chưa đóng", "nội dung", "Điều 2. B", "x"]
    p = parse_articles(lines)
    assert p.stats["ambiguous_quote"] == 1
    assert [a.number for a in p.articles] == ["1", "2"]  # không nuốt cả văn bản; cấu trúc cũ + cờ mơ hồ


# ---- 3. bảng ----
def test_table_keeps_empty_cell_positions():
    h = "<table><tr><td>A</td><td></td><td>C</td></tr></table>"
    assert html_to_lines(h) == ["A | | C"]


def test_table_cell_with_line_breaks_stays_one_row():
    h = "<table><tr><td>Dòng 1\n  Dòng 2<br>Dòng 3</td><td>B</td></tr><tr><td>X</td><td>Y</td></tr></table>"
    assert html_to_lines(h) == ["Dòng 1 Dòng 2 Dòng 3 | B", "X | Y"]


def test_all_empty_row_skipped():
    assert html_to_lines("<table><tr><td></td><td> </td></tr><tr><td>1</td></tr></table>") == ["1"]


# ---- 4/5. validate_data ----
def _write_jsonl(p: Path, rows) -> None:
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _mini_env(tmp_path: Path, *, wrong_n_tokens: bool = False):
    cfg = yaml.safe_load(open(ROOT / "configs" / "data.yaml", encoding="utf-8"))
    if not (ROOT / cfg["tokenizer"]["local_dir"] / "tokenizer.json").exists():
        pytest.skip("thiếu tokenizer E5")
    cfg["tokenizer"]["local_dir"] = str(ROOT / cfg["tokenizer"]["local_dir"])
    raw, proc, out, logs = tmp_path / "raw", tmp_path / "proc", tmp_path / "out", tmp_path / "logs"
    for d in (raw / "data", proc, out, logs):
        d.mkdir(parents=True)
    cfg["paths"]["raw_dir"] = str(raw)
    cfg["processed"].update(dir=str(proc), after_filter_dir=str(out), filter_counts_log=str(logs / "fc.json"))
    pd.DataFrame({"id": ["1", "2"], "co_quan_ban_hanh": ["Bộ Tài chính", None]}).to_parquet(
        raw / "data" / "metadata.parquet")
    labels = list(cfg["relations"]["mapping"])  # mọi nhãn đã ánh xạ phải xuất hiện trong dữ liệu
    pd.DataFrame({"doc_id": ["1"] * len(labels), "other_doc_id": ["2"] * len(labels),
                  "relationship": labels}).to_parquet(raw / "data" / "relationships.parquet")
    (logs / "fc.json").write_text(json.dumps({"steps": [], "articles_rejected": {}, "parse_stats": {}}), encoding="utf-8")
    body = "Nội dung giống nhau."
    docs = [{"doc_id": "1", "title": "A", "co_quan_ban_hanh": "Bộ Tài chính", "n_articles": 2, "has_duplicate_article_numbers": False, "linh_vuc": "x",
             "loai_van_ban": "Luật", "tinh_trang_hieu_luc": "Còn hiệu lực", "year": 2020},
            {"doc_id": "2", "title": "B", "co_quan_ban_hanh": None, "n_articles": 1, "has_duplicate_article_numbers": False, "linh_vuc": "x",
             "loai_van_ban": "Luật", "tinh_trang_hieu_luc": "Còn hiệu lực", "year": 2020}]
    arts = [{"article_id": "1_001", "doc_id": "1", "number": "1", "title": "t", "body": body, "n_chunks": 1},
            {"article_id": "1_002", "doc_id": "1", "number": "2", "title": "t", "body": "Khác nhau", "n_chunks": 1},
            {"article_id": "2_001", "doc_id": "2", "number": "1", "title": "t", "body": body, "n_chunks": 1}]
    from src.data.tokenizer import count_tokens, load_tokenizer
    tok = load_tokenizer(cfg)
    chunks = []
    for a in arts:
        text = f"Tên › Điều {a['number']}. t › {a['body']}"
        n = count_tokens(tok, text)
        chunks.append({"chunk_id": a["article_id"] + "#00", "article_id": a["article_id"], "doc_id": a["doc_id"],
                       "chunk_index": 0, "n_chunks": 1, "kind": "whole",
                       "n_tokens": n + 5 if wrong_n_tokens else n, "text": text})
    _write_jsonl(proc / "docs.jsonl", docs)
    _write_jsonl(proc / "articles.jsonl", arts)
    _write_jsonl(proc / "chunks.jsonl", chunks)
    return cfg, proc, out


def test_validate_failure_writes_no_index_and_keeps_previous(tmp_path):
    v = _load_script("validate_data")
    cfg, proc, out = _mini_env(tmp_path, wrong_n_tokens=True)
    for name in ("docs_index", "articles_index", "chunks_index"):  # kết quả hợp lệ từ lần chạy trước
        (proc / f"{name}.jsonl").write_text("PREVIOUS_VALID\n", encoding="utf-8")
    info = v.validate(cfg)
    assert info["errors"]
    for name in ("docs_index", "articles_index", "chunks_index"):
        assert (proc / f"{name}.jsonl").read_text(encoding="utf-8") == "PREVIOUS_VALID\n"
    assert (out / "validate_report_failed.json").exists()
    assert not (out / "validate_report.json").exists()


def test_validate_success_recomputes_n_articles_after_dedup(tmp_path):
    v = _load_script("validate_data")
    cfg, proc, out = _mini_env(tmp_path)
    info = v.validate(cfg)
    assert info["errors"] == []
    docs = {d["doc_id"]: d for d in map(json.loads, (proc / "docs_index.jsonl").read_text(encoding="utf-8").splitlines())}
    arts = [json.loads(l) for l in (proc / "articles_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [a["article_id"] for a in arts] == ["1_001", "1_002"]  # 2_001 trùng 1_001 -> bị loại
    assert "2" not in docs  # văn bản 2 mất hết Điều
    assert docs["1"]["n_articles"] == 2 and docs["1"]["n_articles_before_dedup"] == 2
    assert (out / "validate_report.json").exists()


def test_validate_detects_stale_n_articles(tmp_path):
    v = _load_script("validate_data")
    cfg, proc, out = _mini_env(tmp_path)
    assert v.check_doc_article_counts([{"doc_id": "1", "n_articles": 24}], [{"doc_id": "1"}, {"doc_id": "1"}])
    assert not v.check_doc_article_counts([{"doc_id": "1", "n_articles": 2}], [{"doc_id": "1"}, {"doc_id": "1"}])


# ---- 6. log từng văn bản bị loại ở các bước lọc đầu ----
def test_filter_step_log_one_line_per_removed_doc():
    prep = _load_script("prepare_data")
    meta = pd.DataFrame({
        "id": ["1", "2", "3", "4"],
        "loai_van_ban": ["Luật", "Quyết định", "Luật", "Luật"],
        "tinh_trang_hieu_luc": ["Còn hiệu lực", "Còn hiệu lực", "Hết hiệu lực toàn bộ", "Còn hiệu lực"],
        "linh_vuc": ["D1", "D1", "D1", None],
    })
    flt = {"doc_types": ["Luật"], "effective_statuses": ["Còn hiệu lực"], "domains": ["D1"]}
    kept, steps, removed = prep.apply_filters(meta, flt)
    assert list(kept["id"]) == ["1"]
    assert sorted((r["doc_id"], r["step"]) for r in removed) == [("2", "1_doc_type"), ("3", "2_effect_status"),
                                                                  ("4", "3_domain_exact")]
    assert all(r["reason"] for r in removed)
    for s in steps[1:]:
        assert s["docs_before"] - s["docs_after"] == sum(1 for r in removed if r["step"] == s["step"])


# ---- phần đính kèm: sau khối "Nơi nhận" và các mẫu biểu không thành Điều độc lập ----
def test_text_after_signature_is_cut_and_following_articles_are_flagged_not_dropped():
    lines = ["Điều 1. Ban hành", "Nội dung 1.", "Điều 2. Hiệu lực", "Nội dung 2.", "Nơi nhận:", "- Như trên;",
             "QCVN 01:2024", "Chương I", "Điều 1. Phạm vi điều chỉnh", "Quy định của quy chuẩn."]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1", "2", "1"]
    assert p.articles[1].lines == ["Nội dung 2."]  # nơi nhận / tên quy chuẩn không lẫn vào Điều 2
    assert [a.after_signature for a in p.articles] == [False, False, True]
    assert p.stats["trailer_lines"] == 3 and p.stats["articles_after_signature"] == 1


def test_form_templates_marked_by_mau_so_are_cut():
    lines = ["Điều 1. A", "nội dung", "Mẫu số: 01/QĐ", "QUYẾT ĐỊNH", "Điều 1: Duyệt dự toán", "Điều 2: Thi hành"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1"] and p.stats["appendix_cut"]


def test_quoted_nơi_nhận_is_not_a_trailer():
    lines = ["Điều 1. Sửa đổi", "“Điều 5. A", "Nơi nhận: ví dụ trong đoạn trích”", "Điều 2. B", "x"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1", "2"]


# ---- nhãn hiển thị Điều trùng số ----
def test_display_label_number_and_title_with_identifier_only_when_still_duplicated():
    from src.data.labels import make_display_labels
    arts = [{"article_id": "d_001", "number": "2", "title": "Sửa đổi Mục II"},
            {"article_id": "d_002", "number": "2", "title": "Hiệu lực thi hành"},
            {"article_id": "d_003", "number": "3", "title": ""},
            {"article_id": "d_004", "number": "1", "title": "Phạm vi"},
            {"article_id": "d_005", "number": "1", "title": "Phạm vi"}]
    lab = make_display_labels(arts)
    assert lab["d_001"] == "Điều 2 — Sửa đổi Mục II" and lab["d_002"] == "Điều 2 — Hiệu lực thi hành"
    assert lab["d_003"] == "Điều 3"
    assert lab["d_004"] == "Điều 1 — Phạm vi [d_004]" and lab["d_005"] == "Điều 1 — Phạm vi [d_005]"
    assert len(set(lab.values())) == len(lab)


def test_stray_closing_quote_does_not_disable_quote_context():
    lines = ["Điều 1. Sửa đổi", "“Điều 5. A", "nội dung 5", "Điều 6. B", "nd6”", "câu có dấu đóng thừa ”",
             "Điều 2. Hiệu lực", "nd2"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1", "2"] and "Điều 6. B" in p.articles[0].lines
    assert p.stats["ambiguous_quote"] == 0 and p.stats["quote_stray_closers"] == 1


def test_heading_without_punctuation_accepted_only_when_number_is_consecutive():
    lines = ["Điều 33. Kiểm tra", "nội dung 33", "Điều 34 Trách nhiệm của Uỷ ban nhân dân các cấp", "nội dung 34",
             "Điều 5 Luật này quy định về thuế", "tiếp nội dung 34"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["33", "34"] and p.stats["heading_without_punct"] == 1
    assert "Điều 5 Luật này quy định về thuế" in p.articles[1].lines  # tham chiếu không phải tiêu đề


def test_long_heading_text_without_body_is_content_not_title_only():
    long_text = "- Tổ kiểm kê phải kiểm kê tại từng kế hoạch hợp đồng, kiểm kê xong phải lập biên bản (xem mẫu)"
    p = parse_articles(["Điều 64. Kiểm kê", "nd", f"Điều 65. {long_text}"])
    a = p.articles[1]
    assert a.title == "" and a.lines == [long_text] and article_reject_reason(a) is None
    short = parse_articles(["Điều 2. Tổ chức thực hiện"]).articles[0]
    assert article_reject_reason(short) == "title_only"


# ---- phần đính kèm sau chữ ký: quy chế giữ, mẫu biểu loại; Điều trong phần bị cắt được ghi nhận ----
def test_quy_che_after_signature_kept_but_form_templates_dropped():
    lines = ["Điều 1. Ban hành", "Ban hành kèm theo Quy chế.", "Nơi nhận:", "- Như trên;",
             "Quy chế làm việc", "Điều 1. Phạm vi", "Quy chế này quy định về làm việc.", "Điều 2. Nguyên tắc", "Làm việc công khai.",
             "Mẫu quyết định", "Căn cứ Nghị định số …/2025/NĐ-CP;", "QUYẾT ĐỊNH:", "Điều 1. Phê duyệt", "Nội dung ……",
             "Điều 2. Thi hành", "Có hiệu lực từ ngày ký."]
    p = parse_articles(lines)
    assert [(a.number, a.after_signature, a.form_template) for a in p.articles] == [
        ("1", False, False), ("1", True, False), ("2", True, False), ("1", True, True), ("2", True, True)]
    assert article_reject_reason(p.articles[1]) is None and article_reject_reason(p.articles[3]) == "form_template"
    assert article_reject_reason(p.articles[4]) == "form_template"  # cả đoạn mẫu bị loại, kể cả Điều không có chỗ trống


def test_articles_inside_cut_appendix_are_recorded():
    p = parse_articles(["Điều 1. A", "nd", "PHỤ LỤC I", "Điều 1. Mẫu hợp đồng", "x", "Điều 2. Khác", "y"])
    assert [(d["number"], d["title"]) for d in p.dropped] == [("1", "Mẫu hợp đồng"), ("2", "Khác")]


def test_validate_checks_co_quan_ban_hanh_retained(tmp_path):
    v = _load_script("validate_data")
    cfg, proc, out = _mini_env(tmp_path)
    assert v.validate(cfg)["errors"] == []
    docs = [json.loads(l) for l in (proc / "docs_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert docs[0]["co_quan_ban_hanh"] == "Bộ Tài chính"
    # xóa trường ở docs.jsonl đầu vào -> lỗi
    raw_docs = [json.loads(l) for l in (proc / "docs.jsonl").read_text(encoding="utf-8").splitlines()]
    for d in raw_docs:
        d.pop("co_quan_ban_hanh")
    _write_jsonl(proc / "docs.jsonl", raw_docs)
    assert any("co_quan_ban_hanh" in e for e in v.validate(cfg)["errors"])


def test_first_heading_without_punctuation_only_when_it_is_article_one():
    p = parse_articles(["Điều 1 Phạm vi điều chỉnh", "nội dung", "Điều 2. Đối tượng", "x"])
    assert [a.number for a in p.articles] == ["1", "2"] and p.articles[0].title == "Phạm vi điều chỉnh"
    p = parse_articles(["Điều 5 Luật này quy định về thuế", "nội dung"])
    assert p.articles == []


# ---- bằng chứng biểu mẫu: dấu ba chấm thông thường không đủ để loại ----
def test_quy_che_with_ordinary_ellipsis_is_kept_and_flagged():
    lines = ["Điều 1. A", "nd", "Nơi nhận:", "- Như trên;", "Quy chế",
             "Điều 1. Phạm vi", "Các khoản chi gồm: ... theo quy định.",
             "Điều 2. Mức chi", "Mức chi như sau: a) ...; b) ...", "Điều 3. Hiệu lực", "Có hiệu lực từ ngày ký."]
    p = parse_articles(lines)
    att = [a for a in p.articles if a.after_signature]
    assert len(att) == 3
    assert not any(a.form_template for a in att) and all(a.form_uncertain for a in att)
    assert all(article_reject_reason(a) is None for a in att)
    assert p.stats["form_uncertain_articles"] == 3 and p.stats["form_template_articles"] == 0


def test_lead_in_with_single_weak_ellipsis_is_not_enough():
    lines = ["Điều 1. A", "nd", "Nơi nhận:", "- Như trên;", "Căn cứ Luật X;", "QUYẾT ĐỊNH:",
             "Điều 1. Phê duyệt", "Phê duyệt kế hoạch ... của đơn vị.", "Điều 2. Thi hành", "Có hiệu lực từ ngày ký."]
    p = parse_articles(lines)
    att = [a for a in p.articles if a.after_signature]
    assert len(att) == 2 and not any(a.form_template for a in att) and all(a.form_uncertain for a in att)


def test_single_preamble_line_with_ellipsis_and_placeholder_is_counted_once():
    lines = ["Điều 1. A", "nd", "Nơi nhận:", "- Như trên;", "Căn cứ Luật X và đề nghị của ... (tên đơn vị);", "QUYẾT ĐỊNH:",
             "Điều 1. Phê duyệt", "Phê duyệt kế hoạch của đơn vị.", "Điều 2. Thi hành", "Có hiệu lực từ ngày ký."]
    p = parse_articles(lines)
    att = [a for a in p.articles if a.after_signature]
    assert len(att) == 2 and not any(a.form_template for a in att) and all(a.form_uncertain for a in att)
    ev = att[0].form_evidence
    assert ev["weak_ellipsis_lines"] == 1 and ev["paren_placeholder_lines"] == 1 and not ev["clear"]
    assert all(article_reject_reason(a) is None for a in att)


def test_regular_quy_che_with_can_cu_in_preamble_and_ordinary_ellipsis_is_kept():
    lines = ["Điều 1. A", "nd", "Nơi nhận:", "- Như trên;", "Căn cứ Luật Tổ chức Chính phủ, Quy chế này quy định:",
             "Điều 1. Phạm vi", "Quy chế áp dụng cho các cơ quan ... và đơn vị.", "Điều 2. Thi hành", "x"]
    p = parse_articles(lines)
    att = [a for a in p.articles if a.after_signature]
    assert not any(a.form_template for a in att) and all(article_reject_reason(a) is None for a in att)


def test_clear_form_evidence_is_recorded_for_the_reject_log():
    lines = ["Điều 1. A", "nd", "Nơi nhận:", "- Như trên;", "Căn cứ Nghị định số …/2025/NĐ-CP;", "QUYẾT ĐỊNH:",
             "Điều 1. Phê duyệt", "Nội dung ……………", "Điều 2. Thi hành", "Có hiệu lực."]
    p = parse_articles(lines)
    att = [a for a in p.articles if a.after_signature]
    assert all(article_reject_reason(a) == "form_template" for a in att)
    ev = att[0].form_evidence
    assert ev["lead_in"] and ev["strong_blank_lines"] >= 1 and ev["clear"]


# ---- vết dòng nguồn (không đổi hành vi parser) ----
def test_line_owner_maps_every_source_line():
    from src.data.parse import OWNER_NONE, OWNER_SECTION, OWNER_TRAILER, OWNER_CUT
    lines = ["Mở đầu", "Chương I", "TÊN CHƯƠNG", "Điều 1. A", "nd", "Điều 2. B", "x", "Nơi nhận:", "- y"]
    p = parse_articles(lines)
    assert p.line_owner == [OWNER_NONE, OWNER_SECTION, OWNER_SECTION, 0, 0, 1, 1, OWNER_TRAILER, OWNER_TRAILER]
    assert p.articles[0].heading_line == 3 and p.articles[0].src_lines == [4]
    p = parse_articles(["Điều 1. A", "nd", "PHỤ LỤC I", "z"])
    assert p.line_owner == [0, 0, OWNER_CUT, OWNER_CUT]


def test_line_owner_for_title_on_next_line_and_signature_tail():
    from src.data.parse import OWNER_TRAILER
    p = parse_articles(["Điều 1.", "Tên điều", "nd", "CHỦ TỊCH QUỐC HỘI", "(Đã ký)"])
    assert p.articles[0].title == "Tên điều" and p.articles[0].heading_line == 0
    assert p.line_owner == [0, 0, 0, OWNER_TRAILER, OWNER_TRAILER]


# ---- chữ "Điều" bị lỗi OCR/mã hóa ở đầu dòng (vd. 135753: "Điểu 1. …") ----
def test_ocr_variant_of_dieu_is_accepted_only_at_line_start_and_as_next_number():
    lines = ["Chương I", "QUY ĐỊNH CHUNG", "Điểu 1. Phạm vi điều chỉnh và đối tượng áp dụng", "1. Phạm vi điều chỉnh:", "Thông tư này quy định về:",
             "Điều 2. Nguyên tắc", "nội dung 2"]
    p = parse_articles(lines)
    assert [a.number for a in p.articles] == ["1", "2"] and p.articles[0].title == "Phạm vi điều chỉnh và đối tượng áp dụng"
    assert p.articles[0].lines == ["1. Phạm vi điều chỉnh:", "Thông tư này quy định về:"]  # nội dung Điều 1 không bị mất
    assert p.stats["heading_ocr_variant"] == 1 and p.line_owner[2] == 0


def test_ocr_variant_encoding_eth_is_accepted_too():
    p = parse_articles(["Ðiều 1. Phạm vi", "nd", "Điều 2. Đối tượng", "x"])
    assert [a.number for a in p.articles] == ["1", "2"] and p.stats["heading_ocr_variant"] == 1


def test_ocr_variant_is_rejected_when_number_is_not_next_or_not_at_line_start_or_no_punctuation():
    # số không phải số Điều kế tiếp
    p = parse_articles(["Điều 1. A", "nd", "Điểu 5. B", "nd5"])
    assert [a.number for a in p.articles] == ["1"] and "Điểu 5. B" in p.articles[0].lines and p.stats["heading_ocr_variant"] == 0
    # giữa dòng
    p = parse_articles(["Điều 1. A", "theo Điểu 2. của luật", "Điều 2. B", "x"])
    assert [a.number for a in p.articles] == ["1", "2"] and p.stats["heading_ocr_variant"] == 0
    # không có dấu câu sau số: giống câu tham chiếu, không nhận
    p = parse_articles(["Điều 1. A", "Điểu 2 của Luật này quy định", "Điều 2. B"])
    assert p.stats["heading_ocr_variant"] == 0
    # từ đầu dòng không phải biến thể của "Điều"
    p = parse_articles(["Điều 1. A", "Mục 2. Khác", "x"])
    assert p.stats["heading_ocr_variant"] == 0
    # "Điều" viết đúng vẫn đi đường cũ
    assert parse_articles(["Điều 1. A", "x"]).stats["heading_ocr_variant"] == 0


def test_ocr_variant_inside_quote_is_not_a_heading():
    p = parse_articles(["Điều 1. Sửa đổi", "“Điều 5. A", "Điểu 6. B", "nd”", "Điều 2. Hiệu lực", "x"])
    assert [a.number for a in p.articles] == ["1", "2"] and p.stats["heading_ocr_variant"] == 0
