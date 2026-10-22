"""Hàm duy nhất gắn tiền tố E5 (SPEC 7.3): mỗi chuỗi nhận tiền tố đúng một lần."""
from __future__ import annotations

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


def format_query(text: str) -> str:
    _check_unprefixed(text)
    return QUERY_PREFIX + text


def format_passage(text: str) -> str:
    _check_unprefixed(text)
    return PASSAGE_PREFIX + text


def _check_unprefixed(text: str) -> None:
    if text.startswith((QUERY_PREFIX, PASSAGE_PREFIX)):
        raise ValueError("Văn bản đã có tiền tố E5; không được gắn tiền tố hai lần.")
