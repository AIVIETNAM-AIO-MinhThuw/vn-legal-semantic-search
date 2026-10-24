"""Duyệt query val/test OFFLINE (SPEC 5.4). Người điền phiếu CSV; công cụ chỉ kiểm tra và áp dụng, KHÔNG tự quyết định.

- Val: người chọn `accept` hoặc `reject` (kèm lý do thuộc danh sách của SPEC).
- Test: `accept`, `reject` hoặc `edit` (sửa câu chữ giữ nguyên ý). Mọi sửa ghi vào `logs/test_query_edits.jsonl`
  (bản gốc, bản sửa, người sửa) và bản đã sửa phải qua lại kiểm tra chép nguyên văn N = 8 (và không nhắc số hiệu).
- Query bị loại được thay bằng query CÙNG KIỂU của Điều dự phòng kế tiếp cùng split; hết dự phòng thì báo lỗi (không lấy bù nơi khác).
- Phiếu thiếu `reviewer` hoặc `date`, hoặc quyết định không hợp lệ -> toàn bộ lần áp dụng bị từ chối, không đổi trạng thái.
Công cụ không bao giờ điền tên người duyệt hay quyết định thay người.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .text import article_text, has_verbatim_copy, overlap, refers_to_article_or_document_number, syllables

DECISIONS_VAL = {"accept", "reject"}
DECISIONS_TEST = {"accept", "reject", "edit"}
REJECT_REASONS = ("khó hiểu", "Điều nguồn không trả lời được", "chứa số hiệu Điều hoặc văn bản", "trùng ý với query khác trong tập")
SHEET_COLS = ["slot", "query_id", "article_id", "type", "query_text", "article_title", "article_text", "decision", "reason",
              "edited_text", "reviewer", "date", "note"]


class ReviewError(ValueError):
    """Phiếu không hợp lệ hoặc không áp dụng được. `problems` liệt kê từng lỗi."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems[:5]) + (f" (+{len(problems) - 5} lỗi nữa)" if len(problems) > 5 else ""))
        self.problems = problems


def _usable(rec: dict | None, qtype: str):
    if not rec or rec["skip"]:
        return None
    q = next(x for x in rec["queries"] if x["type"] == qtype)
    if q["verbatim_copy"] or q["refers_to_article_or_document"]:
        return None
    return {**q, "article_id": rec["article_id"], "doc_id": rec["doc_id"], "split": rec["split"]}


def init_state(split: str, candidates: list[dict], plan: dict) -> dict:
    """Trạng thái duyệt ban đầu từ tập ứng viên (kết quả `assemble_eval`, theo thứ tự Điều chính)."""
    if split not in ("val", "test"):
        raise ValueError("chỉ duyệt val và test")
    slots = [{"slot": i, "type": q["type"], "article_id": q["article_id"], "query_id": q["query_id"], "text": q["text"],
              "status": "pending", "edited": False, "history": []} for i, q in enumerate(candidates)]
    return {"split": split, "round": 1, "slots": slots, "reserve_used": [], "plan": {"reserve_ids": plan["reserve_ids"], "reserve_types": plan["reserve_types"]}}


def export_sheet(state: dict, articles: dict[str, dict], path: Path | str, max_chars: int = 2500) -> int:
    rows = [s for s in state["slots"] if s["status"] == "pending"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLS)
        w.writeheader()
        for s in rows:
            a = articles[s["article_id"]]
            w.writerow({"slot": s["slot"], "query_id": s["query_id"], "article_id": s["article_id"], "type": s["type"], "query_text": s["text"],
                        "article_title": a.get("title", ""), "article_text": a["body"][:max_chars], "decision": "", "reason": "", "edited_text": "",
                        "reviewer": "", "date": "", "note": ""})
    return len(rows)


def read_sheet(path: Path | str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def apply_sheet(state: dict, rows: list[dict], records: list[dict], articles: dict[str, dict], *, verbatim_n: int = 8,
                edit_log: Path | str | None = None) -> dict:
    """Áp dụng phiếu do NGƯỜI điền. Trả về trạng thái mới (không sửa `state` đầu vào). Atomic: có lỗi thì raise ReviewError."""
    split = state["split"]
    allowed = DECISIONS_VAL if split == "val" else DECISIONS_TEST
    by_rec = {r["article_id"]: r for r in records}
    slots = json.loads(json.dumps(state))  # bản sao sâu
    pending = {s["slot"]: s for s in slots["slots"] if s["status"] == "pending"}
    problems: list[str] = []
    edits: list[dict] = []
    seen = set()
    for row in rows:
        try:
            slot = int(row["slot"])
        except (ValueError, KeyError):
            problems.append(f"dòng phiếu có slot không hợp lệ: {row.get('slot')!r}")
            continue
        s = pending.get(slot)
        tag = f"slot {slot} ({row.get('query_id')})"
        if s is None or row.get("query_id") != s["query_id"]:
            problems.append(f"{tag}: không khớp slot đang chờ duyệt")
            continue
        if slot in seen:
            problems.append(f"{tag}: lặp trong phiếu")
            continue
        seen.add(slot)
        d = (row.get("decision") or "").strip().lower()
        if d not in allowed:
            problems.append(f"{tag}: quyết định {d!r} không hợp lệ cho {split} (cho phép {sorted(allowed)}); không được để trống")
            continue
        if not (row.get("reviewer") or "").strip() or not (row.get("date") or "").strip():
            problems.append(f"{tag}: thiếu reviewer hoặc date (do người điền)")
            continue
        art = articles[s["article_id"]]
        atext = article_text(art.get("title", ""), art["body"])
        entry = {"article_id": s["article_id"], "query_id": s["query_id"], "decision": d, "reviewer": row["reviewer"].strip(),
                 "date": row["date"].strip(), "note": (row.get("note") or "").strip()}
        if d == "reject":
            reason = (row.get("reason") or "").strip()
            if reason not in REJECT_REASONS:
                problems.append(f"{tag}: lý do loại phải thuộc {list(REJECT_REASONS)}")
                continue
            entry["reason"] = reason
            s["pending_reject"] = entry
        elif d == "edit":
            new = (row.get("edited_text") or "").strip()
            if not new or new == s["text"]:
                problems.append(f"{tag}: edit cần edited_text khác bản gốc")
                continue
            if has_verbatim_copy(new, atext, verbatim_n):
                problems.append(f"{tag}: bản sửa chép nguyên văn >= {verbatim_n} âm tiết từ Điều; sửa lại hoặc loại")
                continue
            if refers_to_article_or_document_number(new):
                problems.append(f"{tag}: bản sửa nhắc số hiệu Điều/văn bản; sửa lại hoặc loại")
                continue
            if not new.strip() or (s["type"] == "keyword" and not 1 <= len(syllables(new)) <= 4):
                problems.append(f"{tag}: query keyword phải có 1-4 từ")
                continue
            entry.update(edited_text=new, original_text=s["text"])
            edits.append({"query_id": s["query_id"], "split": split, "original": s["text"], "edited": new, "editor": entry["reviewer"], "date": entry["date"]})
            s["text"], s["edited"] = new, True
            s["status"] = "accepted"
            s["history"].append(entry)
        else:  # accept: không chấp nhận query đã vi phạm bộ lọc tự động
            q = _usable(by_rec.get(s["article_id"]), s["type"])
            if q is None:
                problems.append(f"{tag}: query vi phạm bộ lọc tự động (chép nguyên văn/nhắc số hiệu/skip) nên không thể accept")
                continue
            s["status"] = "accepted"
            s["history"].append(entry)
    if problems:
        raise ReviewError(problems)
    # áp dụng loại + thay thế (sau khi mọi dòng hợp lệ)
    used = set(slots["reserve_used"])
    for s in slots["slots"]:
        rej = s.pop("pending_reject", None)
        if rej is None:
            continue
        s["history"].append(rej)
        for cand in slots["plan"]["reserve_ids"]:
            if cand in used or slots["plan"]["reserve_types"].get(cand) != s["type"]:
                continue
            q = _usable(by_rec.get(cand), s["type"])
            if q:
                used.add(cand)
                s.update(article_id=cand, query_id=q["query_id"], text=q["text"], status="pending", edited=False)
                s["history"].append({"replacement_from_reserve": cand})
                break
        else:
            raise ReviewError([f"slot {s['slot']}: hết Điều dự phòng kiểu {s['type']}; báo nhóm, không lấy bù từ split khác"])
    slots["reserve_used"] = sorted(used)
    slots["round"] = state["round"] + 1
    if edit_log and edits:
        Path(edit_log).parent.mkdir(parents=True, exist_ok=True)
        with open(edit_log, "a", encoding="utf-8", newline="\n") as f:
            for e in edits:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return slots


def finalize(state: dict, records: list[dict], per_type: int) -> list[dict]:
    """Chỉ khi mọi slot đã accepted và đủ per_type query mỗi kiểu."""
    pend = [s["slot"] for s in state["slots"] if s["status"] != "accepted"]
    if pend:
        raise ReviewError([f"còn {len(pend)} slot chưa được người duyệt chấp nhận: {pend[:5]}"])
    by_rec = {r["article_id"]: r for r in records}
    out = []
    for s in state["slots"]:
        rec = by_rec[s["article_id"]]
        q = next(x for x in rec["queries"] if x["type"] == s["type"])
        out.append({**q, "text": s["text"], "article_id": s["article_id"], "doc_id": rec["doc_id"], "split": state["split"], "edited": s["edited"],
                    "review_history": s["history"]})
    counts = {t: sum(1 for x in out if x["type"] == t) for t in ("natural", "scenario", "keyword")}
    if any(c != per_type for c in counts.values()):
        raise ReviewError([f"số query mỗi kiểu phải là {per_type}, hiện {counts}"])
    return out
