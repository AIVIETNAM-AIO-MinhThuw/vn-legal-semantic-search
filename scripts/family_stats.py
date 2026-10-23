"""Thống kê cấu trúc họ văn bản (Task 1, SPEC 4.1) — CHỈ THỐNG KÊ; không split, không ghi group_id/splits.json.

Union-find trên toàn bộ `relationships` với 6 nhãn đã ánh xạ (config relations.mapping), trước khi lọc.
ID không có trong metadata là nút trung gian (SPEC 3.6, 4.1). Sau đó chỉ xét họ có >= 1 văn bản trong corpus
cuối cùng (docs_index.jsonl). Không đọc tham số split (ngưỡng buộc train, tỷ lệ train/val/test): các giá trị đó do
Task 2 tính trong scripts/split.py.

Chạy:  python -X utf8 scripts/family_stats.py --config configs/data.yaml
Đầu ra (reports/data_stats/after_filter/):
  family_stats.json          số họ, phân phối số văn bản/số Điều mỗi họ, họ lớn nhất, lĩnh vực chủ đạo, nút thiếu metadata
  family_sizes.csv           một dòng mỗi họ có văn bản trong corpus
  family_bridge_report.json  đường nối qua nút thiếu metadata của các họ có nút đó
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import yaml


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.size: dict[str, int] = {}

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # nén đường đi
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]


def quant(values: list[int]) -> dict:
    s = pd.Series(values)
    return {"min": int(s.min()), "median": float(s.median()), "p95": float(s.quantile(0.95)), "max": int(s.max())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    raw, proc = Path(cfg["paths"]["raw_dir"]), Path(cfg["processed"]["dir"])
    out = Path(cfg["processed"]["after_filter_dir"])
    mapping = cfg["relations"]["mapping"]

    meta = pd.read_parquet(raw / cfg["dataset"]["files"]["metadata"])
    meta_ids = set(meta["id"])
    rel = pd.read_parquet(raw / cfg["dataset"]["files"]["relationships"])
    rel = rel[rel["relationship"].isin(mapping)]
    rel = rel[rel["doc_id"].notna() & rel["other_doc_id"].notna()
              & (rel["doc_id"].astype(str).str.strip() != "") & (rel["other_doc_id"].astype(str).str.strip() != "")]

    uf = UnionFind()
    for a, b in zip(rel["doc_id"], rel["other_doc_id"]):
        uf.add(a)
        uf.add(b)
        uf.union(a, b)
    nodes = set(uf.parent)
    dangling = {n for n in nodes if n not in meta_ids}

    docs = [json.loads(l) for l in open(proc / "docs_index.jsonl", encoding="utf-8")]
    arts = [json.loads(l) for l in open(proc / "articles_index.jsonl", encoding="utf-8")]
    corpus_ids = {d["doc_id"] for d in docs}
    art_count = Counter(a["doc_id"] for a in arts)
    for d in docs:  # văn bản không có cạnh nào là một họ riêng
        uf.add(d["doc_id"])

    fam: dict[str, dict] = defaultdict(lambda: {"corpus_docs": [], "nodes": 0, "dangling": 0})
    for n in uf.parent:
        r = uf.find(n)
        fam[r]["nodes"] += 1
        fam[r]["dangling"] += int(n in dangling)
    dom_of = {d["doc_id"]: d["linh_vuc"] for d in docs}
    for d in docs:
        fam[uf.find(d["doc_id"])]["corpus_docs"].append(d["doc_id"])
    fam = {r: f for r, f in fam.items() if f["corpus_docs"]}  # chỉ họ có >= 1 văn bản trong corpus (SPEC 4.1)

    rows = []
    for r, f in fam.items():
        cnt = Counter(dom_of[x] for x in f["corpus_docs"])
        top = cnt.most_common()
        tied = [k for k, v in top if v == top[0][1]]
        rows.append({"corpus_docs": len(f["corpus_docs"]),
                     "corpus_articles": sum(art_count[x] for x in f["corpus_docs"]),
                     "nodes_total": f["nodes"], "dangling_nodes": f["dangling"],
                     "n_domains": len(cnt), "dominant_domain_tied": len(tied) > 1,
                     "dominant_domain_alphabetical": sorted(tied)[0], "_root": r})
    df = pd.DataFrame(rows).sort_values(["corpus_docs", "corpus_articles"], ascending=False).reset_index(drop=True)
    df.drop(columns="_root").to_csv(out / "family_sizes.csv", index=False, encoding="utf-8-sig")

    total_docs, total_arts = len(docs), sum(art_count.values())
    in_dangling_fam = sum(r["corpus_docs"] for r in rows if r["dangling_nodes"] > 0)
    r0 = df.iloc[0]
    largest = {"corpus_docs": int(r0["corpus_docs"]), "corpus_articles": int(r0["corpus_articles"]),
               "nodes_total": int(r0["nodes_total"]), "dangling_nodes": int(r0["dangling_nodes"]),
               "dominant_domain": r0["dominant_domain_alphabetical"],
               "domains": dict(Counter(dom_of[x] for x in fam[r0["_root"]]["corpus_docs"])),
               "corpus_doc_ids": sorted(fam[r0["_root"]]["corpus_docs"])}
    # --- Báo cáo đường nối qua ID thiếu metadata (chỉ mô tả; không cắt cạnh, không đổi mapping) ---
    adj: dict[str, set[str]] = defaultdict(set)
    edge_labels: dict[str, Counter] = defaultdict(Counter)
    for a, b, lab in zip(rel["doc_id"], rel["other_doc_id"], rel["relationship"]):
        if a != b:
            adj[a].add(b)
            adj[b].add(a)
            for x in (a, b):
                edge_labels[x][lab] += 1
    members: dict[str, list[str]] = defaultdict(list)
    for node in uf.parent:
        members[uf.find(node)].append(node)
    largest_root = df.iloc[0]["_root"]
    bridge = []
    for r in sorted(fam, key=lambda x: (-len(fam[x]["corpus_docs"]), x)):
        if fam[r]["dangling"] == 0:
            continue
        mem, dang = members[r], [n for n in members[r] if n in dangling]
        rest = set(mem) - set(dang)
        comps, seen = [], set()
        for start in sorted(rest):  # thành phần liên thông nếu bỏ nút ID thiếu (chỉ để đo mức phụ thuộc)
            if start in seen:
                continue
            comp, stack = set(), [start]
            while stack:
                u = stack.pop()
                if u in comp:
                    continue
                comp.add(u)
                stack.extend(v for v in adj[u] if v in rest and v not in comp)
            seen |= comp
            comps.append(comp)
        cd = sorted((len(c & corpus_ids) for c in comps), reverse=True)
        hubs = sorted(dang, key=lambda n: -len(adj[n]))[:5]
        bridge.append({
            "is_largest_family": r == largest_root, "corpus_docs": len(fam[r]["corpus_docs"]),
            "nodes_total": len(mem), "dangling_nodes": len(dang),
            "components_without_dangling_nodes": len(comps),
            "corpus_docs_per_component_desc_top5": cd[:5],
            "corpus_docs_outside_largest_component": int(sum(cd[1:])),
            "corpus_docs_adjacent_to_dangling": len({v for n in dang for v in adj[n] if v in corpus_ids}),
            "dangling_hubs": [{"id": n, "degree": len(adj[n]), "corpus_neighbors": len(adj[n] & corpus_ids),
                               "labels": dict(edge_labels[n])} for n in hubs],
        })
    (out / "family_bridge_report.json").write_text(json.dumps(bridge, ensure_ascii=False, indent=1), encoding="utf-8")

    info = {
        "note": "Chỉ thống kê. Không phải split; chưa ghi group_id. Không có ngưỡng cắt họ.",
        "edges_used": int(len(rel)), "nodes_in_graph": len(nodes), "dangling_nodes_in_graph": len(dangling),
        "components_in_graph": len({uf.find(n) for n in nodes}),
        "corpus_docs": total_docs, "corpus_articles": total_arts,
        "families_with_corpus_doc": len(df),
        "singleton_families_one_corpus_doc": int((df["corpus_docs"] == 1).sum()),
        "singleton_with_no_edge_at_all": int(sum(1 for d in docs if d["doc_id"] not in nodes)),
        "corpus_docs_per_family": quant(df["corpus_docs"].tolist()),
        "corpus_articles_per_family": quant(df["corpus_articles"].tolist()),
        "nodes_total_per_family": quant(df["nodes_total"].tolist()),
        "largest_family_share_of_docs": round(float(df["corpus_docs"].max()) / total_docs, 4),
        "largest_family_share_of_articles": round(float(df["corpus_articles"].max()) / total_arts, 4),
        "top5_families_share_of_articles": round(float(df["corpus_articles"].head(5).sum()) / total_arts, 4),
        "families_with_multiple_corpus_docs": int((df["corpus_docs"] > 1).sum()),
        "families_with_dangling_node": int((df["dangling_nodes"] > 0).sum()),
        "corpus_docs_in_families_with_dangling_node": int(in_dangling_fam),
        "families_with_domain_tie": int(df["dominant_domain_tied"].sum()),
        "families_with_more_than_one_domain": int((df["n_domains"] > 1).sum()),
        "dominant_domain_family_counts": df["dominant_domain_alphabetical"].value_counts().to_dict(),
        "largest_family": largest,
    }
    (out / "family_stats.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
