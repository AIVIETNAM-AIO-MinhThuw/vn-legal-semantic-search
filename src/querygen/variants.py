"""Biến thể của tập TEST (SPEC 5.5): `no_diacritic` và `typo`, xác định theo seed. Không dùng cho train/val/OOD.

Biến thể có `query_id` riêng, `variant_of`, `variant_type`; dùng chung qrels với query gốc; không vào huấn luyện, không vào pooling.
"""
from __future__ import annotations

import csv
import random
import unicodedata
from pathlib import Path

# phím kề trên bàn phím QWERTY (chỉ chữ cái ASCII)
_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
NEIGHBORS: dict[str, str] = {}
for _r, _row in enumerate(_ROWS):
    for _i, _ch in enumerate(_row):
        nb = set()
        if _i > 0:
            nb.add(_row[_i - 1])
        if _i < len(_row) - 1:
            nb.add(_row[_i + 1])
        for dr in (-1, 1):
            rr = _r + dr
            if 0 <= rr < len(_ROWS):
                for di in (0, -1, 1):
                    j = _i + di
                    if 0 <= j < len(_ROWS[rr]):
                        nb.add(_ROWS[rr][j])
        NEIGHBORS[_ch] = "".join(sorted(nb))

ERROR_TYPES = ("adjacent_key", "delete", "swap", "telex")
_TONE_KEYS = {"́": "s", "̀": "f", "̉": "r", "̃": "x", "̣": "j"}  # sắc, huyền, hỏi, ngã, nặng
_MOD_KEYS = {"̂": "{c}", "̆": "w", "̛": "w"}  # mũ (â ê ô -> lặp chữ), trăng (ă), móc (ơ ư)


def strip_diacritics(text: str) -> str:
    """Bỏ toàn bộ dấu thanh và dấu mũ; đ -> d."""
    t = unicodedata.normalize("NFD", text).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def telex_keystrokes(ch: str) -> str | None:
    """Ký tự có dấu -> chuỗi phím Telex gõ ra (vd. 'ọ' -> 'oj'; 'ô' -> 'oo'; 'ơ' -> 'ow'; 'đ' -> 'dd'). None nếu không có dấu."""
    if ch in "đĐ":
        return ch.replace("đ", "dd").replace("Đ", "DD")
    parts = unicodedata.normalize("NFD", ch)
    base, marks = parts[0], parts[1:]
    if not marks or not base.isascii():
        return None
    out = base
    for m in marks:
        if m in _MOD_KEYS:
            out += _MOD_KEYS[m].format(c=base)
    for m in marks:
        if m in _TONE_KEYS:
            out += _TONE_KEYS[m]
    return out


def _letter_positions(s: str) -> list[int]:
    return [i for i, c in enumerate(s) if c.isalpha()]


def _apply(s: str, kind: str, rng: random.Random) -> str | None:
    """Áp một lỗi; None nếu không áp được (vd. không có chữ có dấu cho lỗi Telex)."""
    if kind == "adjacent_key":
        pos = [i for i, c in enumerate(s) if c.lower() in NEIGHBORS]
        if not pos:
            return None
        i = rng.choice(pos)
        rep = rng.choice(NEIGHBORS[s[i].lower()])
        return s[:i] + (rep.upper() if s[i].isupper() else rep) + s[i + 1:]
    if kind == "delete":
        pos = _letter_positions(s)
        if len(pos) < 2:
            return None
        i = rng.choice(pos)
        return s[:i] + s[i + 1:]
    if kind == "swap":
        pos = [i for i in range(len(s) - 1) if s[i].isalpha() and s[i + 1].isalpha() and s[i] != s[i + 1]]
        if not pos:
            return None
        i = rng.choice(pos)
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if kind == "telex":
        pos = [i for i, c in enumerate(s) if telex_keystrokes(c)]
        if not pos:
            return None
        i = rng.choice(pos)
        return s[:i] + telex_keystrokes(s[i]) + s[i + 1:]
    raise ValueError(kind)


def make_typo(text: str, query_id: str, seed, short_max: int = 5, errors_short: int = 1, errors_long: int = 2) -> tuple[str, list[str]]:
    """Query <= short_max âm tiết: 1 lỗi; dài hơn: 2 lỗi. Mỗi lỗi chọn đều một trong bốn loại. Xác định theo seed và query_id.
    Nếu loại được chọn không áp dụng được (vd. không có chữ có dấu cho Telex) thì thử các loại còn lại theo thứ tự cố định."""
    from .text import syllables
    n_err = errors_short if len(syllables(text)) <= short_max else errors_long
    rng = random.Random(f"{seed}|{query_id}|typo")
    out, applied = text, []
    for _ in range(n_err):
        first = rng.choice(ERROR_TYPES)  # mỗi lỗi chọn đều một trong bốn loại
        order = [first] + [k for k in ERROR_TYPES if k != first]  # dự phòng theo thứ tự cố định nếu loại đó không áp dụng được
        for kind in order:
            new = _apply(out, kind, rng)
            if new is not None and new != out:
                out, applied = new, applied + [kind]
                break
    return out, applied


def make_variants(test_queries: list[dict], seed, **typo_cfg) -> list[dict]:
    """Chỉ nhận query test. Trả về biến thể no_diacritic và typo cho từng query."""
    out = []
    for q in test_queries:
        if q.get("split") != "test":
            raise ValueError(f"{q.get('query_id')}: biến thể chỉ áp dụng cho query test (split={q.get('split')})")
        if q.get("variant_of"):
            raise ValueError(f"{q['query_id']}: không tạo biến thể từ biến thể")
        base = {"article_id": q["article_id"], "doc_id": q.get("doc_id"), "split": "test", "variant_of": q["query_id"],
                "use_for_training": False, "use_for_pooling": False, "qrels_from": q["query_id"]}
        out.append({**base, "query_id": f"{q['query_id']}::no_diacritic", "variant_type": "no_diacritic", "text": strip_diacritics(q["text"])})
        typo, applied = make_typo(q["text"], q["query_id"], seed, **typo_cfg)
        out.append({**base, "query_id": f"{q['query_id']}::typo", "variant_type": "typo", "text": typo, "typo_errors": applied})
    return out


def export_typo_sample(variants: list[dict], originals: dict[str, str], k: int, seed, path: Path | str) -> int:
    """Mẫu cho người đọc (SPEC 5.5): k biến thể typo chọn theo seed; cột kết quả để trống cho người điền."""
    typos = sorted((v for v in variants if v["variant_type"] == "typo"), key=lambda v: v["query_id"])
    sample = random.Random(f"{seed}|typo-sample").sample(typos, min(k, len(typos)))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "variant_of", "original", "typo_variant", "typo_errors", "meaning_changed(reviewer)", "reviewer", "date"])
        for v in sorted(sample, key=lambda v: v["query_id"]):
            w.writerow([v["query_id"], v["variant_of"], originals[v["variant_of"]], v["text"], "+".join(v.get("typo_errors", [])), "", "", ""])
    return len(sample)


_YES = {"yes", "y", "có", "co", "1", "true", "đổi nghĩa"}


def apply_typo_review(variants: list[dict], sheet_rows: list[dict]) -> tuple[list[dict], dict]:
    """Áp dụng kết quả người đọc mẫu typo (SPEC 5.5): biến thể có nghĩa bị đổi thì bị loại, không gán nhãn lại.
    Cột `meaning_changed(reviewer)` do người điền (yes/no); thiếu reviewer/date hoặc để trống -> lỗi, không đoán."""
    col = "meaning_changed(reviewer)"
    problems, drop = [], set()
    for r in sheet_rows:
        v = (r.get(col) or "").strip().lower()
        if not v or not (r.get("reviewer") or "").strip() or not (r.get("date") or "").strip():
            problems.append(f"{r.get('query_id')}: thiếu kết quả/người đọc/ngày")
        elif v in _YES:
            drop.add(r["query_id"])
        elif v not in {"no", "n", "không", "khong", "0", "false"}:
            problems.append(f"{r.get('query_id')}: giá trị {v!r} không hợp lệ (yes/no)")
    if problems:
        raise ValueError("; ".join(problems[:5]))
    known = {v["query_id"] for v in variants}
    unknown = [q for q in drop if q not in known]
    if unknown:
        raise ValueError(f"biến thể không tồn tại: {unknown[:3]}")
    kept = [v for v in variants if v["query_id"] not in drop]
    return kept, {"sample_size": len(sheet_rows), "removed": len(drop), "removed_ids": sorted(drop), "variants_before": len(variants), "variants_after": len(kept)}
