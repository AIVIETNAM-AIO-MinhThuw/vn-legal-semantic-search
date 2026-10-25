"""Split dataset query (SPEC 4.2, OI-12 phương án (a) mở rộng) — tất định, seed 42.

Đơn vị chia = thành phần liên thông nối các query:
  - cùng `source_article_id` (3 kiểu query của một Điều không bị tách sang split khác nhau);
  - cùng `exact_group_id` (trùng nguyên văn đã gộp);
  - cặp `likely_same_intent` trong bản review trùng ý (dup_group_id).
Phân tầng theo lĩnh vực của văn bản nguồn; tỷ lệ 80/10/10 tính theo số query.
Query pilot luôn vào train (SPEC 10.4).
Đầu ra: data/splits_v2/{query_splits.json, overlap_report.json}. Không ghi đè.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}


class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b: self.p[max(a, b)] = min(a, b)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=Path, default=Path("data/interim/full_v2/queries_v2.csv"))
    ap.add_argument("--near-dup", type=Path, default=Path(
        "data/interim/query_processing_v2/near_duplicate_review_v2_DRAFT.csv"))
    ap.add_argument("--pilot", type=Path, default=Path("data/interim/pilot_v2/pilot_queries_v2.csv"))
    ap.add_argument("--qrels", type=Path, default=Path("data/interim/source_qrels_v1/qrels.jsonl"))
    ap.add_argument("--articles", type=Path, default=Path("data/processed/articles_index.jsonl"))
    ap.add_argument("--families", type=Path, default=Path("data/splits.json"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", type=Path, default=Path("data/splits_v2"))
    a = ap.parse_args()
    if a.output.exists():
        sys.exit(f"Output đã tồn tại: {a.output}")

    with open(a.queries, encoding="utf-8-sig", newline="") as f:
        Q = {r["query_id"]: r for r in csv.DictReader(f)}
    with open(a.pilot, encoding="utf-8-sig", newline="") as f:
        pilot = {r["query_id"] for r in csv.DictReader(f)}
    uf = UF()
    for qid, r in Q.items():
        uf.find("q:" + qid)
        uf.union("q:" + qid, "a:" + r["source_article_id"])
        if r.get("exact_group_id"):
            uf.union("q:" + qid, "x:" + r["exact_group_id"])
    dup_pairs = 0
    with open(a.near_dup, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["claude_suggestion"] == "likely_same_intent" and r["query_id_a"] in Q and r["query_id_b"] in Q:
                uf.union("q:" + r["query_id_a"], "q:" + r["query_id_b"]); dup_pairs += 1
    units = defaultdict(list)
    for qid in Q:
        units[uf.find("q:" + qid)].append(qid)
    unit_ids = {u: "U" + hashlib.sha1(",".join(sorted(m)).encode()).hexdigest()[:10] for u, m in units.items()}

    by_field = defaultdict(list)
    forced = {}
    for u, members in units.items():
        fields = Counter(Q[q]["field"] for q in members)
        field = sorted(fields.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        by_field[field].append(u)
        if pilot & set(members):
            forced[u] = "train"
    rng = random.Random(a.seed)
    assign = {}
    for field in sorted(by_field):
        us = sorted(by_field[field], key=lambda u: unit_ids[u])
        rng.shuffle(us)
        total = sum(len(units[u]) for u in us)
        got = Counter()
        for u in us:
            if u in forced:
                s = forced[u]
            else:
                s = max(RATIOS, key=lambda k: (RATIOS[k] * total - got[k], k == "train"))
            assign[u] = s; got[s] += len(units[u])

    qsplit = {q: assign[u] for u, m in units.items() for q in m}
    qunit = {q: unit_ids[u] for u, m in units.items() for q in m}

    # Báo cáo chồng lấn (SPEC 4.3)
    arts = {}
    with open(a.articles, encoding="utf-8") as f:
        for l in f:
            r = json.loads(l); arts[r["article_id"]] = r
    members = json.loads(a.families.read_text(encoding="utf-8"))["members"]
    doc_group = {d: g for g, ds in members.items() for d in ds}
    pos = defaultdict(set)
    with open(a.qrels, encoding="utf-8") as f:
        for l in f:
            r = json.loads(l)
            if r["label"] >= 1: pos[r["query_id"]].add(r["article_id"])
    sets = {s: defaultdict(set) for s in RATIOS}
    for q, s in qsplit.items():
        sa = Q[q]["source_article_id"]
        sets[s]["source_article"].add(sa)
        sets[s]["source_doc"].add(arts[sa]["doc_id"])
        sets[s]["source_group"].add(doc_group[arts[sa]["doc_id"]])
        sets[s]["positive_article"] |= pos[q]
        sets[s]["positive_hash"] |= {arts[x]["content_sha1"] for x in pos[q]}
        sets[s]["unit"].add(qunit[q])
    errors = []
    for k in ("unit", "source_article"):
        for s1 in RATIOS:
            for s2 in RATIOS:
                if s1 < s2 and sets[s1][k] & sets[s2][k]:
                    errors.append(f"{k} chung giữa {s1}/{s2}: {len(sets[s1][k] & sets[s2][k])}")
    if pilot - {q for q, s in qsplit.items() if s == "train"} - (pilot - Q.keys()):
        errors.append("query pilot không nằm trong train")
    overlap = {}
    for s1, s2 in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap[f"{s1}-{s2}"] = {
            k: {"shared": len(sets[s1][k] & sets[s2][k]),
                f"rate_of_{s2}": round(len(sets[s1][k] & sets[s2][k]) / max(1, len(sets[s2][k])), 4)}
            for k in ("source_doc", "source_group", "positive_article", "positive_hash")}
    counts = Counter(qsplit.values())
    report = {
        "rule": "unit = source_article ∪ exact_group ∪ likely_same_intent; stratify by field; 80/10/10 by queries",
        "seed": a.seed, "n_queries": len(Q), "n_units": len(units), "near_dup_pairs_merged": dup_pairs,
        "counts": dict(counts), "ratios": {k: round(v / len(Q), 4) for k, v in counts.items()},
        "by_field": {f: dict(Counter(qsplit[q] for q in Q if Q[q]["field"] == f)) for f in sorted(by_field)},
        "by_type": {t: dict(Counter(qsplit[q] for q in Q if Q[q]["query_type"] == t)) for t in ("natural", "scenario", "keyword")},
        "pilot_in_train": len(pilot & Q.keys()),
        "overlap": overlap, "errors": errors,
        "inputs": {str(p): sha(p) for p in (a.queries, a.near_dup, a.pilot, a.qrels, a.articles, a.families)},
    }
    a.output.mkdir(parents=True)
    out = {"meta": {k: report[k] for k in ("rule", "seed", "n_queries", "counts")},
           "query_split": dict(sorted(qsplit.items())), "query_unit": dict(sorted(qunit.items()))}
    (a.output / "query_splits.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    report["query_splits_sha256"] = sha(a.output / "query_splits.json")
    (a.output / "overlap_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("counts", "ratios", "n_units", "near_dup_pairs_merged", "pilot_in_train", "errors", "overlap", "by_type")}, ensure_ascii=False, indent=1))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
