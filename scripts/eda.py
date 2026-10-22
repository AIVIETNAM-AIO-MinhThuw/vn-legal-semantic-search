"""EDA phiên 1 (SPEC 3.7, 17): chỉ thống kê trên dữ liệu gốc. Không lọc, không parse, không chunk.

Chạy:  python scripts/eda.py --config configs/data.yaml
"""
from __future__ import annotations

import argparse
import html
import random
import re
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

# Tập con chỉ dùng để mô tả trong EDA (giá trị gốc chính xác); KHÔNG phải bộ lọc corpus.
EDA_CORE_TYPES = ["Luật", "Nghị định", "Thông tư"]
EDA_EFFECTIVE = "Còn hiệu lực"

TAG_RE = re.compile(r"<[^>]+>")
QUANTILES = [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0]


def html_to_rough_text(s: str) -> str:
    """Bóc tag thô để ước lượng độ dài / đếm mẫu. Không phải parser."""
    t = TAG_RE.sub("\n", s)
    t = unicodedata.normalize("NFC", html.unescape(t))
    return t


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    d = df if max_rows is None else df.head(max_rows)
    cols = list(d.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in d.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def value_counts_df(s: pd.Series, name: str) -> pd.DataFrame:
    vc = s.fillna("<NULL>").value_counts()
    return pd.DataFrame({name: vc.index, "n_docs": vc.values})


def schema_md(raw: Path, files: dict[str, str], cfg: dict) -> str:
    out = [
        "# Schema dataset",
        "",
        f"- Dataset: `{cfg['dataset']['name']}`",
        f"- Revision: `{cfg['dataset']['revision']}`",
        "- Config/split trên HF (theo README dataset): `metadata`/`data`, `content`/`data`, "
        "`relationships`/`data`; ngoài ra có `legacy_metadata`/`metadata` và `legacy_content`/`content` "
        "(bản cũ, schema khác, **không tải** trong phiên này).",
        "",
    ]
    for key, rel in files.items():
        pf = pq.ParquetFile(raw / rel)
        out += [f"## `{key}` — `{rel}`", "", f"- Số dòng: {pf.metadata.num_rows:,}",
                f"- Số row group: {pf.metadata.num_row_groups}", "", "| Cột | Kiểu Arrow |", "|---|---|"]
        for field in pf.schema_arrow:
            out.append(f"| `{field.name}` | `{field.type}` |")
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))

    raw = Path(cfg["paths"]["raw_dir"])
    files = cfg["dataset"]["files"]
    out = Path(cfg["paths"]["stats_dir"])
    samples_dir = Path(cfg["paths"]["samples_dir"])
    out.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    art_line_re = re.compile(r"(?m)^[ \t ]*" + cfg["eda"]["article_regex"])
    art_any_re = re.compile(cfg["eda"]["article_regex"])
    summary: list[str] = ["# EDA summary (phiên 1)", "",
                          f"Dataset `{cfg['dataset']['name']}` @ `{cfg['dataset']['revision']}`. "
                          "Chưa lọc, chưa parse. Mọi giá trị là giá trị gốc trong metadata.", ""]

    (out / "schema.md").write_text(schema_md(raw, files, cfg), encoding="utf-8")

    # ---------- metadata ----------
    meta = pd.read_parquet(raw / files["metadata"])
    n_meta = len(meta)
    summary += [f"## Metadata", "", f"- Số văn bản: {n_meta:,}; `id` duy nhất: {meta['id'].is_unique}; "
                f"`id` null: {meta['id'].isna().sum()}", ""]

    types = value_counts_df(meta["loai_van_ban"], "loai_van_ban")
    write_csv(types, out / "doc_type_counts.csv")
    summary += ["### Theo loại văn bản (`loai_van_ban`)", "", md_table(types), ""]

    status = value_counts_df(meta["tinh_trang_hieu_luc"], "tinh_trang_hieu_luc")
    write_csv(status, out / "effect_status_counts.csv")
    summary += ["### Theo tình trạng hiệu lực (`tinh_trang_hieu_luc`)", "", md_table(status), ""]

    xt = pd.crosstab(meta["loai_van_ban"].fillna("<NULL>"), meta["tinh_trang_hieu_luc"].fillna("<NULL>"))
    xt.to_csv(out / "doc_type_x_effect_status.csv", encoding="utf-8-sig")

    domains = value_counts_df(meta["linh_vuc"], "linh_vuc")
    domains["has_comma"] = domains["linh_vuc"].str.contains(",", regex=False)
    domains["has_semicolon"] = domains["linh_vuc"].str.contains(";", regex=False)
    write_csv(domains, out / "domain_counts_all.csv")
    nganh = value_counts_df(meta["nganh"], "nganh")
    write_csv(nganh, out / "nganh_counts_all.csv")
    summary += ["### Theo lĩnh vực (`linh_vuc`), toàn bộ", "",
                f"- Số giá trị gốc khác nhau: {len(domains):,} (file `domain_counts_all.csv`).",
                f"- Giá trị chứa dấu `,`: {int(domains['has_comma'].sum()):,} giá trị; "
                f"chứa `;`: {int(domains['has_semicolon'].sum()):,} giá trị.",
                f"- Cột `nganh` (ngành): {len(nganh):,} giá trị gốc (file `nganh_counts_all.csv`).", "",
                "Top 30:", "", md_table(domains[["linh_vuc", "n_docs"]], 30), ""]

    dt = pd.to_datetime(meta["ngay_ban_hanh"], format="%d/%m/%Y", errors="coerce")
    years = dt.dt.year.astype("Int64")
    yc = years.value_counts(dropna=False).sort_index()
    ydf = pd.DataFrame({"year": yc.index.astype("string").fillna("<unparsed>"), "n_docs": yc.values})
    write_csv(ydf, out / "year_counts.csv")
    n_bad_date = int(dt.isna().sum())
    summary += ["### Theo năm ban hành", "",
                f"- `ngay_ban_hanh` không parse được theo `dd/mm/yyyy` (hoặc null): {n_bad_date:,}",
                f"- Khoảng năm: {int(years.min())}–{int(years.max())} (file `year_counts.csv`)", ""]

    core_mask = meta["loai_van_ban"].isin(EDA_CORE_TYPES) & (meta["tinh_trang_hieu_luc"] == EDA_EFFECTIVE)
    core_ids = set(meta.loc[core_mask, "id"])
    meta_ids = set(meta["id"])

    # ---------- content (đọc theo batch) ----------
    pf = pq.ParquetFile(raw / files["content"])
    rows = []
    content_ids_seen: dict[str, int] = {}
    for batch in pf.iter_batches(batch_size=2000, columns=["id", "content_html"]):
        for doc_id, h in zip(batch.column("id").to_pylist(), batch.column("content_html").to_pylist()):
            content_ids_seen[doc_id] = content_ids_seen.get(doc_id, 0) + 1
            if h is None:
                rows.append((doc_id, None, None, None, None, "null"))
                continue
            if not h.strip():
                rows.append((doc_id, len(h), 0, 0, 0, "empty_string"))
                continue
            t = html_to_rough_text(h)
            tlen = len(re.sub(r"\s+", " ", t).strip())
            if doc_id in core_ids:
                n_line, n_any = len(art_line_re.findall(t)), len(art_any_re.findall(t))
            else:
                n_line = n_any = None
            rows.append((doc_id, len(h), tlen, n_line, n_any, "empty_text" if tlen == 0 else "ok"))
    cdf = pd.DataFrame(rows, columns=["id", "html_chars", "text_chars", "est_articles_line_start",
                                      "est_articles_any_mention", "content_state"])
    n_dup_content = sum(1 for v in content_ids_seen.values() if v > 1)
    cdf = cdf.drop_duplicates("id", keep="first")

    meta_c = meta[["id", "loai_van_ban", "tinh_trang_hieu_luc", "linh_vuc"]].merge(cdf, on="id", how="left")
    meta_c["content_state"] = meta_c["content_state"].fillna("missing_row")
    n_content_orphan = len(set(content_ids_seen) - meta_ids)

    def state_table(df: pd.DataFrame) -> pd.DataFrame:
        vc = df["content_state"].value_counts()
        return pd.DataFrame({"content_state": vc.index, "n_docs": vc.values,
                             "pct": (100 * vc.values / len(df)).round(3)})

    st_all, st_core = state_table(meta_c), state_table(meta_c[core_mask.values])
    st_all.insert(0, "scope", "all"); st_core.insert(0, "scope", "core_effective")
    st = pd.concat([st_all, st_core])
    write_csv(st, out / "content_missing_empty.csv")
    summary += ["## Nội dung HTML", "",
                f"- Số dòng content: {sum(content_ids_seen.values()):,}; id trùng trong content: {n_dup_content}; "
                f"id content không có trong metadata: {n_content_orphan}",
                "- `missing_row`: metadata không có dòng content; `null`/`empty_string`: HTML null/rỗng; "
                "`empty_text`: HTML có tag nhưng bóc tag ra không còn chữ.", "",
                md_table(st), ""]

    # ---------- tập core: L/NĐ/TT còn hiệu lực ----------
    core = meta_c[core_mask.values].copy()
    summary += ["## Tập mô tả: Luật / Nghị định / Thông tư, `Còn hiệu lực`", "",
                f"Chỉ để mô tả, **không phải bộ lọc đã chốt**. Loại văn bản đúng chuỗi {EDA_CORE_TYPES}, "
                f"`tinh_trang_hieu_luc == '{EDA_EFFECTIVE}'`. Số văn bản: {len(core):,}.", "",
                "Ước lượng số Điều: `est_articles_line_start` = số dòng bắt đầu bằng `Điều <số>` sau khi bóc tag "
                "(gần với số Điều thật hơn); `est_articles_any_mention` = mọi lần xuất hiện `Điều <số>` "
                "(gồm cả viện dẫn, chắc chắn đếm dư). Cả hai chỉ là ước lượng.", ""]

    ct = (core.groupby("loai_van_ban")
          .agg(n_docs=("id", "size"), n_with_text=("content_state", lambda s: int((s == "ok").sum())),
               est_articles_line_start=("est_articles_line_start", "sum"),
               docs_zero_article_line_start=("est_articles_line_start", lambda s: int((s == 0).sum())))
          .reset_index())
    write_csv(ct, out / "core_effective_by_type.csv")
    summary += ["### Theo loại", "", md_table(ct), ""]

    dom = (core.assign(linh_vuc=core["linh_vuc"].fillna("<NULL>"))
           .groupby("linh_vuc")
           .agg(n_docs=("id", "size"),
                n_luat=("loai_van_ban", lambda s: int((s == "Luật").sum())),
                n_nghi_dinh=("loai_van_ban", lambda s: int((s == "Nghị định").sum())),
                n_thong_tu=("loai_van_ban", lambda s: int((s == "Thông tư").sum())),
                n_with_text=("content_state", lambda s: int((s == "ok").sum())),
                est_articles_line_start=("est_articles_line_start", "sum"),
                est_articles_any_mention=("est_articles_any_mention", "sum"))
           .reset_index().sort_values(["n_docs", "linh_vuc"], ascending=[False, True]))
    for c in ["est_articles_line_start", "est_articles_any_mention"]:
        dom[c] = dom[c].fillna(0).astype(int)
    dom["is_multi_value_candidate"] = dom["linh_vuc"].str.contains(",", regex=False)
    write_csv(dom, out / "domain_counts_core_effective.csv")
    summary += ["### Theo lĩnh vực (giá trị gốc)", "",
                f"- Số giá trị `linh_vuc` gốc trong tập này: {len(dom):,} (đầy đủ ở `domain_counts_core_effective.csv`).",
                "", "Top 40 theo số văn bản:", "",
                md_table(dom.drop(columns=["est_articles_any_mention"]), 40), ""]

    ql = core.loc[core["content_state"] == "ok", ["html_chars", "text_chars"]].quantile(QUANTILES)
    ql.index = [f"p{int(q * 100)}" for q in QUANTILES]
    ql = ql.round(0).astype(int).reset_index().rename(columns={"index": "quantile"})
    write_csv(ql, out / "length_quantiles_core_effective.csv")
    write_csv(core[["id", "loai_van_ban", "linh_vuc", "html_chars", "text_chars", "est_articles_line_start",
                    "est_articles_any_mention", "content_state"]], out / "core_effective_docs.csv")
    lq_type = (core[core["content_state"] == "ok"].groupby("loai_van_ban")["text_chars"]
               .quantile([0.5, 0.95]).unstack().round(0).astype(int).reset_index()
               .rename(columns={0.5: "text_chars_p50", 0.95: "text_chars_p95"}))
    summary += ["### Phân phối độ dài (ký tự, văn bản có nội dung)", "",
                "`text_chars` = độ dài sau khi bóc tag thô và gộp khoảng trắng.", "",
                md_table(ql), "", md_table(lq_type), ""]

    # ---------- relationships ----------
    rel = pd.read_parquet(raw / files["relationships"])
    rel["src_ok"] = rel["doc_id"].isin(meta_ids)
    rel["dst_ok"] = rel["other_doc_id"].isin(meta_ids)
    rel["both_ok"] = rel["src_ok"] & rel["dst_ok"]
    rt = (rel.assign(relationship=rel["relationship"].fillna("<NULL>"))
          .groupby("relationship")
          .agg(n_edges=("both_ok", "size"), n_src_mapped=("src_ok", "sum"),
               n_dst_mapped=("dst_ok", "sum"), n_both_mapped=("both_ok", "sum"))
          .reset_index().sort_values("n_edges", ascending=False))
    rt["pct_both_mapped"] = (100 * rt["n_both_mapped"] / rt["n_edges"]).round(2)
    write_csv(rt, out / "relationship_types.csv")
    n_self = int((rel["doc_id"] == rel["other_doc_id"]).sum())
    n_dup_edges = int(rel.duplicated(["doc_id", "other_doc_id", "relationship"]).sum())
    n_null_ids = int(rel["doc_id"].isna().sum() + rel["other_doc_id"].isna().sum())
    summary += ["## Relationships", "",
                f"- Số cạnh: {len(rel):,}; số loại quan hệ gốc: {rt.shape[0]}",
                f"- Cạnh có cả hai đầu ánh xạ về metadata `id`: {int(rel['both_ok'].sum()):,} "
                f"({100 * rel['both_ok'].mean():.2f}%); chỉ đầu `doc_id`: {100 * rel['src_ok'].mean():.2f}%; "
                f"chỉ đầu `other_doc_id`: {100 * rel['dst_ok'].mean():.2f}%",
                f"- Self-loop: {n_self:,}; cạnh trùng (cùng 3 cột): {n_dup_edges:,}; ID null: {n_null_ids}",
                "", "**Toàn bộ** loại quan hệ gốc (chưa ánh xạ — nhóm xác nhận theo OI-10):", "",
                md_table(rt), ""]

    # ---------- mẫu HTML ----------
    rng = random.Random(cfg["seed"])
    pool = {t: sorted(core.loc[(core["loai_van_ban"] == t) & (core["content_state"] == "ok"), "id"])
            for t in EDA_CORE_TYPES}
    picks: list[tuple[str, str]] = []
    order = [EDA_CORE_TYPES[i % 3] for i in range(cfg["eda"]["n_samples"])]
    for t in order:
        cand = [i for i in pool[t] if i not in {p for _, p in picks}]
        picks.append((t, rng.choice(cand)))
    want = {p for _, p in picks}
    got: dict[str, str] = {}
    for batch in pf.iter_batches(batch_size=2000, columns=["id", "content_html"]):
        for doc_id, h in zip(batch.column("id").to_pylist(), batch.column("content_html").to_pylist()):
            if doc_id in want and doc_id not in got:
                got[doc_id] = h
    slugs = {"Luật": "luat", "Nghị định": "nghi_dinh", "Thông tư": "thong_tu"}
    srows = []
    for k, (t, i) in enumerate(picks, 1):
        fn = f"{k:02d}_{slugs[t]}_{i}.html"
        (samples_dir / fn).write_text(got[i], encoding="utf-8")
        m = meta.loc[meta["id"] == i].iloc[0]
        srows.append({"file": fn, "id": i, "loai_van_ban": t, "so_ky_hieu": m["so_ky_hieu"],
                      "title": m["title"], "linh_vuc": m["linh_vuc"]})
    sdf = pd.DataFrame(srows)
    write_csv(sdf, samples_dir / "samples_index.csv")
    summary += ["## Mẫu HTML", "",
                f"{len(sdf)} văn bản ngẫu nhiên (seed {cfg['seed']}) từ tập mô tả, xoay vòng Luật/Nghị định/Thông tư. "
                "Lưu nguyên HTML thô tại `samples/`, chỉ mục `samples/samples_index.csv`.", "",
                md_table(sdf[["file", "loai_van_ban", "so_ky_hieu"]]), ""]

    (out / "eda_summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"Done. Outputs in {out}")


if __name__ == "__main__":
    main()
