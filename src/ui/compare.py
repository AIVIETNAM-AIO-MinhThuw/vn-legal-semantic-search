"""Đối chiếu Điều bằng article_id; không so sánh điểm khác thang."""
from src.contracts import ResultList


def summary(bm25: ResultList, semantic: ResultList) -> tuple[int, int, int]:
    left = {item.article_id for item in bm25.items}
    right = {item.article_id for item in semantic.items}
    return len(left & right), len(left - right), len(right - left)


def other_rank(other: ResultList, article_id: str) -> int | None:
    return next((item.rank for item in other.items if item.article_id == article_id), None)
