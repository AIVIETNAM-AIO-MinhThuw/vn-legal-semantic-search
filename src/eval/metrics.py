"""Metric truy hồi cấp Điều (SPEC 11.2). Thuần Python, không phụ thuộc numpy.

qrels: {query_id: {article_id: grade}} (grade ≥ 1 là liên quan)
run:   {query_id: [article_id theo thứ tự rank]}
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

KS = (1, 3, 5, 10)


def read_trec_run(path) -> dict[str, list[str]]:
    rows = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            qid, _, aid, rank, _score, _tag = line.split()
            rows[qid].append((int(rank), aid))
    return {q: [a for _, a in sorted(v)] for q, v in rows.items()}


def per_query(ranked: list[str], rel: dict[str, int], depth: int = 10) -> dict[str, float]:
    ranked = ranked[:depth]
    n_rel = sum(1 for g in rel.values() if g >= 1)
    hits = [1 if rel.get(a, 0) >= 1 else 0 for a in ranked]
    out = {}
    for k in KS:
        h = sum(hits[:k])
        out[f"P@{k}"] = h / k
        out[f"R@{k}"] = h / n_rel if n_rel else 0.0
    first = next((i for i, x in enumerate(hits) if x), None)
    out["MRR@10"] = 0.0 if first is None else 1.0 / (first + 1)
    s, h = 0.0, 0
    for i, x in enumerate(hits):
        if x:
            h += 1
            s += h / (i + 1)
    out["MAP@10"] = s / min(n_rel, depth) if n_rel else 0.0
    dcg = sum((2 ** rel.get(a, 0) - 1) / math.log2(i + 2) for i, a in enumerate(ranked))
    ideal = sorted((g for g in rel.values()), reverse=True)[:depth]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    out["NDCG@10"] = dcg / idcg if idcg else 0.0
    out["rank_first_rel"] = float(first + 1) if first is not None else float("inf")
    return out


def evaluate(run: dict, qrels: dict, query_ids) -> tuple[dict, dict]:
    per = {}
    for q in query_ids:
        rel = qrels.get(q, {})
        if not any(g >= 1 for g in rel.values()):
            continue
        per[q] = per_query(run.get(q, []), rel)
    keys = [k for k in next(iter(per.values())) if k != "rank_first_rel"] if per else []
    mean = {k: sum(v[k] for v in per.values()) / len(per) for k in keys}
    mean["n_queries"] = len(per)
    return mean, per


def paired_bootstrap(a: dict, b: dict, metric: str, n: int = 10000, seed: int = 42) -> dict:
    """Paired bootstrap trên query chung; trả chênh lệch b - a, CI 95% và p hai phía."""
    qs = sorted(set(a) & set(b))
    d = [b[q][metric] - a[q][metric] for q in qs]
    obs = sum(d) / len(d)
    rng = random.Random(seed)
    m = len(d)
    stats = []
    for _ in range(n):
        stats.append(sum(d[rng.randrange(m)] for _ in range(m)) / m)
    stats.sort()
    lo, hi = stats[int(0.025 * n)], stats[int(0.975 * n) - 1]
    centered = [s - obs for s in stats]
    p = sum(1 for s in centered if abs(s) >= abs(obs)) / n
    return {"metric": metric, "n": m, "diff": obs, "ci95": [lo, hi], "p_value": p}
