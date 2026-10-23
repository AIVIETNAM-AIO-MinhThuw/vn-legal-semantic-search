"""Nhãn hiển thị của Điều: 'Điều <số> — <tiêu đề>'; thêm định danh khi nhãn vẫn trùng trong cùng văn bản."""
from __future__ import annotations

from collections import Counter


def make_display_labels(articles: list[dict]) -> dict[str, str]:
    """articles: các Điều của MỘT văn bản (có article_id, number, title). Trả về {article_id: nhãn}."""
    base = {}
    for a in articles:
        title = (a.get("title") or "").strip()
        base[a["article_id"]] = f"Điều {a['number']} — {title}" if title else f"Điều {a['number']}"
    seen = Counter(base.values())
    return {aid: (lab if seen[lab] == 1 else f"{lab} [{aid}]") for aid, lab in base.items()}
