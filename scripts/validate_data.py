"""validate_data (SPEC 3.6): chạy SAU parse/chunk, TRƯỚC split. Dừng với lỗi nếu một kiểm tra thất bại.

Chạy:  python -X utf8 scripts/validate_data.py --config configs/data.yaml
Đầu ra khi mọi kiểm tra đạt: data/processed/{docs,articles,chunks}_index.jsonl (sau loại trùng),
        reports/data_stats/after_filter/* (gồm validate_report.json).
Khi có lỗi: chỉ ghi validate_report_failed.json; không ghi/ghi đè bất kỳ file đầu ra hợp lệ nào.
Không gom họ, không split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.tokenizer import count_tokens, load_tokenizer  # noqa: E402
from src.retrieval.e5_format import format_passage  # noqa: E402


def read_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def write_jsonl(p: Path, rows) -> None:
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def is_blank(x) -> bool:
    return x is None or (isinstance(x, float) and pd.isna(x)) or (isinstance(x, str) and not x.strip())


def quant(s: pd.Series) -> dict:
    return {"min": int(s.min()), "median": float(s.median()), "p95": float(s.quantile(0.95)), "max": int(s.max())}


def check_doc_article_counts(docs_idx: list[dict], arts_idx: list[dict]) -> list[str]:
    """doc_id có n_articles không khớp số Điều thật sự còn trong articles_index."""
    real = Counter(a["doc_id"] for a in arts_idx)
    return [d["doc_id"] for d in docs_idx if d["n_articles"] != real[d["doc_id"]]]


def check_article_chunk_counts(arts_idx: list[dict], chunks_idx: list[dict]) -> list[str]:
    real = Counter(c["article_id"] for c in chunks_idx)
    return [a["article_id"] for a in arts_idx if a["n_chunks"] != real[a["article_id"]]]


def validate(cfg: dict) -> dict:
    """Chạy mọi kiểm tra. Chỉ khi errors rỗng mới ghi đầu ra. Trả về info (có khóa 'errors')."""
    raw, proc = Path(cfg["paths"]["raw_dir"]), Path(cfg["processed"]["dir"])
    out = Path(cfg["processed"]["after_filter_dir"])
    out.mkdir(parents=True, exist_ok=True)
    limit, max_len = cfg["chunk"]["max_tokens"], cfg["tokenizer"]["max_length"]
    errors: list[str] = []
    info: dict = {}

    docs = read_jsonl(proc / "docs.jsonl")
    arts = read_jsonl(proc / "articles.jsonl")
    chunks = read_jsonl(proc / "chunks.jsonl")
    meta = pd.read_parquet(raw / cfg["dataset"]["files"]["metadata"])
    meta_ids = set(meta["id"])
    doc_ids = {d["doc_id"] for d in docs}
    art_by_id = {a["article_id"]: a for a in arts}

    # ---- 1. toàn vẹn khóa / chunk rỗng ----
    if len(art_by_id) != len(arts):
        errors.append("article_id trùng lặp trong articles.jsonl")
    if len(doc_ids) != len(docs):
        errors.append("doc_id trùng lặp trong docs.jsonl")
    bad_doc = [d["doc_id"] for d in docs if is_blank(d["doc_id"]) or d["doc_id"] not in meta_ids]
    if bad_doc:
        errors.append(f"{len(bad_doc)} doc_id thiếu hoặc không có trong metadata, ví dụ {bad_doc[:3]}")
    bad_art = [a["article_id"] for a in arts if is_blank(a["article_id"]) or is_blank(a["doc_id"])
               or a["doc_id"] not in doc_ids]
    if bad_art:
        errors.append(f"{len(bad_art)} Điều thiếu article_id/doc_id hoặc doc_id không có trong docs")
    bad_chunk_key = [c["chunk_id"] for c in chunks if is_blank(c.get("article_id")) or is_blank(c.get("doc_id"))
                     or c["article_id"] not in art_by_id or c["doc_id"] not in meta_ids
                     or art_by_id[c["article_id"]]["doc_id"] != c["doc_id"]]
    if bad_chunk_key:
        errors.append(f"{len(bad_chunk_key)} chunk có article_id/doc_id thiếu hoặc không khớp bảng Điều/metadata")
    empty_chunks = [c["chunk_id"] for c in chunks if is_blank(c["text"])]
    if empty_chunks:
        errors.append(f"{len(empty_chunks)} chunk rỗng")
    per_art = Counter(c["article_id"] for c in chunks)
    no_chunk = [aid for aid in art_by_id if per_art[aid] == 0]
    if no_chunk:
        errors.append(f"{len(no_chunk)} Điều không có chunk")

    # ---- 2. độ dài token: tính lại độc lập bằng tokenizer E5 ----
    tok = load_tokenizer(cfg)
    n_tok = [count_tokens(tok, c["text"]) for c in chunks]
    over = [c["chunk_id"] for c, n in zip(chunks, n_tok) if n > limit]
    if over:
        errors.append(f"{len(over)} chunk > {limit} token (kể cả tiền tố), ví dụ {over[:3]}")
    mism = [c["chunk_id"] for c, n in zip(chunks, n_tok) if n != c["n_tokens"]]
    if mism:
        errors.append(f"{len(mism)} chunk có n_tokens lưu khác số tính lại")
    over_passage = [c["chunk_id"] for c in chunks
                    if len(tok(format_passage(c["text"]), add_special_tokens=True)["input_ids"]) > max_len]
    if over_passage:
        errors.append(f"{len(over_passage)} passage > {max_len} token sau khi gắn 'passage: '")
    if n_tok:
        info["chunk_tokens"] = quant(pd.Series(n_tok))

    # ---- 3. loại trùng chính xác (SHA-1 nội dung Điều đã chuẩn hóa, không tính tiền tố) ----
    groups: dict[str, list[str]] = defaultdict(list)
    for a in arts:
        groups[hashlib.sha1(a["body"].encode("utf-8")).hexdigest()].append(a["article_id"])
    dup_map: dict[str, list[str]] = {}
    removed: set[str] = set()
    for ids in groups.values():
        if len(ids) > 1:
            ids = sorted(ids)  # bản đại diện = article_id nhỏ nhất theo thứ tự chuỗi (kỹ thuật, không pháp lý)
            dup_map[ids[0]] = ids[1:]
            removed.update(ids[1:])
    arts_idx = []
    for a in arts:
        if a["article_id"] in removed:
            continue
        a = dict(a)
        a["content_sha1"] = hashlib.sha1(a["body"].encode("utf-8")).hexdigest()
        a["duplicate_article_ids"] = dup_map.get(a["article_id"], [])
        arts_idx.append(a)
    chunks_idx = [c for c in chunks if c["article_id"] not in removed]
    real_n = Counter(a["doc_id"] for a in arts_idx)
    docs_idx = []
    for d in docs:
        if real_n[d["doc_id"]] == 0:
            continue
        d = dict(d)
        d["n_articles_before_dedup"] = d["n_articles"]
        d["n_articles"] = real_n[d["doc_id"]]  # tính lại theo dữ liệu sau dedup
        docs_idx.append(d)
    stale = check_doc_article_counts(docs_idx, arts_idx)
    if stale:
        errors.append(f"{len(stale)} văn bản có n_articles không khớp articles_index, ví dụ {stale[:3]}")
    stale_c = check_article_chunk_counts(arts_idx, chunks_idx)
    if stale_c:
        errors.append(f"{len(stale_c)} Điều có n_chunks không khớp chunks_index, ví dụ {stale_c[:3]}")
    if {a["doc_id"] for a in arts_idx} != {d["doc_id"] for d in docs_idx}:
        errors.append("tập doc_id của docs_index và articles_index không khớp")
    dup_cross_doc = sum(1 for k, v in dup_map.items() if len({art_by_id[x]["doc_id"] for x in [k] + v}) > 1)
    info["dedup"] = {"groups": len(dup_map), "articles_removed": len(removed),
                     "groups_spanning_multiple_docs": dup_cross_doc,
                     "docs_losing_all_articles": len(doc_ids) - len(docs_idx)}

    # ---- 4. relationships ----
    rel = pd.read_parquet(raw / cfg["dataset"]["files"]["relationships"])
    mapping = cfg["relations"]["mapping"]
    src_blank = int(rel["doc_id"].map(is_blank).sum())
    dst_blank = int(rel["other_doc_id"].map(is_blank).sum())
    lab_blank = int(rel["relationship"].map(is_blank).sum())
    if src_blank or dst_blank:
        errors.append(f"relationships: ID null/rỗng — doc_id {src_blank}, other_doc_id {dst_blank} (luôn là lỗi)")
    if lab_blank:
        errors.append(f"relationships: {lab_blank} cạnh có nhãn null/rỗng")
    valid = ~(rel["doc_id"].map(is_blank) | rel["other_doc_id"].map(is_blank))
    src_missing = int((valid & ~rel["doc_id"].isin(meta_ids)).sum())
    if src_missing:
        errors.append(f"relationships: {src_missing} cạnh có doc_id nguồn không có trong metadata (không thuộc ngoại lệ)")
    rel["dst_missing"] = valid & ~rel["other_doc_id"].isin(meta_ids)
    rel["self_loop"] = rel["doc_id"] == rel["other_doc_id"]
    rel["dup_edge"] = rel.duplicated(["doc_id", "other_doc_id", "relationship"], keep="first")
    rel["mapped_label"] = rel["relationship"].isin(mapping)
    labels_present = set(rel["relationship"].dropna())
    missing_labels = [l for l in mapping if l not in labels_present]
    if missing_labels:
        errors.append(f"nhãn trong config.relations.mapping không có trong dữ liệu: {missing_labels}")
    bad_vals = {v for v in mapping.values()} - {"sua_doi", "bo_sung", "thay_the"}
    if bad_vals:
        errors.append(f"giá trị ánh xạ không hợp lệ: {bad_vals}")

    def rel_stats(df: pd.DataFrame) -> dict:
        n = len(df)
        return {"edges": n, "dst_missing": int(df["dst_missing"].sum()),
                "dst_missing_pct": round(100 * df["dst_missing"].mean(), 3) if n else None,
                "distinct_missing_ids": int(df.loc[df["dst_missing"], "other_doc_id"].nunique()),
                "self_loops": int(df["self_loop"].sum()), "duplicate_edges": int(df["dup_edge"].sum())}

    per_label = []
    for lab, g in rel.groupby("relationship", dropna=False):
        r = rel_stats(g)
        r.update({"relationship": lab, "mapped_to": mapping.get(lab, "")})
        per_label.append(r)
    pl = pd.DataFrame(per_label)
    if len(pl):
        pl = pl.sort_values("edges", ascending=False)[
            ["relationship", "mapped_to", "edges", "dst_missing", "dst_missing_pct", "distinct_missing_ids",
             "self_loops", "duplicate_edges"]]
    corpus = {d["doc_id"] for d in docs_idx}
    touch = rel[rel["mapped_label"] & (rel["doc_id"].isin(corpus) | rel["other_doc_id"].isin(corpus))]
    info["relationships"] = {
        "all_edges": rel_stats(rel), "mapped_labels_edges": rel_stats(rel[rel["mapped_label"]]),
        "mapped_edges_touching_corpus": rel_stats(touch), "labels_total": int(rel["relationship"].nunique()),
        "null_or_empty_ids": {"doc_id": src_blank, "other_doc_id": dst_blank},
        "src_doc_id_missing_in_metadata": src_missing,
        "mapped_label_counts_by_class": rel[rel["mapped_label"]].assign(cls=lambda d: d["relationship"].map(mapping))
        .groupby("cls").size().to_dict()}

    # ---- 5. thống kê sau lọc (SPEC 3.7) ----
    D, A, C = pd.DataFrame(docs_idx), pd.DataFrame(arts_idx), pd.DataFrame(chunks_idx)
    if len(D) and len(A) and len(C):
        info["articles_per_doc"] = quant(A.groupby("doc_id").size())
        info["article_body_chars"] = quant(A["body"].str.len())
        info["chunks_per_article"] = quant(C.groupby("article_id").size())
        info["chunk_kinds"] = C["kind"].value_counts().to_dict()
    info["counts"] = {"docs_processed": len(docs), "docs_index": len(docs_idx), "articles_processed": len(arts),
                      "articles_index": len(arts_idx), "chunks_processed": len(chunks), "chunks_index": len(chunks_idx)}
    info["docs_with_duplicate_article_numbers"] = int(D["has_duplicate_article_numbers"].sum()) if len(D) else 0
    fc = json.loads(Path(cfg["processed"]["filter_counts_log"]).read_text(encoding="utf-8"))
    info["filter_steps"] = fc["steps"]
    info["articles_rejected"] = fc["articles_rejected"]
    info["parse_stats"] = fc["parse_stats"]
    info["errors"] = errors

    if errors:  # chỉ báo cáo lỗi; giữ nguyên mọi đầu ra hợp lệ của lần chạy trước
        (out / "validate_report_failed.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
        return info

    # ---- mọi kiểm tra đạt: công bố đầu ra ----
    write_jsonl(proc / "articles_index.jsonl", arts_idx)
    write_jsonl(proc / "chunks_index.jsonl", chunks_idx)
    write_jsonl(proc / "docs_index.jsonl", docs_idx)
    (out / "duplicate_groups.json").write_text(json.dumps(dup_map, ensure_ascii=False, indent=1), encoding="utf-8")
    pl.to_csv(out / "relationships_per_label.csv", index=False, encoding="utf-8-sig")
    for col, name in [("loai_van_ban", "type"), ("linh_vuc", "domain"), ("year", "year"),
                      ("tinh_trang_hieu_luc", "status")]:
        D[col].value_counts(dropna=False).rename_axis(col).reset_index(name="n_docs").to_csv(
            out / f"docs_by_{name}.csv", index=False, encoding="utf-8-sig")
    dm = D.merge(C.groupby("doc_id").size().rename("n_chunks"), left_on="doc_id", right_index=True)
    for col, name in [("linh_vuc", "domain"), ("loai_van_ban", "type")]:
        agg = dm.groupby(col).agg(n_docs=("doc_id", "size"), n_articles=("n_articles", "sum"),
                                  n_chunks=("n_chunks", "sum")).reset_index().sort_values("n_docs", ascending=False)
        agg.to_csv(out / f"after_filter_by_{name}.csv", index=False, encoding="utf-8-sig")
    C[["chunk_id", "n_tokens"]].to_csv(out / "chunk_token_lengths.csv", index=False)
    (out / "validate_report.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = out / "validate_report_failed.json"
    if failed.exists():
        failed.unlink()
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    info = validate(cfg)
    print(json.dumps({k: v for k, v in info.items() if k != "filter_steps"}, ensure_ascii=False, indent=1))
    if info["errors"]:
        print("\nVALIDATE_DATA FAILED:", *info["errors"], sep="\n - ")
        raise SystemExit(1)
    print("\nVALIDATE_DATA OK")


if __name__ == "__main__":
    main()
