"""Danh sách một cột và hai danh sách so sánh độc lập."""
import streamlit as st

from src.contracts import Highlight
from src.ui.compare import other_rank, summary
from src.ui.highlight import render_html, snippet
from src.ui.layout import NAMES, SCORE_HELP, format_score
from src.ui.reader import open_reader


def result_card(item, result_list, search_id, client, other=None):
    system = result_list.system
    cross_rank = other_rank(other, item.article_id) if other is not None else None
    with st.container(border=True, key=f"card-{system}-{item.article_id}"):
        ratio = [0.74, 0.26] if other is not None else [0.82, 0.18]
        title_col, score_col = st.columns(ratio, vertical_alignment="top")
        with title_col:
            if st.button(f":small[#{item.rank}]  Điều {item.article_number}. {item.article_title}",
                         key=f"article:{search_id}:{system}:{item.article_id}",
                         type="tertiary", width="stretch"):
                open_reader(item, system, result_list.score_type,
                            search_id, client, other is not None, cross_rank)
        with score_col:
            with st.container(horizontal=True, horizontal_alignment="right", key=f"score-{system}-{item.article_id}"):
                st.caption(format_score(item.score, result_list.score_type), help=SCORE_HELP, width="content")
        content, highlights = item.content, item.highlights
        if system != "bm25" and highlights:
            first = highlights[0]
            content = content[first.start:first.end]
            highlights = [Highlight(start=0, end=len(content))]
        text, spans = snippet(content, highlights)
        st.markdown(render_html(text, spans, doc_title=item.doc_title,
                                fixed_snippet=other is not None), unsafe_allow_html=True)
        if other is not None:
            rank = f"#{cross_rank}" if cross_rank is not None else "—"
            with st.container(key=f"cross-rank-{system}-{item.article_id}"):
                st.caption(f"Bên {NAMES[other.system]}: {rank}")


def results(response, mode, client):
    if mode != "compare":
        result_list = response.lists[0]
        for item in result_list.items:
            result_card(item, result_list, response.search_id, client)
        return
    lists = {result_list.system: result_list for result_list in response.lists}
    bm25, semantic = lists["bm25"], lists["semantic"]
    counts = summary(bm25, semantic)
    for index, (column, count, text) in enumerate(zip(st.columns(3), counts,
                                   ("Điều có ở cả hai", "chỉ có ở BM25", "chỉ có ở Semantic"))):
        with column.container(border=True, key=f"compare-summary-{index}"):
            st.markdown(f'<div class="summary"><div class="summary-num">{count}</div>'
                        f'<div class="summary-label">{text}</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    for column, title, scale in ((left, "BM25 — Khớp từ khóa", "bm25"),
                                 (right, "Semantic — Gần nghĩa nội dung", "cosine")):
        with column:
            st.markdown(f'<div class="col-head"><div class="col-title">{title}</div>'
                        f'<div class="col-scale">Thang điểm: {scale}</div></div>', unsafe_allow_html=True)
    for index in range(max(len(bm25.items), len(semantic.items))):
        left, right = st.columns(2)
        if index < len(bm25.items):
            with left:
                result_card(bm25.items[index], bm25, response.search_id, client, semantic)
        if index < len(semantic.items):
            with right:
                result_card(semantic.items[index], semantic, response.search_id, client, bm25)
