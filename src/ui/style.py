"""CSS tập trung, chỉ chọn key của UI hoặc class HTML do UI sinh ra."""
import streamlit as st


def inject():
    primary = st.get_option("theme.primaryColor")
    text = st.get_option("theme.textColor")
    st.html(f"""
<style>
[class*="st-key-article"] button {{
    justify-content: flex-start;
    text-align: left;
    color: {primary};
}}
[class*="st-key-article"] button p {{
    text-align: left;
    font-size: 1.05rem;
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
[class*="st-key-rank-"] p,
[class*="st-key-score-"] p,
[class*="st-key-cross-rank-"] p {{
    font-size: 0.8rem;
    color: #5B6470;
}}
[class*="st-key-score-"] p {{
    font-variant-numeric: tabular-nums;
}}
.doc {{
    font-size: 0.85rem;
    color: #5B6470;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.snip {{
    font-size: 0.95rem;
    line-height: 1.55;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
    min-height: calc(3 * 0.95rem * 1.55);
}}
.snip mark,
.reader-body mark {{
    background: #FCE8A6;
    color: inherit;
    padding: 0 .1em;
    border-radius: 2px;
}}
[class*="st-key-compare-summary-"] p {{
    text-align: center;
    font-size: 0.85rem;
    color: #5B6470;
}}
[class*="st-key-compare-summary-"] strong {{
    font-size: 1.5rem;
    font-weight: 700;
    color: {text};
}}
[class*="st-key-compare-heading-"] p {{
    font-size: 1.25rem;
}}
[class*="st-key-compare-scale-"] p,
.st-key-reader-source p,
.st-key-reader-meta p,
.st-key-reader-score p,
.st-key-reader-note p {{
    color: #5B6470;
}}
.st-key-reader-header .reader-title {{
    font-size: 1.6rem;
    font-weight: 700;
    line-height: 1.3;
}}
.reader-body {{
    white-space: pre-wrap;
    font-size: 1.05rem;
    line-height: 1.75;
    max-width: 75ch;
}}
</style>
""")
