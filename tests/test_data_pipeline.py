"""Unit test cho prefix E5, tokenization, HTML->text, parse Điều và chunk (SPEC 3.4, 7.3, 13.1)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.chunk import chunk_article, make_prefix  # noqa: E402
from src.data.html_text import html_to_lines  # noqa: E402
from src.data.parse import article_reject_reason, parse_articles  # noqa: E402
from src.data.tokenizer import count_tokens, load_tokenizer  # noqa: E402
from src.retrieval.e5_format import format_passage, format_query  # noqa: E402

CFG = yaml.safe_load(open(ROOT / "configs" / "data.yaml", encoding="utf-8"))
LIMIT, OVERLAP = CFG["chunk"]["max_tokens"], CFG["chunk"]["token_overlap"]


@pytest.fixture(scope="module")
def tok():
    if not (ROOT / CFG["tokenizer"]["local_dir"] / "tokenizer.json").exists():
        pytest.skip("thiếu tokenizer E5; chạy scripts/download_data.py")
    return load_tokenizer(CFG)


# ---- E5 prefix: đúng một lần ----
def test_prefix_applied_once():
    assert format_query("thuế") == "query: thuế"
    assert format_passage("nội dung") == "passage: nội dung"


def test_prefix_not_applied_twice():
    with pytest.raises(ValueError):
        format_passage(format_passage("x"))
    with pytest.raises(ValueError):
        format_query(format_query("x"))


# ---- HTML -> text ----
def test_inline_tags_do_not_break_lines_and_nfc():
    h = "<p>Điều 1. <b>Phạm</b> vi</p><p>Theo <a href='#'>158/2002/QĐ-TTg</a> ngày 1</p>"
    assert html_to_lines(h) == ["Điều 1. Phạm vi", "Theo 158/2002/QĐ-TTg ngày 1"]
    import unicodedata
    decomposed = unicodedata.normalize("NFD", "<p>Điều</p>")
    assert html_to_lines(decomposed) == [unicodedata.normalize("NFC", "Điều")]


def test_table_rows_one_line_cells_joined_by_pipe():
    h = "<table><tr><td>STT</td><td>Tên</td></tr><tr><td>1</td><td>Thuế</td></tr></table>"
    assert html_to_lines(h) == ["STT | Tên", "1 | Thuế"]


def test_empty_html():
    assert html_to_lines("") == [] and html_to_lines("   ") == []


# ---- parse ----
def test_parse_basic_and_trailer_and_section():
    lines = ["NGHỊ ĐỊNH", "Căn cứ Luật X;", "Chương I", "QUY ĐỊNH CHUNG", "Điều 1. Phạm vi", "Nội dung 1.",
             "Điều 2. Đối tượng", "1. Khoản một.", "Nơi nhận:", "- Như trên;"]
    p = parse_articles(lines)
    assert [(a.number, a.title) for a in p.articles] == [("1", "Phạm vi"), ("2", "Đối tượng")]
    assert p.articles[0].lines == ["Nội dung 1."]
    assert p.articles[1].lines == ["1. Khoản một."]


def test_parse_quoted_article_inside_amendment_not_a_heading():
    lines = ["Điều 1. Sửa đổi Điều 5", "“Điều 5. Nội dung mới", "1. Khoản”"]
    p = parse_articles(lines)
    assert len(p.articles) == 1 and p.articles[0].number == "1"


def test_heading_text_that_is_content():
    p = parse_articles(["Điều 3. Nghị định này có hiệu lực từ ngày 1 tháng 1 năm 1996."])
    a = p.articles[0]
    assert a.title == "" and a.lines and article_reject_reason(a) is None


def test_appendix_cut():
    p = parse_articles(["Điều 1. A", "nội dung", "PHỤ LỤC I", "Điều 1. Mẫu hợp đồng", "x"])
    assert len(p.articles) == 1 and p.stats["appendix_cut"]


def test_reject_title_only_and_repeal_note():
    p = parse_articles(["Điều 1. Tên điều", "Điều 2. Khác", "Điều này được bãi bỏ.", "Điều 3. Hiệu lực", "Bãi bỏ Thông tư số 1/2000."])
    assert article_reject_reason(p.articles[0]) == "title_only"
    assert article_reject_reason(p.articles[1]) == "repeal_note"
    assert article_reject_reason(p.articles[2]) is None  # nội dung tác nghiệp, không phải ghi chú bãi bỏ


# ---- chunk ----
def test_tokenization_consistency(tok):
    t = make_prefix("Luật Thuế", "5", "Giải thích") + "Nội dung của Điều."
    assert count_tokens(tok, t) == len(tok(t, add_special_tokens=False)["input_ids"])
    assert count_tokens(tok, t) == count_tokens(tok, t)


def test_short_article_single_chunk(tok):
    prefix = make_prefix("Luật Thuế", "1", "Phạm vi")
    chunks, long_s = chunk_article(tok, prefix, ["Luật này quy định về thuế."], LIMIT, OVERLAP)
    assert len(chunks) == 1 and chunks[0].kind == "whole" and not long_s
    assert chunks[0].text.startswith("Luật Thuế › Điều 1. Phạm vi › ")


def _all_le_limit(chunks, tok):
    return all(count_tokens(tok, c.text) <= LIMIT and c.n_tokens == count_tokens(tok, c.text) for c in chunks)


def test_long_article_groups_khoan(tok):
    prefix = make_prefix("Luật Thuế", "2", "Quy định")
    khoans = [f"{i}. " + "Người nộp thuế phải kê khai đầy đủ thông tin theo quy định. " * 12 for i in range(1, 8)]
    chunks, long_s = chunk_article(tok, prefix, khoans, LIMIT, OVERLAP)
    assert len(chunks) > 1 and _all_le_limit(chunks, tok) and not long_s
    assert all(c.kind == "khoan" for c in chunks)
    joined = "\n".join(c.body for c in chunks)
    assert all(k[:30] in joined for k in khoans)  # không mất khoản nào


def test_long_khoan_splits_by_sentence_with_one_sentence_overlap(tok):
    prefix = make_prefix("Luật Thuế", "3", "Quy định")
    sents = [f"Câu số {i} quy định nghĩa vụ kê khai thuế của người nộp thuế trong kỳ tính thuế." for i in range(1, 80)]
    chunks, long_s = chunk_article(tok, prefix, ["1. " + " ".join(sents)], LIMIT, OVERLAP)
    assert len(chunks) > 1 and _all_le_limit(chunks, tok) and not long_s
    assert all(c.kind == "sentence" for c in chunks)
    for a, b in zip(chunks, chunks[1:]):  # chồng lấn 1 câu giữa hai cửa sổ liền nhau
        last = a.body.split(". ")[-1].strip()
        assert last.rstrip(".") in b.body


def test_oversize_sentence_cut_by_token_with_overlap_and_flag(tok):
    prefix = make_prefix("Luật Thuế", "4", "Danh mục")
    sentence = ", ".join(f"mặt hàng số {i}" for i in range(1, 600)) + "."
    chunks, long_s = chunk_article(tok, prefix, [sentence], LIMIT, OVERLAP)
    assert long_s and len(chunks) > 1 and _all_le_limit(chunks, tok)
    assert all(c.kind == "token_window" for c in chunks)
    # chồng lấn ~50 token: phần cuối cửa sổ k xuất hiện đầu cửa sổ k+1
    for a, b in zip(chunks, chunks[1:]):
        tail = a.body[-80:].strip()
        assert tail[-30:] in b.body


def test_prefix_too_long_raises(tok):
    prefix = make_prefix("từ " * 600, "1", "x")
    with pytest.raises(ValueError):
        chunk_article(tok, prefix, ["câu rất dài " * 300], LIMIT, OVERLAP)
