"""Chọn Điều để sinh query (SPEC 5.2, 5.4). Đọc split đã có; không tạo hoặc đổi split."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from .text import is_excluded_title

SPLITS = ("train", "val", "test")
TYPES = ("natural", "scenario", "keyword")


class SplitMissingError(SystemExit):
    pass


class InsufficientSourceError(ValueError):
    """Nguồn đủ điều kiện không đủ: báo nhóm; không lấy bù từ split khác, không đổi seed (SPEC 5.4)."""


def read_jsonl(p: Path | str) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_doc_splits(path: Path | str) -> dict[str, str]:
    """doc_id -> split từ splits.json (do scripts/split.py tạo). Báo lỗi rõ nếu split chưa tồn tại."""
    p = Path(path)
    if not p.exists():
        raise SplitMissingError(f"Chưa có split tại {p}: chưa chạy split (chờ người xác nhận corpus). "
                                "Công cụ sinh query không tự tạo split.")
    obj = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for g, members in obj["members"].items():
        for d in members:
            if d in out:
                raise ValueError(f"văn bản {d} thuộc nhiều họ")
            out[d] = obj["splits"][g]
    return out


def eligible_articles(articles: list[dict], docs: list[dict], doc_split: dict[str, str], split: str, excluded_titles: list[str]) -> list[dict]:
    """Điều của split đã cho, bỏ các Điều có tiêu đề thuộc nhóm thi hành; sắp theo article_id (thứ tự ổn định)."""
    if split not in SPLITS:
        raise ValueError(split)
    domain = {d["doc_id"]: d["linh_vuc"] for d in docs}
    out = []
    for a in articles:
        if doc_split.get(a["doc_id"]) != split or is_excluded_title(a.get("title", ""), excluded_titles):
            continue
        out.append({**a, "split": split, "domain": domain.get(a["doc_id"])})
    return sorted(out, key=lambda a: a["article_id"])


def uniform_sample(items: list[dict], k: int, seed) -> list[dict]:
    if k > len(items):
        raise InsufficientSourceError(f"cần {k} Điều nhưng chỉ có {len(items)} Điều đủ điều kiện")
    return random.Random(f"{seed}|uniform").sample(sorted(items, key=lambda a: a["article_id"]), k)


def stratified_sample(items: list[dict], k: int, seed) -> list[dict]:
    """Chọn ngẫu nhiên phân tầng theo lĩnh vực: chỉ tiêu tỷ lệ thuận, phần dư lớn nhất (hòa: tên lĩnh vực Unicode)."""
    if k > len(items):
        raise InsufficientSourceError(f"cần {k} Điều nhưng chỉ có {len(items)} Điều đủ điều kiện")
    by = defaultdict(list)
    for a in items:
        by[a["domain"]].append(a)
    n = len(items)
    exact = {d: Fraction(k * len(v), n) for d, v in by.items()}
    alloc = {d: e.numerator // e.denominator for d, e in exact.items()}
    for d in sorted(by, key=lambda d: (-(exact[d] - alloc[d]), d))[: k - sum(alloc.values())]:
        alloc[d] += 1
    out = []
    for d in sorted(by):
        pool = sorted(by[d], key=lambda a: a["article_id"])
        out += random.Random(f"{seed}|{d}").sample(pool, alloc[d])
    return sorted(out, key=lambda a: a["article_id"])


def assign_eval_types(article_ids: list[str], per_type: int, seed) -> dict[str, str]:
    """Gán kiểu query cho từng Điều của val/test theo seed, đúng per_type mỗi kiểu (SPEC 5.4)."""
    if len(article_ids) != per_type * len(TYPES):
        raise ValueError(f"cần đúng {per_type * len(TYPES)} Điều để chia {per_type}/{per_type}/{per_type}")
    types = [t for t in TYPES for _ in range(per_type)]
    random.Random(f"{seed}|eval-types").shuffle(types)
    return dict(zip(article_ids, types))


class _NameMin(str):
    """Khóa để max() chọn tên lĩnh vực NHỎ nhất theo Unicode khi hòa."""

    def __lt__(self, other):
        return str.__gt__(self, other)

    def __gt__(self, other):
        return str.__lt__(self, other)


def stratified_order(items: list[dict], seed) -> list[dict]:
    """Thứ tự ngẫu nhiên phân tầng theo lĩnh vực, có seed: mọi tiền tố của danh sách xấp xỉ đúng tỷ lệ lĩnh vực.
    Mỗi lĩnh vực xáo bằng Random(f"{seed}|{lĩnh vực}|order"); ở bước t chọn lĩnh vực có thiếu hụt lớn nhất
    (size_d * t / N - đã lấy_d); hòa: tên lĩnh vực theo Unicode."""
    by = defaultdict(list)
    for a in sorted(items, key=lambda a: a["article_id"]):
        by[a["domain"]].append(a)
    for d, lst in by.items():
        random.Random(f"{seed}|{d}|order").shuffle(lst)
    n, taken, out = len(items), {d: 0 for d in by}, []
    for t in range(1, n + 1):
        d = max((d for d in by if taken[d] < len(by[d])), key=lambda d: (Fraction(len(by[d]) * t, n) - taken[d], _NameMin(d)))
        out.append(by[d][taken[d]])
        taken[d] += 1
    return out


def plan_eval(pool: list[dict], per_type: int, reserve_per_type: int, seed) -> dict:
    """Val/test: 3*per_type Điều chính + 3*reserve_per_type Điều dự phòng (cùng split), ngẫu nhiên phân tầng theo lĩnh vực.
    Điều chính gán kiểu 50/50/50, Điều dự phòng gán đều từng kiểu (25 mỗi kiểu)."""
    n_main, n_res = per_type * len(TYPES), reserve_per_type * len(TYPES)
    if n_main + n_res > len(pool):
        raise InsufficientSourceError(f"cần {n_main + n_res} Điều (chính + dự phòng) nhưng chỉ có {len(pool)} Điều đủ điều kiện")
    main = stratified_sample(pool, n_main, seed)
    main_ids = {a["article_id"] for a in main}
    rest = [a for a in pool if a["article_id"] not in main_ids]
    reserve = stratified_sample(rest, n_res, f"{seed}|reserve")
    main_order = [a["article_id"] for a in main]
    res_order = [a["article_id"] for a in reserve]
    return {"article_ids": main_order, "reserve_ids": res_order,
            "types": assign_eval_types(main_order, per_type, seed),
            "reserve_types": assign_eval_types(res_order, reserve_per_type, f"{seed}|reserve")}
