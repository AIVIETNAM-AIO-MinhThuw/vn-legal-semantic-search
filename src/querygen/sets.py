"""Lọc và ghép các tập query từ file query thô (SPEC 5.3–5.4). Không gọi LLM."""
from __future__ import annotations

from collections import Counter


def flatten(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        if r["skip"]:
            continue
        for q in r["queries"]:
            out.append({**q, "article_id": r["article_id"], "doc_id": r["doc_id"], "split": r["split"]})
    return out


def reject_reason(q: dict, split: str, train_overlap_threshold: float | None, train_overlap_inclusive: bool | None) -> str | None:
    """Query chép nguyên văn hoặc nhắc số hiệu bị loại khỏi mọi tập; overlap cao chỉ lọc ở train (SPEC 5.3)."""
    if q["verbatim_copy"]:
        return "verbatim_copy"
    if q["refers_to_article_or_document"]:
        return "refers_to_article_or_document_number"
    if split == "train":
        if train_overlap_threshold is None or train_overlap_inclusive is None:
            raise ValueError("train_overlap_threshold và train_overlap_inclusive phải được chốt trước khi lọc train")
        hi = q["overlap"] >= train_overlap_threshold if train_overlap_inclusive else q["overlap"] > train_overlap_threshold
        if hi:
            return "high_overlap_train"
    return None


def filter_split(records: list[dict], split: str, threshold, inclusive) -> tuple[list[dict], Counter]:
    """Train: mọi query qua bộ lọc của các Điều được chọn. Val/test: chỉ loại chép nguyên văn / số hiệu; overlap chỉ để phân nhóm."""
    kept, why = [], Counter()
    for q in flatten(records):
        if q["split"] != split:
            raise ValueError(f"{q['query_id']}: split {q['split']} khác {split}")
        r = reject_reason(q, split, threshold, inclusive)
        if r:
            why[r] += 1
        else:
            kept.append(q)
    return kept, why


def assemble_eval(records: list[dict], main_ids: list[str], types: dict[str, str], reserve_ids: list[str],
                  reserve_types: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Ghép tập val/test: mỗi Điều chính một query đúng kiểu đã gán. Nếu query không dùng được (skip / chép nguyên văn /
    nhắc số hiệu), thay bằng query CÙNG KIỂU của Điều dự phòng kế tiếp được gán đúng kiểu đó, cùng split (SPEC 5.4).
    Hết dự phòng của kiểu đó thì ValueError (báo nhóm; không lấy bù từ split khác)."""
    by_art = {r["article_id"]: r for r in records}

    def usable(aid: str, t: str):
        r = by_art.get(aid)
        if not r or r["skip"]:
            return None
        q = next(x for x in r["queries"] if x["type"] == t)
        return None if (q["verbatim_copy"] or q["refers_to_article_or_document"]) else {**q, "article_id": aid, "doc_id": r["doc_id"], "split": r["split"]}

    used, out, replaced = set(), [], []
    for aid in main_ids:
        t = types[aid]
        q = usable(aid, t)
        if q is None:
            for cand in reserve_ids:
                if cand in used or reserve_types.get(cand) != t:
                    continue
                q2 = usable(cand, t)
                if q2:
                    used.add(cand)
                    replaced.append({"replaced_article_id": aid, "by_article_id": cand, "type": t})
                    q = q2
                    break
        if q is None:
            raise ValueError(f"hết Điều dự phòng kiểu {t} để thay query của {aid}")
        out.append(q)
    return out, replaced


def filter_stats(records: list[dict], split: str, threshold, inclusive) -> dict:
    """Số query trước/sau lọc theo từng kiểu (natural/scenario/keyword) và lý do loại, để đo (không phải kết luận)."""
    stats = {t: {"generated": 0, "kept": 0, "rejected": Counter()} for t in ("natural", "scenario", "keyword")}
    for q in flatten(records):
        st = stats[q["type"]]
        st["generated"] += 1
        why = reject_reason(q, split, threshold, inclusive)
        if why:
            st["rejected"][why] += 1
        else:
            st["kept"] += 1
    return {"split": split, "by_type": {t: {"generated": v["generated"], "kept": v["kept"], "rejected": dict(v["rejected"])} for t, v in stats.items()},
            "articles_total": len(records), "articles_skipped": sum(1 for r in records if r["skip"]),
            "kept_total": sum(v["kept"] for v in stats.values()), "generated_total": sum(v["generated"] for v in stats.values())}


def _usable_after_copy_filters(q: dict) -> bool:
    return not (q["verbatim_copy"] or q["refers_to_article_or_document"])


def kept_count_distribution(records: list[dict], split: str, threshold, inclusive) -> dict:
    """Số Điều còn 0/1/2/3 query, tách theo tầng lọc (SPEC 5.3):
    - `after_copy_filters`: sau lọc chép nguyên văn N âm tiết và nhắc số hiệu (áp dụng mọi split);
    - `after_train_overlap`: sau thêm lọc overlap cao (chỉ train; val/test = None vì không lọc overlap).
    Điều `skip` được tính vào 0 và đếm riêng ở `articles_skipped`."""
    def dist(counts: list[int]) -> dict:
        c = Counter(counts)
        return {str(k): c.get(k, 0) for k in range(4)}

    copy_counts, train_counts = [], []
    for r in records:
        qs = [] if r["skip"] else r["queries"]
        copy_counts.append(sum(1 for q in qs if _usable_after_copy_filters(q)))
        if split == "train":
            train_counts.append(sum(1 for q in qs if reject_reason(q, split, threshold, inclusive) is None))
    return {"split": split, "articles_total": len(records), "articles_skipped": sum(1 for r in records if r["skip"]),
            "after_copy_filters": dist(copy_counts), "after_train_overlap": dist(train_counts) if split == "train" else None}


def error_report(entries: list[dict], processed_ids: set[str], planned_ids: list[str] | None = None) -> dict:
    """Tổng hợp log lỗi chỉ ghi thêm của `generate`. Điều chưa xử lý được = có trong log lỗi (cấp Điều hoặc thuộc batch
    hỏng) nhưng chưa có bản ghi trong file query thô. `planned_ids` (kế hoạch val/test/pilot) thêm danh sách Điều chưa có."""
    art = [e for e in entries if e.get("level") == "article"]
    batch = [e for e in entries if e.get("level") == "batch"]
    by_article: dict[str, list[dict]] = {}
    for e in art:
        by_article.setdefault(e["article_id"], []).append({"field": e["field"], "reason": e["reason"], "run_id": e.get("run_id")})
    touched = set(by_article)
    for e in batch:
        touched.update(e.get("article_ids") or [])
    out = {"article_errors_by_field": dict(Counter(e["field"] for e in art)), "article_errors": dict(sorted(by_article.items())),
           "batch_errors_by_type": dict(Counter(e.get("error_type") for e in batch)), "batch_errors": batch,
           "unresolved_article_ids": sorted(touched - processed_ids)}
    if planned_ids is not None:
        out["planned_not_processed"] = [a for a in planned_ids if a not in processed_ids]
    return out
