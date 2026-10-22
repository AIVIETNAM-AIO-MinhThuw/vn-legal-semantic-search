"""Lọc (SPEC 3.2) -> parse/chuẩn hóa (3.4-3.5) -> chunk (3.4). Chưa dedup, chưa split.

Chạy:  python -X utf8 scripts/prepare_data.py --config configs/data.yaml
Đầu ra: data/processed/{docs,articles,chunks}.jsonl, logs/{rejected.jsonl,long_sentence.jsonl,filter_counts.json}
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.chunk import chunk_article, make_prefix  # noqa: E402
from src.data.html_text import html_to_lines, normalize_line  # noqa: E402
from src.data.parse import article_reject_reason, parse_articles  # noqa: E402
from src.data.tokenizer import count_tokens, load_tokenizer  # noqa: E402


def jdump(f, obj) -> None:
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def apply_filters(meta: pd.DataFrame, flt: dict):
    """SPEC 3.2 bước 1-3 theo thứ tự cố định. Trả về (meta_đã_lọc, steps, removed); removed có 1 dòng/văn bản."""
    steps = [{"step": "0_all_metadata", "docs_before": len(meta), "docs_after": len(meta)}]
    removed: list[dict] = []
    rules = [("1_doc_type", "loai_van_ban", flt["doc_types"], "loai_van_ban not in config doc_types"),
             ("2_effect_status", "tinh_trang_hieu_luc", flt["effective_statuses"],
              "tinh_trang_hieu_luc not in config effective_statuses"),
             ("3_domain_exact", "linh_vuc", flt["domains"],
              "linh_vuc (exact string) not in config domains; includes null / Chưa phân loại")]
    for step, col, allowed, reason in rules:
        keep = meta[col].isin(allowed)
        for doc_id, val in zip(meta.loc[~keep, "id"], meta.loc[~keep, col]):
            removed.append({"doc_id": doc_id, "step": step, "reason": f"{col} not allowed",
                            "value": "<NULL>" if pd.isna(val) else " ".join(str(val).split())})
        steps.append({"step": step, "docs_before": len(meta), "docs_after": int(keep.sum()), "removed_reason": reason})
        meta = meta[keep.values]
    return meta, steps, removed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    flt, ck = cfg["filter"], cfg["chunk"]
    for k in ("doc_types", "effective_statuses", "domains"):
        if not flt.get(k):
            raise SystemExit(f"configs/data.yaml: filter.{k} chưa được điền (OI-10).")

    raw = Path(cfg["paths"]["raw_dir"])
    out_dir = Path(cfg["processed"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    Path(cfg["processed"]["rejected_log"]).parent.mkdir(parents=True, exist_ok=True)

    meta = pd.read_parquet(raw / cfg["dataset"]["files"]["metadata"])
    meta, steps, removed = apply_filters(meta, flt)
    # SPEC 3.7: mỗi bản ghi bị loại phải có dòng log (doc_id, bước, lý do, giá trị gốc).
    fo_path = Path(cfg["processed"]["filtered_out_log"])
    with open(fo_path, "w", encoding="utf-8", newline="\n") as fo:
        fo.write("doc_id\tstep\treason\tvalue\n")
        for r in removed:
            fo.write(f"{r['doc_id']}\t{r['step']}\t{r['reason']}\t{r['value']}\n")
    for st in steps[1:]:
        n_logged = sum(1 for r in removed if r["step"] == st["step"])
        if n_logged != st["docs_before"] - st["docs_after"]:
            raise SystemExit(f"Log {st['step']} không khớp số văn bản bị loại: {n_logged}")
    meta = meta.sort_values("id").reset_index(drop=True)
    selected = {r.id: r for r in meta.itertuples(index=False)}

    tok = load_tokenizer(cfg)
    rej_f = open(cfg["processed"]["rejected_log"], "w", encoding="utf-8")
    long_f = open(cfg["processed"]["long_sentence_log"], "w", encoding="utf-8")
    anom_f = open(Path(cfg["processed"]["rejected_log"]).parent / "parse_anomalies.jsonl", "w", encoding="utf-8")
    docs_f = open(out_dir / "docs.jsonl", "w", encoding="utf-8")
    arts_f = open(out_dir / "articles.jsonl", "w", encoding="utf-8")
    chunks_f = open(out_dir / "chunks.jsonl", "w", encoding="utf-8")

    rej_doc, rej_art = Counter(), Counter()
    pstats = Counter()
    n_docs_kept = n_arts = n_chunks = 0
    seen_content: set[str] = set()

    def process(doc_id: str, html: str | None) -> None:
        nonlocal n_docs_kept, n_arts, n_chunks
        m = selected[doc_id]
        title = normalize_line(m.title or "")
        if not title:
            rej_doc["missing_title"] += 1
            jdump(rej_f, {"level": "doc", "doc_id": doc_id, "reason": "missing_title"})
            return
        if html is None or not html.strip():
            rej_doc["empty_html"] += 1
            jdump(rej_f, {"level": "doc", "doc_id": doc_id, "reason": "empty_html"})
            return
        try:
            lines = html_to_lines(html, ck["table_cell_sep"])
        except Exception as e:  # parse lỗi
            rej_doc["html_parse_error"] += 1
            jdump(rej_f, {"level": "doc", "doc_id": doc_id, "reason": "html_parse_error", "detail": repr(e)[:200]})
            return
        parsed = parse_articles(lines)
        for k, v in parsed.stats.items():
            pstats[k] += int(v)
        pstats["docs_with_dup_numbers"] += int(parsed.stats["dup_numbers"] > 0)
        if (parsed.stats["dup_numbers"] or parsed.stats["appendix_cut"] or parsed.stats["ambiguous_quote"]
                or parsed.stats["straight_quote_article"]):
            nums = Counter(a.number for a in parsed.articles)
            jdump(anom_f, {"doc_id": doc_id, "n_articles": len(parsed.articles), "stats": parsed.stats,
                           "dup_numbers": sorted(k for k, v in nums.items() if v > 1)})
        if not parsed.articles:
            rej_doc["no_article"] += 1
            jdump(rej_f, {"level": "doc", "doc_id": doc_id, "reason": "no_article", "n_lines": len(lines)})
            return
        kept = []
        for seq, a in enumerate(parsed.articles, 1):
            aid = f"{doc_id}_{seq:03d}"
            why = article_reject_reason(a)
            if why is None:
                prefix = make_prefix(title, a.number, normalize_line(a.title))
                try:
                    chunks, long_s = chunk_article(tok, prefix, a.lines, ck["max_tokens"], ck["token_overlap"],
                                                   ck["sentence_overlap"])
                except ValueError as e:
                    why, chunks, long_s = "prefix_too_long", [], False
                    jdump(rej_f, {"level": "article", "doc_id": doc_id, "article_id": aid, "reason": why,
                                  "detail": str(e)})
                    rej_art[why] += 1
                    continue
                if long_s:
                    pstats["articles_with_long_sentence"] += 1
                    jdump(long_f, {"article_id": aid, "doc_id": doc_id})
                kept.append((aid, a, chunks))
            else:
                rej_art[why] += 1
                jdump(rej_f, {"level": "article", "doc_id": doc_id, "article_id": aid, "reason": why,
                              "number": a.number, "title": a.title[:120], "body_chars": len(a.body)})
        if not kept:
            rej_doc["no_valid_article"] += 1
            jdump(rej_f, {"level": "doc", "doc_id": doc_id, "reason": "no_valid_article",
                          "n_parsed_articles": len(parsed.articles)})
            return
        n_docs_kept += 1
        year = pd.to_datetime(m.ngay_ban_hanh, format="%d/%m/%Y", errors="coerce")
        jdump(docs_f, {"doc_id": doc_id, "title": title, "so_ky_hieu": m.so_ky_hieu, "loai_van_ban": m.loai_van_ban,
                       "linh_vuc": m.linh_vuc, "tinh_trang_hieu_luc": m.tinh_trang_hieu_luc,
                       "year": None if pd.isna(year) else int(year.year), "n_articles": len(kept),
                       "has_duplicate_article_numbers": parsed.stats["dup_numbers"] > 0})
        for aid, a, chunks in kept:
            n_arts += 1
            jdump(arts_f, {"article_id": aid, "doc_id": doc_id, "number": a.number, "title": normalize_line(a.title),
                           "body": a.body, "n_chunks": len(chunks)})
            for k, c in enumerate(chunks):
                n_chunks += 1
                jdump(chunks_f, {"chunk_id": f"{aid}#{k:02d}", "article_id": aid, "doc_id": doc_id,
                                 "chunk_index": k, "n_chunks": len(chunks), "kind": c.kind,
                                 "n_tokens": c.n_tokens, "text": c.text})

    pf = pq.ParquetFile(raw / cfg["dataset"]["files"]["content"])
    got: set[str] = set()
    for batch in pf.iter_batches(batch_size=500, columns=["id", "content_html"]):
        ids = batch.column("id").to_pylist()
        htmls = batch.column("content_html").to_pylist()
        for doc_id, h in zip(ids, htmls):
            if doc_id in selected and doc_id not in got:
                got.add(doc_id)
                process(doc_id, h)
    for doc_id in sorted(set(selected) - got):  # metadata không có dòng content
        rej_doc["empty_html"] += 1
        jdump(rej_f, {"level": "doc", "doc_id": doc_id, "reason": "empty_html", "detail": "no content row"})

    for f in (rej_f, long_f, anom_f, docs_f, arts_f, chunks_f):
        f.close()

    steps.append({"step": "4_empty_or_no_article", "docs_before": len(selected), "docs_after": n_docs_kept,
                  "removed_reason": dict(rej_doc)})
    steps.append({"step": "5_amendment_docs_kept", "docs_before": n_docs_kept, "docs_after": n_docs_kept,
                  "note": "văn bản sửa đổi/bổ sung/thay thế được giữ nếu qua bước 1-4 (SPEC 3.2)"})
    summary = {"steps": steps, "articles_kept": n_arts, "chunks": n_chunks,
               "articles_rejected": dict(rej_art), "parse_stats": dict(pstats)}
    Path(cfg["processed"]["filter_counts_log"]).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                           encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
