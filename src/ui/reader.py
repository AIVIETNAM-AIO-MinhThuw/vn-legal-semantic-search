"""Cửa sổ đọc chỉ nhận item và hệ thống của lần bấm."""
import streamlit as st

from src.contracts import ErrorCode, FeedbackRequest
from src.ui.errors import ApiFailure, FEEDBACK_FAILED, SEARCH_EXPIRED
from src.ui.highlight import render_html
from src.ui.layout import NAMES, SCORE_HELP, format_score


@st.dialog("Toàn văn Điều", width="large")
def open_reader(item, system, score_type, search_id, client, compare=False, cross_rank=None):
    name = NAMES[system]
    other = "Semantic" if system == "bm25" else "BM25"
    st.caption(f"Đang xem từ cột {name}" if compare else f"Kết quả {name}")
    title = f"Điều {item.article_number}. {item.article_title}"
    st.subheader(title)
    st.caption(f"{item.doc_title} · {item.effect_status}")
    score = f"{name} #{item.rank} · {format_score(item.score, score_type)}"
    if compare:
        score += f" · {other} #{cross_rank}" if cross_rank is not None else f" · {other} —"
    st.caption(score, help=SCORE_HELP)
    with st.container(height=420, border=False):
        st.markdown(render_html(item.content, item.highlights), unsafe_allow_html=True)
    st.caption("BM25: tô các từ trùng với câu hỏi." if system == "bm25" else
               f"{name}: tô câu gần nghĩa nhất với câu hỏi.")
    vote_key = (str(search_id), system, item.article_id)
    selected = st.session_state.feedback_labels.get(vote_key)
    with st.container(horizontal=True):
        for label, text in (("useful", "Hữu ích"), ("not_useful", "Không hữu ích")):
            if st.button(text, key=f"vote:{vote_key}:{label}",
                         type="primary" if selected == label else "secondary", width="content"):
                req = FeedbackRequest(search_id=search_id, system=system, article_id=item.article_id, label=label)
                try:
                    client.feedback(req)
                except ApiFailure as error:
                    # Hợp đồng chỉ có INVALID_REQUEST cho mọi lỗi feedback 422.
                    expired = error.status == 422 and error.code == ErrorCode.INVALID_REQUEST
                    st.toast(SEARCH_EXPIRED if expired else FEEDBACK_FAILED)
                else:
                    st.session_state.feedback_labels[vote_key] = label
                    st.session_state.csv = None
                    st.rerun(scope="fragment")
    st.code(f"{title} — {item.doc_title}", language=None, wrap_lines=True)
