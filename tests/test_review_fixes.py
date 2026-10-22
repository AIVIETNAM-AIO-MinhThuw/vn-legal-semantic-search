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
    pd.DataFrame({"id": ["1", "2"]}).to_parquet(raw / "data" / "metadata.parquet")
    labels = list(cfg["relations"]["mapping"])  # mọi nhãn đã ánh xạ phải xuất hiện trong dữ liệu
    pd.DataFrame({"doc_id": ["1"] * len(labels), "other_doc_id": ["2"] * len(labels),
                  "relationship": labels}).to_parquet(raw / "data" / "relationships.parquet")
    (logs / "fc.json").write_text(json.dumps({"steps": [], "articles_rejected": {}, "parse_stats": {}}), encoding="utf-8")
    body = "Nội dung giống nhau."
    docs = [{"doc_id": "1", "title": "A", "n_articles": 2, "has_duplicate_article_numbers": False, "linh_vuc": "x",
             "loai_van_ban": "Luật", "tinh_trang_hieu_luc": "Còn hiệu lực", "year": 2020},
            {"doc_id": "2", "title": "B", "n_articles": 1, "has_duplicate_article_numbers": False, "linh_vuc": "x",
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
