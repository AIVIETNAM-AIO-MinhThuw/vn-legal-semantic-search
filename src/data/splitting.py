"""Logic split theo SPEC 4.1 (phương án B). Hàm thuần, không đọc/ghi file: dùng chung cho scripts/split.py và test.

Mọi phép tính tỷ lệ dùng `fractions.Fraction` (không dùng số thực). Thứ tự tập luôn là train, val, test.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from fractions import Fraction

SPLITS = ("train", "val", "test")
ORDER = {s: i for i, s in enumerate(SPLITS)}


class StopSplit(Exception):
    """Ràng buộc không thỏa: dừng, báo người quyết định (SPEC 4.1, điều kiện dừng). `diag` là báo cáo chẩn đoán."""

    def __init__(self, reason: str, diag: dict | None = None):
        super().__init__(reason)
        self.reason, self.diag = reason, diag or {}


def to_fraction(x) -> Fraction:
    """0.05 -> 1/20 (từ chuỗi thập phân, không qua số thực nhị phân)."""
    return x if isinstance(x, Fraction) else Fraction(str(x))


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)  # gốc = id nhỏ nhất: kết quả không phụ thuộc thứ tự cạnh


def build_families(edges, corpus_doc_ids) -> dict[str, list[str]]:
    """Union-find trên TOÀN BỘ cạnh đã ánh xạ (kể cả văn bản đã bị lọc và ID thiếu metadata làm nút trung gian),
    rồi chỉ giữ các văn bản trong corpus cuối. Trả về {group_id: [doc_id đã sắp]}, group_id = min(doc_id) trong corpus
    theo thứ tự chuỗi Unicode (SPEC 4.1). Họ không có văn bản nào trong corpus bị bỏ."""
    uf = UnionFind()
    for a, b in edges:
        if any(x is None or x != x or str(x).strip() == "" for x in (a, b)):  # x != x: NaN
            raise ValueError("ID null/rỗng trong quan hệ là lỗi (SPEC 3.6)")
        uf.union(str(a), str(b))
    corpus = sorted({str(d) for d in corpus_doc_ids})
    for d in corpus:
        uf.add(d)  # văn bản không có cạnh là một họ riêng
    groups: dict[str, list[str]] = defaultdict(list)
    for d in corpus:
        groups[uf.find(d)].append(d)
    return {min(members): sorted(members) for members in groups.values()}


def dominant_domain(domains: list[str]) -> str:
    """Lĩnh vực xuất hiện nhiều nhất; hòa thì lĩnh vực đứng trước theo thứ tự chuỗi Unicode."""
    cnt = Counter(domains)
    best = max(cnt.values())
    return min(d for d, c in cnt.items() if c == best)


def compute_quotas(n: int, ratios: dict[str, Fraction]) -> dict[str, int]:
    """Chỉ tiêu theo tổng số họ bằng phần dư lớn nhất; hòa ưu tiên train, val, test."""
    if sum(ratios.values()) != 1:
        raise ValueError("tổng tỷ lệ phải bằng 1")
    exact = {s: n * ratios[s] for s in SPLITS}
    q = {s: exact[s].numerator // exact[s].denominator for s in SPLITS}
    left = n - sum(q.values())
    for s in sorted(SPLITS, key=lambda s: (-(exact[s] - q[s]), ORDER[s]))[:left]:
        q[s] += 1
    return q


def _floor(x: Fraction) -> int:
    return x.numerator // x.denominator


def _row_allocation(total: int, ideal: dict[str, Fraction]) -> dict[str, int]:
    x = {s: _floor(ideal[s]) for s in SPLITS}
    left = total - sum(x.values())
    for s in sorted(SPLITS, key=lambda s: (-(ideal[s] - x[s]), ORDER[s]))[:left]:
        x[s] += 1
    return x


def allocate(families: list[dict], ratios: dict, threshold, seed) -> tuple[dict[str, str], dict]:
    """families: [{'group_id', 'n_articles', 'domain'}]. Trả về ({group_id: split}, báo cáo).

    Raise StopSplit khi: F > Q_train; chỉ tiêu còn lại âm; một lĩnh vực không có họ nào trong val hoặc test.
    """
    ratios = {s: to_fraction(ratios[s]) for s in SPLITS}
    thr = to_fraction(threshold)
    ids = [f["group_id"] for f in families]
    if len(set(ids)) != len(ids):
        raise ValueError("group_id trùng")
    n = len(families)
    total = sum(f["n_articles"] for f in families)
    if n == 0 or total <= 0:
        raise StopSplit("không có họ hoặc không có Điều trong index", {"N": n, "A": total})
    Q = compute_quotas(n, ratios)
    forced = sorted((f for f in families if Fraction(f["n_articles"], total) > thr), key=lambda f: f["group_id"])
    F = len(forced)
    diag = {"N": n, "A": total, "Q": Q, "F": F, "threshold": str(thr),
            "forced": [{"group_id": f["group_id"], "article_share": str(Fraction(f["n_articles"], total))} for f in forced]}
    if F > Q["train"]:
        raise StopSplit(f"số họ buộc vào train F={F} lớn hơn chỉ tiêu train Q_train={Q['train']}", diag)
    q = {"train": Q["train"] - F, "val": Q["val"], "test": Q["test"]}
    rest = [f for f in families if f not in forced]
    R = len(rest)
    assert sum(q.values()) == R
    by_dom: dict[str, list[dict]] = defaultdict(list)
    for f in rest:
        by_dom[f["domain"]].append(f)
    domains = sorted(by_dom)  # thứ tự chuỗi Unicode
    ideal = {d: {s: Fraction(len(by_dom[d]) * q[s], R) for s in SPLITS} for d in domains} if R else {}
    x = {d: _row_allocation(len(by_dom[d]), ideal[d]) for d in domains}
    moves = []
    while True:
        col = {s: sum(x[d][s] for d in domains) for s in SPLITS}
        over = [s for s in SPLITS if col[s] > q[s]]
        under = [s for s in SPLITS if col[s] < q[s]]
        if not over and not under:
            break
        best = None
        for d in domains:
            for s_from in over:
                if x[d][s_from] <= 0:
                    continue
                for s_to in under:
                    delta = ((x[d][s_from] - 1 - ideal[d][s_from]) ** 2 + (x[d][s_to] + 1 - ideal[d][s_to]) ** 2
                             - (x[d][s_from] - ideal[d][s_from]) ** 2 - (x[d][s_to] - ideal[d][s_to]) ** 2)
                    key = (delta, d, ORDER[s_from], ORDER[s_to])
                    if best is None or key < best[0]:
                        best = (key, d, s_from, s_to)
        assert best is not None
        _, d, s_from, s_to = best
        x[d][s_from] -= 1
        x[d][s_to] += 1
        moves.append({"domain": d, "from": s_from, "to": s_to, "delta_sse": str(best[0][0])})
    missing = {s: [d for d in domains if x[d][s] == 0] for s in ("val", "test")}
    diag.update({"q": q, "R": R, "x": x, "ideal": {d: {s: str(v) for s, v in ideal[d].items()} for d in domains},
                 "column_moves": moves, "domains_missing_in": missing})
    if missing["val"] or missing["test"]:
        raise StopSplit("có lĩnh vực không có họ nào trong val hoặc test", diag)
    assignment = {f["group_id"]: "train" for f in forced}
    for d in domains:
        fams = sorted(f["group_id"] for f in by_dom[d])
        random.Random(f"{seed}|{d}").shuffle(fams)
        i = 0
        for s in SPLITS:
            for g in fams[i:i + x[d][s]]:
                assignment[g] = s
            i += x[d][s]
    assert len(assignment) == n
    return assignment, diag


def groups_hash(group_ids) -> str:
    return hashlib.sha256("\n".join(sorted(group_ids)).encode("utf-8")).hexdigest()
