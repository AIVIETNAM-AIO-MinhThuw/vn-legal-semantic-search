"""CSS tập trung; ngoại lệ ngoài key/class của UI: html (cỡ chữ gốc) và stMainBlockContainer (padding trên)."""
import streamlit as st


def inject():
    primary = st.get_option("theme.primaryColor")
    text = st.get_option("theme.textColor")
    st.html(f"""
<style>
html {{ font-size: clamp(16px, 0.55vw + 9.5px, 19px); }}
.st-key-page {{
    width: min(90vw, 1440px);
    max-width: 100%;
    margin-left: auto;
    margin-right: auto;
}}
.st-key-page .page-title {{
    font-size: 2rem;
    font-weight: 700;
    text-align: center;
}}
[class*="st-key-article"] button {{
    justify-content: flex-start;
    text-align: left;
    color: {primary};
}}
[class*="st-key-article"] button p {{
    text-align: left;
    font-size: 1.15rem;
    font-weight: 600;
    color: {primary};
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
}}
[class*="st-key-article"] button:hover p {{
    text-decoration: underline;
}}
[class*="st-key-score-"] p,
[class*="st-key-cross-rank-"] p,
.st-key-search-status p {{
    font-size: 0.85rem;
    color: #5B6470;
}}
[class*="st-key-article"] button p > span:first-child {{
    /* :small của Streamlit gán font-size inline. */
    font-size: 0.85rem !important;
    color: #5B6470;
    font-weight: 400;
}}
[class*="st-key-score-"] p {{
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}
.doc {{
    font-size: 0.95rem;
    color: {text};
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.snip {{
    font-size: 1rem;
    line-height: 1.6;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
}}
.snip-fixed {{
    min-height: calc(3 * 1rem * 1.6);
}}
.snip mark,
.reader-body mark {{
    background: #FCE8A6;
    color: inherit;
    padding: 0 .1em;
    border-radius: 2px;
}}
.summary {{
    text-align: center;
}}
.summary-num {{
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.2;
    color: {text};
}}
.summary-label {{
    font-size: 0.85rem;
    color: #5B6470;
    margin: 0;
}}
.col-title {{
    font-size: 1.25rem;
    font-weight: 600;
    line-height: 1.3;
}}
.col-scale {{
    font-size: 0.85rem;
    color: #5B6470;
}}
.st-key-reader-source p,
.st-key-reader-meta p,
.st-key-reader-score p,
.st-key-reader-note p {{
    color: #5B6470;
}}
.st-key-reader-header .reader-title {{
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.3;
}}
.reader-body {{
    white-space: pre-wrap;
    font-size: 1.1rem;
    line-height: 1.75;
    max-width: 75ch;
}}
.st-key-reader {{
    gap: 0.25rem;
}}
.st-key-reader-divider-top hr,
.st-key-reader-divider-bottom hr {{
    margin: 0.25rem 0;
}}
/* Streamlit gán margin-bottom:-1rem cho khối markdown (bù khoảng cách đoạn văn);
   khối HTML tự viết không có đoạn văn nên phải tự bù, nếu không phần tử sau sẽ đè lên.
   Không viết thẻ HTML trong comment: st.html sẽ làm hỏng cả khối style. */
.page-title,
.reader-title,
.reader-body,
.card-body,
.summary,
.col-head {{
    margin-bottom: 1rem;
}}
/* Ngoại lệ thứ hai ngoài key của UI: bớt khoảng trống mặc định phía trên trang. */
[data-testid="stMainBlockContainer"] {{
    padding-top: 4rem; /* thanh header của Streamlit cao 3.75rem, thấp hơn sẽ che tiêu đề */
}}
</style>
""")
