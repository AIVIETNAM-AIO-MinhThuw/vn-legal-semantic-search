"""Thành phần Streamlit gốc, không CSS hoặc sidebar."""
import streamlit as st

from src.contracts import WarningCode
from src.ui.client import SCENARIOS
from src.ui.errors import ApiFailure, EXPORT_FAILED, WARNINGS
from src.ui.state import (
    FILTERS, change_scenario, clear_filters, queue_search, reload_info, remove_filter,
)

NAMES = {"semantic": "Semantic", "bm25": "BM25", "hybrid": "Hybrid", "compare": "So sánh"}
SCORE_HELP = "Điểm chỉ dùng để xếp hạng trong cùng một danh sách, không phải phần trăm chính xác."
MODE_HELP = "BM25: tìm theo từ khóa trùng khớp. Semantic: tìm theo ý nghĩa câu hỏi. Hybrid: kết hợp cả hai."


def format_score(score, score_type):
    digits = {"bm25": 3, "cosine": 3, "rrf": 4}[score_type]
    return f"{score_type} {score:.{digits}f}".replace(".", ",")


def header():
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.title("Tìm kiếm ngữ nghĩa văn bản pháp luật", width="content")
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.caption("Kết quả không thay thế tư vấn pháp lý.", width="content")


def search_form(disabled):
    with st.form("search_form", border=False):
        question, submit = st.columns([9, 1], vertical_alignment="bottom")
        with question:
            st.text_input("Câu hỏi pháp luật", placeholder="Nhập câu hỏi pháp luật…",
                          label_visibility="collapsed", key="query", disabled=disabled)
        with submit:
            return st.form_submit_button("Tìm", type="primary", disabled=disabled, width="stretch")


def controls(info, disabled):
    mode_col, filter_col = st.columns([4, 1], vertical_alignment="bottom")
    with mode_col:
        options = [mode for mode in NAMES if mode in info.modes] if info else []
        if options:
            st.segmented_control("Chế độ", options, format_func=NAMES.get, key="mode",
                                 help=MODE_HELP, disabled=disabled, on_change=queue_search,
                                 label_visibility="collapsed")
    with filter_col:
        count = sum(bool(st.session_state.get(key)) for key in FILTERS)
        with st.popover(f"Bộ lọc ({count})" if count else "Bộ lọc", disabled=disabled, width="stretch"):
            if info:
                for key, label in FILTERS.items():
                    st.multiselect(label, getattr(info.filter_values, key), key=key,
                                   disabled=disabled, on_change=queue_search, placeholder="Tất cả")
                limits = info.limits
                if limits.top_k_min < limits.top_k_max:
                    st.slider("Số kết quả", limits.top_k_min, limits.top_k_max, key="top_k",
                              disabled=disabled, on_change=queue_search)
                else:
                    st.caption(f"Số kết quả: {limits.top_k_min}")
                st.button("Xóa lọc", key="clear_popover", on_click=clear_filters, disabled=disabled)
    selected = [(key, value) for key in FILTERS for value in st.session_state.get(key, [])]
    if selected:
        with st.container(horizontal=True):
            for key, value in selected:
                st.button(f"{FILTERS[key]}: {value} ✕", key=f"chip:{key}:{value}",
                          on_click=remove_filter, args=(key, value), disabled=disabled)


def status(response, mode, top_k):
    if mode == "compare":
        st.caption("So sánh: BM25 (thang bm25) và Semantic (thang cosine) · "
                   f"{top_k} kết quả mỗi bên · {response.timing_ms:g} ms")
    else:
        result_list = response.lists[0]
        st.caption(f"{len(result_list.items)} kết quả · {response.timing_ms:g} ms · "
                   f"{NAMES[result_list.system]} (thang {result_list.score_type})")
    for warning in response.warnings:
        if warning.code in WARNINGS:
            st.info(WARNINGS[WarningCode(warning.code)])


def footer(info, client, sample):
    with st.expander("Thông tin hệ thống & tải feedback", expanded=False):
        if sample:
            st.caption("Dữ liệu mẫu tự biên soạn, không phải văn bản pháp luật thật. Bộ lọc chỉ mô phỏng thao tác.")
            st.session_state.scenario_widget = st.session_state.scenario
            st.selectbox("Kịch bản (chế độ mẫu)", SCENARIOS, key="scenario_widget", on_change=change_scenario)
        if info:
            for field in ("semantic_system", "model_name", "model_revision", "git_commit",
                          "manifest_hashes", "contract_version"):
                st.text(f"{field}: {getattr(info, field)}")
        else:
            st.caption("Chưa tải được thông tin hệ thống.")
        if st.button("Chuẩn bị CSV feedback"):
            st.session_state.csv = None
            try:
                st.session_state.csv = client.export_csv()
            except ApiFailure:
                st.toast(EXPORT_FAILED)
        if st.session_state.csv is not None:
            st.download_button("Tải CSV feedback", data=st.session_state.csv,
                               file_name="feedback.csv", mime="text/csv", on_click="ignore")
        st.button("Tải lại thông tin", on_click=reload_info)
