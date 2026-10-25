"""Tạo qrels giả lập theo Điều nguồn (pseudo-qrels, phương án nhãn cơ bản).

Quy tắc tất định, không gọi API, không dùng điểm hay độ trùng từ để gán nhãn positive:
  - positive (2): Điều nguồn của query; cộng các Điều có cùng `content_sha1` với Điều nguồn.
  - hard negative (0, giả định): ứng viên top-k của BM25 S1₀ / E5 S2 (run.trec) KHÔNG thuộc cùng văn bản,
    cùng họ văn bản hay cùng hash nội dung với Điều nguồn. Chỉ là giả định 0; chưa ai chấm.
  - irrelevant (0, giả định): n Điều ngẫu nhiên khác họ văn bản, seed cố định theo (seed, query_id).
  - mọi Điều khác: chưa chấm (không ghi vào qrels).

Họ văn bản: lấy ánh xạ doc -> group từ `members` của data/splits.json (cùng code union-find, SPEC 4.1);
KHÔNG đọc nhãn split trong file đó.

Chạy:
  python -X utf8 scripts/build_source_qrels.py --queries data/interim/full_v2/queries_v2.csv \
      --output data/interim/source_qrels_v1
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = "source-qrels-v1"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_jsonl(p: Path):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def read_run(p: Path) -> dict[str, list[tuple[int, str]]]:
    out = defaultdict(list)
    with open(p, encoding="utf-8") as f:
        for line in f:
            qid, _, aid, rank, _score, _tag = line.split()
            out[qid].append((int(rank), aid))
    return {q: sorted(v) for q, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", required=True, type=Path)
    ap.add_argument("--articles", default=Path("data/processed/articles_index.jsonl"), type=Path)
    ap.add_argument("--families", default=Path("data/splits.json"), type=Path)
    ap.add_argument("--runs", nargs="+", type=Path,
                    default=[Path("data/interim/full_v2/bm25_s10/run.trec"),
                             Path("data/interim/full_v2/e5_s2/run.trec")])
    ap.add_argument("--hard-depth", type=int, default=10)
    ap.add_argument("--n-random", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()

    if a.output.exists():
        sys.exit(f"Output đã tồn tại, không ghi đè: {a.output}")

    articles = {r["article_id"]: r for r in read_jsonl(a.articles)}
    by_hash = defaultdict(set)
    for aid, r in articles.items():
        by_hash[r["content_sha1"]].add(aid)
    members = json.loads(a.families.read_text(encoding="utf-8"))["members"]
    doc_group = {d: g for g, docs in members.items() for d in docs}
    missing_group = sorted({r["doc_id"] for r in articles.values()} - doc_group.keys())
    if missing_group:
        sys.exit(f"{len(missing_group)} văn bản trong corpus không có họ: {missing_group[:5]}")

    runs = {p.parent.name: read_run(p) for p in a.runs}
    with open(a.queries, encoding="utf-8-sig", newline="") as f:
        queries = list(csv.DictReader(f))
    all_ids = sorted(articles)

    qrels, negs, errors = [], [], []
    stats = Counter()
    for q in queries:
        qid, src = q["query_id"], q["source_article_id"]
        if src not in articles:
            errors.append({"query_id": qid, "error": "source_article_id không có trong corpus", "source_article_id": src})
            continue
        s = articles[src]
        s_doc, s_group = s["doc_id"], doc_group[s["doc_id"]]
        if q.get("source_group_id") and q["source_group_id"] != s_group:
            stats["source_group_mismatch_csv"] += 1
        pos = sorted(by_hash[s["content_sha1"]])
        for aid in pos:
            qrels.append({"query_id": qid, "article_id": aid, "label": 2,
                          "label_source": "source_article" if aid == src else "source_content_duplicate"})
        stats["positives"] += len(pos)
        stats["queries_with_dup_positive"] += len(pos) > 1

        excl = set(pos)
        def ok(aid: str) -> bool:
            r = articles[aid]
            return aid not in excl and r["doc_id"] != s_doc and doc_group[r["doc_id"]] != s_group

        hard = {}
        for sysname, run in runs.items():
            ranked = run.get(qid)
            if ranked is None:
                errors.append({"query_id": qid, "error": f"thiếu trong run {sysname}"})
                continue
            src_rank = next((r for r, aid in ranked if aid in excl), None)
            stats[f"{sysname}_source_in_top{a.hard_depth}"] += src_rank is not None
            for rank, aid in ranked[: a.hard_depth]:
                if ok(aid):
                    hard.setdefault(aid, []).append({"system": sysname, "rank": rank})
        for aid in sorted(hard):
            negs.append({"query_id": qid, "article_id": aid, "label": 0,
                         "label_source": "assumed_hard_negative", "origins": hard[aid]})
        stats["hard_negatives"] += len(hard)
        stats["queries_without_hard_negative"] += not hard

        rng = random.Random(f"{a.seed}:{qid}")
        pool = [aid for aid in all_ids if ok(aid) and aid not in hard]
        for aid in sorted(rng.sample(pool, a.n_random)):
            negs.append({"query_id": qid, "article_id": aid, "label": 0,
                         "label_source": "assumed_random_negative", "origins": []})
        stats["random_negatives"] += a.n_random
        stats["queries"] += 1

    a.output.mkdir(parents=True)
    def dump(name, rows):
        with open(a.output / name, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    dump("qrels.jsonl", qrels)
    dump("negatives.jsonl", negs)
    dump("errors.jsonl", errors)
    with open(a.output / "qrels.trec", "w", encoding="utf-8", newline="\n") as f:
        for r in qrels:
            f.write(f'{r["query_id"]} 0 {r["article_id"]} {r["label"]}\n')
    summary = {
        "version": VERSION,
        "created": datetime.now(timezone.utc).isoformat(),
        "params": {"hard_depth": a.hard_depth, "n_random": a.n_random, "seed": a.seed},
        "inputs": {str(p): sha256(p) for p in [a.queries, a.articles, a.families, *a.runs]},
        "n_input_queries": len(queries),
        "stats": dict(stats),
        "n_errors": len(errors),
        "outputs": {n: sha256(a.output / n) for n in ("qrels.jsonl", "qrels.trec", "negatives.jsonl", "errors.jsonl")},
    }
    (a.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["stats"], ensure_ascii=False, indent=2), "errors:", len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
