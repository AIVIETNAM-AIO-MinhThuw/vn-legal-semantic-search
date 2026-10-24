"""check_leakage theo SPEC 4.3. Dừng với lỗi (mã thoát 1) nếu:
  1. một `group_id` xuất hiện ở hơn một split (hoặc một văn bản thuộc hơn một họ, khóa JSON lặp, split không hợp lệ);
  2. hash nội dung của một Điều train trùng với hash của một Điều val hoặc test (yêu cầu = 0). "Điều" là bản đại diện
     trong index sau loại trùng (dữ liệu thực sự dùng; SPEC 4.3). Kết luận chỉ áp dụng cho trùng nội dung CHÍNH XÁC, không loại
     trừ near-duplicate. Nhóm trùng có các bản gốc thuộc nhiều split được báo RIÊNG (không phải lỗi: bản đã bị loại khỏi index
     không là nguồn query/positive/negative/chunk/run/qrels);
  3. (khi truyền --queries) Điều nguồn của một query thuộc split khác split của query.
Số liệu chồng lấn luôn được ghi ra file để người xác nhận (SPEC 4.3: không chỉ dựa vào thông báo "không có leakage").

Chạy:  python -X utf8 scripts/check_leakage.py --config configs/data.yaml [--queries runs/queries_train.jsonl ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

SPLITS = ("train", "val", "test")


def read_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_splits(path: Path) -> tuple[dict, list[str]]:
    """Đọc splits.json, ghi nhận khóa lặp trong cùng một đối tượng (vd. group_id xuất hiện hai lần)."""
    dups: list[str] = []

    def hook(pairs):
        keys = [k for k, _ in pairs]
        dups.extend(k for k, c in Counter(keys).items() if c > 1)
        return dict(pairs)

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=hook), dups


def doc_of_article(article_id: str) -> str:
    return article_id.rsplit("_", 1)[0]


def check_leakage(splits_obj: dict, duplicate_keys: list[str], docs: list[dict], articles: list[dict], queries: list[dict]) -> dict:
    errors: list[str] = []
    split_of_group = splits_obj["splits"]
    members = splits_obj["members"]
    bad_split = sorted(g for g, s in split_of_group.items() if s not in SPLITS)
    if duplicate_keys:
        errors.append(f"khóa lặp trong splits.json (group_id có thể xuất hiện ở hơn một split): {sorted(set(duplicate_keys))[:5]}")
    if bad_split:
        errors.append(f"{len(bad_split)} group_id có split không hợp lệ")
    if set(split_of_group) != set(members):
        errors.append("tập group_id của `splits` và `members` không khớp")
    group_of_doc: dict[str, list[str]] = defaultdict(list)
    for g, ms in members.items():
        for d in ms:
            group_of_doc[d].append(g)
    multi = sorted(d for d, gs in group_of_doc.items() if len(gs) > 1)
    if multi:
        errors.append(f"{len(multi)} văn bản thuộc hơn một họ (nên ở hơn một split), ví dụ {multi[:3]}")
    corpus = {d["doc_id"] for d in docs}
    uncovered, extra = sorted(corpus - set(group_of_doc)), sorted(set(group_of_doc) - corpus)
    if uncovered:
        errors.append(f"{len(uncovered)} văn bản trong corpus không thuộc họ nào trong splits.json")
    if extra:
        errors.append(f"{len(extra)} văn bản trong splits.json không có trong corpus")
    doc_split = {d: split_of_group.get(gs[0]) for d, gs in group_of_doc.items()}

    # --- trùng hash giữa train và val/test ---
    by_hash: dict[str, Counter] = defaultdict(Counter)
    by_hash_index_only: dict[str, Counter] = defaultdict(Counter)
    for a in articles:
        h = a.get("content_sha1") or hashlib.sha1(a["body"].encode("utf-8")).hexdigest()
        s = doc_split.get(a["doc_id"])
        by_hash[h][s] += 1
        by_hash_index_only[h][s] += 1
        for dup in a.get("duplicate_article_ids", []):  # bản trùng đã bị loại khỏi index
            by_hash[h][doc_split.get(doc_of_article(dup))] += 1

    def overlap(table: dict[str, Counter]) -> dict:
        res = {"train_val": 0, "train_test": 0, "val_test": 0, "examples": []}
        for h, c in table.items():
            tv, tt, vt = c["train"] and c["val"], c["train"] and c["test"], c["val"] and c["test"]
            res["train_val"] += bool(tv)
            res["train_test"] += bool(tt)
            res["val_test"] += bool(vt)
            if (tv or tt) and len(res["examples"]) < 10:
                res["examples"].append({"sha1": h, "splits": {str(k): v for k, v in c.items()}})
        return res

    ov_all, ov_index = overlap(by_hash), overlap(by_hash_index_only)
    if ov_index["train_val"] or ov_index["train_test"]:  # chỉ Điều trong index (dữ liệu thực sự dùng)
        errors.append(f"hash Điều trong index: train∩val={ov_index['train_val']}, train∩test={ov_index['train_test']}; yêu cầu = 0")
    spanning = [{"sha1": h, "splits": {str(k): v for k, v in c.items() if k is not None}}
                for h, c in by_hash.items() if len({k for k in c if k is not None}) > 1]

    # --- Điều nguồn của query ---
    split_of_article = {a["article_id"]: doc_split.get(a["doc_id"]) for a in articles}
    q_bad, q_unknown = [], []
    for q in queries:
        src = split_of_article.get(q["source_article_id"])
        if src is None:
            q_unknown.append(q["query_id"])
        elif src != q["split"]:
            q_bad.append({"query_id": q["query_id"], "query_split": q["split"], "source_split": src})
    if q_unknown:
        errors.append(f"{len(q_unknown)} query có Điều nguồn không có trong index, ví dụ {q_unknown[:3]}")
    if q_bad:
        errors.append(f"{len(q_bad)} query có Điều nguồn thuộc split khác split của query, ví dụ {q_bad[:3]}")

    return {"ok": not errors, "errors": errors,
            "groups": len(split_of_group), "groups_per_split": dict(Counter(split_of_group.values())),
            "docs_per_split": dict(Counter(doc_split.values())),
            "hash_overlap_index_only": ov_index, "hash_overlap_including_removed_duplicates_info_only": ov_all,
            "duplicate_groups_spanning_splits": {"count": len(spanning), "examples": spanning[:10],
                                                 "note": "báo riêng, không phải lỗi; bản đã loại khỏi index không là nguồn query. Không loại trừ near-duplicate."},
            "queries_checked": len(queries), "queries_with_other_split_source": q_bad, "queries_unknown_source": q_unknown,
            "docs_multi_group": multi, "docs_uncovered": uncovered, "docs_not_in_corpus": extra}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--splits", help="mặc định: split.output trong config")
    ap.add_argument("--queries", nargs="*", default=[], help="file JSONL query: query_id, split, source_article_id")
    ap.add_argument("--out", help="mặc định: <after_filter_dir>/leakage_report.json")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    splits_path = Path(args.splits or cfg["split"]["output"])
    if not splits_path.exists():
        raise SystemExit(f"Chưa có {splits_path}: chưa chạy split (chờ người xác nhận corpus). Không có gì để kiểm tra.")
    proc = Path(cfg["processed"]["dir"])
    splits_obj, dups = load_splits(splits_path)
    queries = [q for p in args.queries for q in read_jsonl(Path(p))]
    report = check_leakage(splits_obj, dups, read_jsonl(proc / "docs_index.jsonl"), read_jsonl(proc / "articles_index.jsonl"), queries)
    out = Path(args.out or Path(cfg["processed"]["after_filter_dir"]) / "leakage_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "groups_per_split", "docs_per_split", "hash_overlap_index_only")}
                     | {"duplicate_groups_spanning_splits": report["duplicate_groups_spanning_splits"]["count"]}, ensure_ascii=False))
    if not report["ok"]:
        print("LEAKAGE CHECK FAILED:", *report["errors"], sep="\n - ", file=sys.stderr)
        raise SystemExit(1)
    print("LEAKAGE CHECK OK (người cần xác nhận các con số trong báo cáo)")


if __name__ == "__main__":
    main()
