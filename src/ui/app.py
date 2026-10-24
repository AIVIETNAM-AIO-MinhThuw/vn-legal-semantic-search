"""Chạy từ thư mục repo: streamlit run src/ui/app.py."""
import os
import sys
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

# Streamlit thêm thư mục entrypoint vào sys.path; đưa gốc repo vào để import contracts.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.contracts import ErrorCode, SearchFilters, SearchRequest
from src.ui.cards import results
from src.ui.client import ApiClient, SampleClient
from src.ui.errors import ApiFailure, UNAVAILABLE, error_text
from src.ui.layout import controls, footer, header, search_form, status
from src.ui.state import FILTERS, apply_info, clear_filters, init_state, reload_info

st.set_page_config(page_title="Tìm kiếm pháp luật", layout="wide", initial_sidebar_state="collapsed")


def load_info(client):
    try:
        info = client.info()
    except ApiFailure as error:
        st.session_state.availability_error = error
    else:
        st.session_state.info = info
        st.session_state.availability_error = None
        apply_info(info)
    st.session_state.info_loaded = True


def availability_notice(error):
    if error.code == ErrorCode.INDEX_MANIFEST_MISMATCH and not error.connection:
        st.error(error_text(error.code))
    else:
        st.warning(UNAVAILABLE)
        if error.code == ErrorCode.MODEL_NOT_READY and not error.connection:
            st.caption(error_text(error.code))
    st.button("Thử lại", on_click=reload_info)


def perform_search(client):
    st.session_state.pending_search = False
    st.session_state.response = None
    st.session_state.search_error = None
    try:
        req = SearchRequest(query=st.session_state.last_query, mode=st.session_state.mode,
                            top_k=st.session_state.top_k,
                            filters=SearchFilters(**{key: st.session_state[key] for key in FILTERS}))
        with st.spinner("Đang tìm…"):
            response = client.search(req)
        expected = {"bm25", "semantic"} if req.mode == "compare" else {req.mode}
        if len(response.lists) != len(expected) or {r.system for r in response.lists} != expected:
            raise ApiFailure()
        st.session_state.response = response
    except ValidationError:
        st.session_state.search_error = ApiFailure()
    except ApiFailure as error:
        if error.connection or error.code in (ErrorCode.MODEL_NOT_READY, ErrorCode.INDEX_MANIFEST_MISMATCH):
            st.session_state.availability_error = error
            st.rerun()
        st.session_state.search_error = error
        if error.code == ErrorCode.INVALID_FILTER:
            # Làm mới ngay; áp dụng options trước khi các widget được tạo ở lần rerun sau.
            try:
                st.session_state.info = client.info()
                st.session_state.apply_info_next = True
            except ApiFailure as info_error:
                st.session_state.availability_error = info_error
            st.rerun()


def main():
    init_state()
    sample = os.environ.get("UI_SAMPLE") == "1"
    if "client" not in st.session_state:
        st.session_state.client = SampleClient() if sample else ApiClient()
    client = st.session_state.client
    if sample:
        client.scenario = st.session_state.scenario
    if not st.session_state.info_loaded:
        load_info(client)
    if st.session_state.pop("apply_info_next", False):
        apply_info(st.session_state.info)
    info = st.session_state.info
    blocked = st.session_state.availability_error is not None or info is None or not info.modes
    with st.container(horizontal=True, horizontal_alignment="center"):
        content = st.container(width=1200)
    with content:
        header()
        submitted = search_form(blocked)
        messages = st.container()
        if not blocked:
            controls(info, False)
            if submitted:
                st.session_state.last_query = st.session_state.query
                st.session_state.pending_search = True
            if st.session_state.pending_search and st.session_state.mode is not None:
                perform_search(client)
            with messages:
                if st.session_state.search_error:
                    st.warning(error_text(st.session_state.search_error.code))
            response = st.session_state.response
            if response is not None:
                status(response, st.session_state.mode, st.session_state.top_k)
                if not any(result_list.items for result_list in response.lists):
                    st.info("Không có Điều nào khớp bộ lọc.")
                    st.button("Xóa lọc", key="clear_empty", on_click=clear_filters)
                else:
                    results(response, st.session_state.mode, client)
            elif st.session_state.last_query is None:
                st.caption("Nhập câu hỏi pháp luật rồi nhấn Tìm để bắt đầu tra cứu.")
        else:
            with messages:
                availability_notice(st.session_state.availability_error or ApiFailure(connection=True))
            controls(info, True)
        footer(info, client, sample)


main()
