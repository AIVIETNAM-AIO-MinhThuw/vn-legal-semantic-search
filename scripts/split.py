"""Split theo họ văn bản (SPEC 4.1, phương án B). Đã chạy thật một lần ngày 2026-10-24 (tạo `data/splits.json`, `split_report.json`).

Lệnh sinh lại (chỉ khi người duyệt đã xác nhận corpus; script không ghi đè `data/splits.json` đã có):
    python -X utf8 scripts/split.py --config configs/data.yaml --approved-by "<tên người xác nhận corpus>"

An toàn:
- Không có `--approved-by` thì dừng, không đọc hay ghi gì.
- Không ghi đè `splits.json` đã tồn tại (SPEC 4.1: không tạo lại/sửa sau khi có query test).
- Khi ràng buộc không thỏa (StopSplit): không ghi `splits.json`, chỉ ghi `split_stop_report.json`, thoát mã 2.
Đường dẫn đọc từ config (`split.output`, `processed.*`, `paths.*`, `relations.mapping`, `split.ratios`,
`split.force_train_article_share_gt`, `seed`).
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.splitting import SPLITS, StopSplit, allocate, build_families, compute_quotas, dominant_domain, groups_hash, to_fraction  # noqa: E402


def read_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def load_inputs(cfg: dict):
    proc, raw = Path(cfg["processed"]["dir"]), Path(cfg["paths"]["raw_dir"])
    docs = read_jsonl(proc / "docs_index.jsonl")
    n_articles = Counter(a["doc_id"] for a in read_jsonl(proc / "articles_index.jsonl"))
    rel = pd.read_parquet(raw / cfg["dataset"]["files"]["relationships"])
    mapping = cfg["relations"]["mapping"]
    rel = rel[rel["relationship"].isin(mapping)]
    edges = list(zip(rel["doc_id"], rel["other_doc_id"]))
    return docs, n_articles, edges


def run(cfg: dict, approved_by: str) -> dict:
    """Trả về báo cáo; ghi splits.json. Raise StopSplit khi ràng buộc không thỏa."""
    out = Path(cfg["split"]["output"])
    if out.exists():
        raise SystemExit(f"{out} đã tồn tại; không được tạo lại hoặc sửa splits.json (SPEC 4.1).")
    docs, n_articles, edges = load_inputs(cfg)
    domain_of = {d["doc_id"]: d["linh_vuc"] for d in docs}
    groups = build_families(edges, domain_of)
    families = [{"group_id": g, "n_articles": sum(n_articles[d] for d in m),
                 "domain": dominant_domain([domain_of[d] for d in m])} for g, m in groups.items()]
    assignment, diag = allocate(families, cfg["split"]["ratios"], cfg["split"]["force_train_article_share_gt"], cfg["seed"])
    doc_split = {d: assignment[g] for g, m in groups.items() for d in m}
    meta = {"rule": "SPEC 4.1 phương án B", "seed": cfg["seed"], "threshold": diag["threshold"], "N": diag["N"], "A": diag["A"],
            "Q": diag["Q"], "F": diag["F"], "ratios": {s: str(to_fraction(cfg["split"]["ratios"][s])) for s in SPLITS},
            "python": platform.python_version(), "group_ids_sha256": groups_hash(groups), "approved_by_corpus": approved_by}
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "splits": dict(sorted(assignment.items())), "members": dict(sorted(groups.items()))}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False), encoding="utf-8")
    report = {**diag, "docs_per_split": dict(Counter(doc_split.values())),
              "families_per_split": dict(Counter(assignment.values())),
              "articles_per_split": {s: sum(n_articles[d] for d, sp in doc_split.items() if sp == s) for s in SPLITS}}
    rep_dir = Path(cfg["processed"]["after_filter_dir"])
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "split_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--approved-by", help="tên người đã xác nhận corpus (bắt buộc để chạy)")
    args = ap.parse_args()
    if not args.approved_by or not args.approved_by.strip():
        raise SystemExit("Chưa chạy: split thật chỉ được chạy sau khi người xác nhận corpus. Truyền --approved-by '<tên>'.")
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    try:
        report = run(cfg, args.approved_by.strip())
    except StopSplit as e:
        rep_dir = Path(cfg["processed"]["after_filter_dir"])
        rep_dir.mkdir(parents=True, exist_ok=True)
        (rep_dir / "split_stop_report.json").write_text(
            json.dumps({"stop_reason": e.reason, **e.diag}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"DỪNG: {e.reason}. Không ghi splits.json. Xem split_stop_report.json.", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps({k: report[k] for k in ("N", "A", "Q", "F", "families_per_split", "docs_per_split", "articles_per_split")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
