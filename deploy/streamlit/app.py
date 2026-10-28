"""Community Cloud entrypoint; run the unchanged, verified main UI."""
import os
from pathlib import Path
import runpy
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap import prepare_runtime, start_backend


@st.cache_resource(show_spinner=False)
def backend():
    source = prepare_runtime()
    process, url = start_backend(source)
    return source, process, url


try:
    with st.spinner('Đang chuẩn bị dữ liệu và nạp model CPU; lần đầu có thể mất vài phút…'):
        source, process, url = backend()
    if process.poll() is not None:
        backend.clear()
        raise RuntimeError('API đã dừng. Tải lại trang để khởi động lại.')
except Exception as error:
    st.error(f'Không khởi động được demo: {error}')
    st.stop()

os.environ.update(API_BASE_URL=url, UI_TIMEOUT_S='180', UI_SAMPLE='0')
runpy.run_path(str(source / 'src/ui/app.py'), run_name='__main__')
