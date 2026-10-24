"""Trạng thái của một phiên trình duyệt, không ghi database."""
import streamlit as st

FILTERS = {"doc_types": "Loại văn bản", "domains": "Lĩnh vực", "issuers": "Cơ quan ban hành"}


def init_state():
    defaults = {
        "info": None, "info_loaded": False, "availability_error": None,
        "search_error": None, "response": None, "last_query": None,
        "pending_search": False, "feedback_labels": {}, "csv": None,
        "scenario": "bình thường", "query": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def queue_search():
    if st.session_state.get("mode") is None:
        st.session_state.mode = st.session_state.get("last_mode")
    else:
        st.session_state.last_mode = st.session_state.mode
    st.session_state.pending_search = st.session_state.last_query is not None


def clear_filters():
    for key in FILTERS:
        st.session_state[key] = []
    queue_search()


def remove_filter(key, value):
    st.session_state[key] = [item for item in st.session_state[key] if item != value]
    queue_search()


def reload_info():
    st.session_state.info_loaded = False
    st.session_state.csv = None
    queue_search()


def change_scenario():
    st.session_state.scenario = st.session_state.scenario_widget
    st.session_state.response = None
    st.session_state.search_error = None
    reload_info()


def apply_info(info):
    for key in FILTERS:
        allowed = getattr(info.filter_values, key)
        st.session_state[key] = [v for v in st.session_state.get(key, []) if v in allowed]
    if st.session_state.get("mode") not in info.modes:
        st.session_state.mode = "semantic" if "semantic" in info.modes else next(iter(info.modes), None)
    st.session_state.last_mode = st.session_state.mode
    limits = info.limits
    st.session_state.top_k = min(limits.top_k_max, max(limits.top_k_min, st.session_state.get("top_k", 10)))
