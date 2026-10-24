"""Danh sách một cột và hai danh sách so sánh độc lập."""
from html import escape

import streamlit as st

from src.contracts import Highlight
from src.ui.compare import other_rank, summary
from src.ui.highlight import render_html, snippet
from src.ui.layout import NAMES, SCORE_HELP, format_score
from src.ui.reader import open_reader


def result_cards(result_list, search_id, client, other=None):
    for item in result_list.items:
        cross_rank = other_rank(other, item.article_id) if other is not None else None
        with st.container(border=True):
            rank_col, title_col, score_col = st.columns([0.3, 3.7, 1], vertical_alignment="center")
            with rank_col:
                st.caption(f"#{item.rank}")
            with title_col:
                if st.button(f"Điều {item.article_number}. {item.article_title}",
                             key=f"article:{search_id}:{result_list.system}:{item.article_id}",
                             type="tertiary", width="stretch"):
                    open_reader(item, result_list.system, result_list.score_type,
                                search_id, client, other is not None, cross_rank)
            with score_col:
                st.caption(format_score(item.score, result_list.score_type), help=SCORE_HELP)
            content, highlights = item.content, item.highlights
            if result_list.system != "bm25" and highlights:
                first = highlights[0]
                content = content[first.start:first.end]
                highlights = [Highlight(start=0, end=len(content))]
            text, spans = snippet(content, highlights)
            doc_title = escape(item.doc_title).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            excerpt = render_html(text, spans).removeprefix('<div style="white-space: pre-wrap">').removesuffix("</div>")
            st.markdown(f":small[:gray[{doc_title}]]  \n<span>{excerpt}</span>", unsafe_allow_html=True)
            if other is not None:
                rank = f"#{cross_rank}" if cross_rank is not None else "—"
                st.caption(f"Bên {NAMES[other.system]}: {rank}")


def results(response, mode, client):
    if mode != "compare":
        result_cards(response.lists[0], response.search_id, client)
        return
    lists = {result_list.system: result_list for result_list in response.lists}
    bm25, semantic = lists["bm25"], lists["semantic"]
    counts = summary(bm25, semantic)
    for column, count, text in zip(st.columns(3), counts,
                                   ("Điều có ở cả hai", "chỉ có ở BM25", "chỉ có ở Semantic")):
        with column.container(border=True):
            st.markdown(f"**{count}** {text}")
    left, right = st.columns(2)
    with left:
        st.subheader("BM25 — Khớp từ khóa")
        st.caption("Thang điểm: bm25")
        result_cards(bm25, response.search_id, client, semantic)
    with right:
        st.subheader("Semantic — Gần nghĩa nội dung")
        st.caption("Thang điểm: cosine")
        result_cards(semantic, response.search_id, client, bm25)
