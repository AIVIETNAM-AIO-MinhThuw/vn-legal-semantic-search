"""Danh sách một cột và hai danh sách so sánh độc lập."""
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
            title_col, score_col = st.columns([4, 1])
            with title_col:
                if st.button(f"#{item.rank} · Điều {item.article_number}. {item.article_title}",
                             key=f"article:{search_id}:{result_list.system}:{item.article_id}",
                             type="tertiary", width="stretch"):
                    open_reader(item, result_list.system, result_list.score_type,
                                search_id, client, other is not None, cross_rank)
            with score_col:
                st.caption(format_score(item.score, result_list.score_type), help=SCORE_HELP)
            st.caption(item.doc_title)
            content, highlights = item.content, item.highlights
            if result_list.system != "bm25" and highlights:
                first = highlights[0]
                content = content[first.start:first.end]
                highlights = [Highlight(start=0, end=len(content))]
            text, spans = snippet(content, highlights)
            st.markdown(render_html(text, spans), unsafe_allow_html=True)
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
            st.write(f"{count} {text}")
    left, right = st.columns(2)
    with left:
        st.subheader("BM25 — Khớp từ khóa")
        st.caption("Thang điểm: bm25")
        result_cards(bm25, response.search_id, client, semantic)
    with right:
        st.subheader("Semantic — Gần nghĩa nội dung")
        st.caption("Thang điểm: cosine")
        result_cards(semantic, response.search_id, client, bm25)
