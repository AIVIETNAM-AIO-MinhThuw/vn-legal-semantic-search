"""CSS tập trung; html là ngoại lệ duy nhất ngoài key/class của UI."""
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
</style>
""")
