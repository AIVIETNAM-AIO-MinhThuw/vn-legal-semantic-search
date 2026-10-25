"""Đánh giá cuối trên test (SPEC 11): bảng chính, biến thể, nhóm phân tích, kiểm định, latency, index size.

python -X utf8 scripts/evaluate.py --config configs/eval.yaml
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, statistics, sys, unicodedata
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.eval.metrics import evaluate, paired_bootstrap, read_trec_run  # noqa: E402

MAIN = ["P@1", "P@5", "R@5", "R@10", "MRR@10", "MAP@10", "NDCG@10"]


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def syl(s):  # SPEC 5.3: NFC, chữ thường, tách theo khoảng trắng/dấu câu
    return set(re.findall(r"\w+", unicodedata.normalize("NFC", s).lower()))


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def fmt(x): return f"{x:.4f}" if isinstance(x, float) else str(x)


def md_table(rows, cols):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(fmt(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True, type=Path)
    cfg = yaml.safe_load(ap.parse_args().config.read_text(encoding="utf-8"))
    out = Path(cfg["output"]); out.mkdir(parents=True, exist_ok=True)
    qrels = defaultdict(dict)
    for l in open(cfg["qrels"], encoding="utf-8"):
        r = json.loads(l); qrels[r["query_id"]][r["article_id"]] = r["label"]
    arts = {}
    for l in open(cfg["articles"], encoding="utf-8"):
        r = json.loads(l); arts[r["article_id"]] = r
    sets = {k: read_csv(v) for k, v in cfg["query_sets"].items()}
    # biến thể dùng chung qrels với query gốc (SPEC 5.5)
    for k in ("test_no_diacritic", "test_typo"):
        for q in sets[k]:
            qrels[q["query_id"]] = qrels[q["variant_of"]]
    runs, missing, per, means = {}, [], {}, {}
    for name, s in cfg["systems"].items():
        for qs in sets:
            p = Path("runs") / qs / s["run"] / "run.trec"
            if not p.exists():
                missing.append(str(p)); continue
            runs[(name, qs)] = read_trec_run(p)
            means[(name, qs)], per[(name, qs)] = evaluate(runs[(name, qs)], qrels, [q["query_id"] for q in sets[qs]])
    systems = [n for n in cfg["systems"] if (n, "test") in means]
    report = {"missing_runs": missing, "inputs": {"qrels": sha(cfg["qrels"]), **{k: sha(v) for k, v in cfg["query_sets"].items()}}}
    md = ["# Kết quả đánh giá (tự sinh bởi scripts/evaluate.py)", "",
          "Qrels: Điều nguồn của query (pseudo-qrels, nhãn 2); Điều khác coi là không liên quan. Độ sâu run = 10.", ""]

    # 1. Bảng chính trên test
    rows = []
    for n in systems:
        s = cfg["systems"][n]; summ = Path("runs") / "test" / s["run"] / "summary.json"
        lat = json.loads(summ.read_text(encoding="utf-8"))["query_seconds"] if summ.exists() else []
        r = {"Hệ thống": n, **{k: means[(n, "test")][k] for k in MAIN}, "n": means[(n, "test")]["n_queries"],
             "Latency p50 (ms)": statistics.median(lat) * 1000 if lat else "",
             "Latency mean (ms)": statistics.mean(lat) * 1000 if lat else "",
             "Index (MB)": dir_size(Path(s["index"])) / 2**20}
        rows.append(r)
    cols = ["Hệ thống", *MAIN, "n", "Latency p50 (ms)", "Latency mean (ms)", "Index (MB)"]
    md += ["## 1. Bảng chính — test", "", md_table(rows, cols), ""]
    report["main"] = rows

    # 2. Val (chọn cấu hình)
    if any((n, "val") in means for n in systems):
        vr = [{"Hệ thống": n, **{k: means[(n, "val")][k] for k in MAIN}} for n in systems if (n, "val") in means]
        md += ["## 2. Val", "", md_table(vr, ["Hệ thống", *MAIN]), ""]
    lr_rows = []
    for p in sorted(Path("models").glob("e5_ft_*/val_metrics.json")):
        v = json.loads(p.read_text(encoding="utf-8"))
        for h in v["history"]:
            lr_rows.append({"Cấu hình": v["variant"], "LR": f'{v["lr"]:g}', "Epoch": h["epoch"],
                            "NDCG@10": h["val"]["NDCG@10"], "MRR@10": h["val"]["MRR@10"], "R@10": h["val"]["R@10"],
                            "Chọn": "✓" if h["epoch"] == v["best_epoch"] else ""})
    if lr_rows:
        md += ["### Chọn learning rate / epoch trên val", "", md_table(lr_rows, ["Cấu hình", "LR", "Epoch", "NDCG@10", "MRR@10", "R@10", "Chọn"]), ""]
        report["lr_selection"] = lr_rows

    # 3. Kiểm định thống kê (paired bootstrap)
    bt = cfg["bootstrap"]; tests = []
    pairs = [(cfg["baseline"], n) for n in systems if n != cfg["baseline"]]
    pairs += [(cfg["zero_shot"], n) for n in systems if "fine-tune" in n]
    if "E5 fine-tune A" in systems and "E5 fine-tune B (+HN)" in systems:
        pairs.append(("E5 fine-tune A", "E5 fine-tune B (+HN)"))
    for a_, b_ in pairs:
        if (a_, "test") not in per or (b_, "test") not in per: continue
        for m in bt["metrics"]:
            r = paired_bootstrap(per[(a_, "test")], per[(b_, "test")], m, bt["n"], bt["seed"])
            tests.append({"So sánh": f"{b_} − {a_}", "Metric": m, "Δ": r["diff"],
                          "CI95": f'[{r["ci95"][0]:+.4f}, {r["ci95"][1]:+.4f}]', "p": r["p_value"]})
    md += ["## 3. Kiểm định paired bootstrap (10.000 lần, seed 42) — test", "", md_table(tests, ["So sánh", "Metric", "Δ", "CI95", "p"]), ""]
    report["significance"] = tests

    # 4. Biến thể: không dấu, lỗi chính tả
    vr = []
    for n in systems:
        r = {"Hệ thống": n}
        for qs, lab in (("test", "gốc"), ("test_no_diacritic", "không dấu"), ("test_typo", "lỗi gõ")):
            if (n, qs) in means:
                r[f"NDCG@10 {lab}"] = means[(n, qs)]["NDCG@10"]; r[f"R@10 {lab}"] = means[(n, qs)]["R@10"]
        vr.append(r)
    vcols = ["Hệ thống"] + [f"{m} {l}" for l in ("gốc", "không dấu", "lỗi gõ") for m in ("NDCG@10", "R@10")]
    md += ["## 4. Truy vấn không dấu và lỗi chính tả (test)", "", md_table(vr, vcols), ""]
    report["variants"] = vr

    # 5. Nhóm phân tích (SPEC 11.5 / Đề tài 8)
    test = {q["query_id"]: q for q in sets["test"]}
    def bucket_overlap(q):
        src = arts[q["source_article_id"]]; qs = syl(q["query"])
        ov = len(qs & syl(src["title"] + " " + src["body"])) / max(1, len(qs))
        return "overlap < 0.5 (diễn đạt khác/đồng nghĩa)" if ov < 0.5 else ("overlap 0.5–0.8" if ov < 0.8 else "overlap ≥ 0.8")
    lens = sorted(len(arts[q["source_article_id"]]["body"]) for q in test.values())
    q75 = lens[int(0.75 * len(lens))]
    groups = {
        "Kiểu query": lambda q: q["query_type"],
        "Độ trùng từ với Điều nguồn": bucket_overlap,
        "Độ dài query": lambda q: "rất ngắn (≤ 3 âm tiết)" if len(re.findall(r"\w+", q["query"])) <= 3 else "dài hơn",
        "Độ dài Điều nguồn (nhiều nội dung không liên quan)": lambda q: f"dài (≥ {q75} ký tự, top 25%)" if len(arts[q["source_article_id"]]["body"]) >= q75 else "ngắn hơn",
    }
    report["groups"] = {}
    for gname, fn in groups.items():
        buckets = defaultdict(list)
        for qid, q in test.items(): buckets[fn(q)].append(qid)
        rows = []
        for b in sorted(buckets):
            r = {"Nhóm": b, "n": len(buckets[b])}
            for n in systems:
                pq = per[(n, "test")]; ids = [x for x in buckets[b] if x in pq]
                r[n] = sum(pq[x]["NDCG@10"] for x in ids) / max(1, len(ids))
            rows.append(r)
        md += [f"## 5. NDCG@10 theo nhóm — {gname}", "", md_table(rows, ["Nhóm", "n", *systems]), ""]
        report["groups"][gname] = rows

    # 6. Dense kém hơn BM25
    base = cfg["baseline"]; cases = {}
    for n in systems:
        if n == base: continue
        pa, pb = per[(base, "test")], per[(n, "test")]
        worse = [q for q in pa if pb[q]["rank_first_rel"] > pa[q]["rank_first_rel"]]
        better = [q for q in pa if pb[q]["rank_first_rel"] < pa[q]["rank_first_rel"]]
        cases[n] = {"dense_worse": len(worse), "dense_better": len(better), "tie": len(pa) - len(worse) - len(better)}
        with open(out / f"dense_worse_than_bm25__{cfg['systems'][n]['run']}.jsonl", "w", encoding="utf-8") as f:
            for q in sorted(worse):
                t = test[q]; f.write(json.dumps({"query_id": q, "query": t["query"], "query_type": t["query_type"],
                    "source_article_id": t["source_article_id"], "source_title": arts[t["source_article_id"]]["title"],
                    "bm25_rank": pa[q]["rank_first_rel"], "dense_rank": pb[q]["rank_first_rel"],
                    "bm25_top3": runs[(base, "test")].get(q, [])[:3], "dense_top3": runs[(n, "test")].get(q, [])[:3]},
                    ensure_ascii=False, default=str) + "\n")
    rows = [{"Hệ thống": n, "Kém hơn BM25": c["dense_worse"], "Tốt hơn BM25": c["dense_better"], "Hòa": c["tie"]} for n, c in cases.items()]
    md += ["## 6. Số query dense xếp Điều nguồn thấp hơn BM25 (test)", "",
           md_table(rows, ["Hệ thống", "Kém hơn BM25", "Tốt hơn BM25", "Hòa"]), "",
           "Danh sách chi tiết: `dense_worse_than_bm25__<system>.jsonl` (rank = inf: không có trong top-10).", ""]
    report["dense_vs_bm25"] = cases
    if missing:
        md += ["## Run còn thiếu", "", *[f"- `{m}`" for m in missing], ""]
    (out / "results.md").write_text("\n".join(md), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    with open(out / "per_query_test.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["system", "query_id", *MAIN, "rank_first_rel"])
        for n in systems:
            for q, v in sorted(per[(n, "test")].items()):
                w.writerow([n, q, *[f"{v[k]:.6f}" for k in MAIN], v["rank_first_rel"]])
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4))
        ms = ["R@10", "MRR@10", "NDCG@10"]; w_ = 0.8 / len(systems)
        for i, n in enumerate(systems):
            ax.bar([j + i * w_ for j in range(len(ms))], [means[(n, "test")][m] for m in ms], w_, label=n)
        ax.set_xticks([j + 0.4 - w_ / 2 for j in range(len(ms))]); ax.set_xticklabels(ms); ax.set_ylim(0, 1)
        ax.legend(fontsize=8); ax.set_title("Test set"); fig.tight_layout(); fig.savefig(out / "main_test.png", dpi=150)
    except ImportError:
        pass
    print((out / "results.md").read_text(encoding="utf-8")[:3000])


if __name__ == "__main__":
    main()
