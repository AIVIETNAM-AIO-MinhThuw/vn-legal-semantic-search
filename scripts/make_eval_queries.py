"""Tạo file query theo split và biến thể test (SPEC 5.5), tất định.

Đầu ra (data/eval_v1/, không ghi đè):
  queries_train.csv, queries_val.csv, queries_test.csv
  queries_test_no_diacritic.csv, queries_test_typo.csv  (cột variant_of, variant_type)
"""
from __future__ import annotations

import argparse, csv, json, random, re, sys, unicodedata
from pathlib import Path

TONES = {"́": "s", "̀": "f", "̉": "r", "̃": "x", "̣": "j"}
QWERTY = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
ADJ = {}
for r, row in enumerate(QWERTY):
    for c, ch in enumerate(row):
        n = []
        for dr in (-1, 0, 1):
            rr = r + dr
            if 0 <= rr < 3:
                for dc in (-1, 0, 1):
                    cc = c + dc
                    if (dr or dc) and 0 <= cc < len(QWERTY[rr]):
                        n.append(QWERTY[rr][cc])
        ADJ[ch] = n


def no_diacritic(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", s)


def syllables(s):  # (start, end) của các âm tiết chữ
    return [m.span() for m in re.finditer(r"\w+", s)]


def telex(word: str) -> str | None:
    d = unicodedata.normalize("NFD", word)
    for i, ch in enumerate(d):
        if ch in TONES:
            base = unicodedata.normalize("NFC", d[:i] + d[i + 1:])
            # vị trí nguyên âm mang dấu trong chuỗi NFC mới = số ký tự gốc trước dấu
            pos = len(unicodedata.normalize("NFC", d[:i]))
            return base[:pos] + TONES[ch] + base[pos:]
    return None


def one_typo(s: str, rng: random.Random) -> tuple[str, str]:
    spans = [sp for sp in syllables(s) if sp[1] - sp[0] >= 2]
    if not spans:
        spans = syllables(s)
    kinds = ["adjacent", "delete", "swap", "telex"]
    for _ in range(20):
        kind = rng.choice(kinds)
        a, b = rng.choice(spans)
        w = s[a:b]
        if kind == "telex":
            t = telex(w)
            if t is None:
                continue
            return s[:a] + t + s[b:], kind
        if kind == "delete":
            if len(w) < 2: continue
            i = rng.randrange(len(w))
            return s[:a] + w[:i] + w[i + 1:] + s[b:], kind
        if kind == "swap":
            if len(w) < 2: continue
            i = rng.randrange(len(w) - 1)
            if w[i] == w[i + 1]: continue
            return s[:a] + w[:i] + w[i + 1] + w[i] + w[i + 2:] + s[b:], kind
        if kind == "adjacent":
            idx = [i for i, ch in enumerate(w) if ch.lower() in ADJ]
            if not idx: continue
            i = rng.choice(idx)
            rep = rng.choice(ADJ[w[i].lower()])
            rep = rep.upper() if w[i].isupper() else rep
            return s[:a] + w[:i] + rep + w[i + 1:] + s[b:], kind
    return s, "none"


def typo(s: str, rng: random.Random) -> tuple[str, list[str]]:
    n = 1 if len(syllables(s)) <= 5 else 2
    kinds = []
    for _ in range(n):
        s, k = one_typo(s, rng); kinds.append(k)
    return s, kinds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=Path, default=Path("data/interim/full_v2/queries_v2.csv"))
    ap.add_argument("--splits", type=Path, default=Path("data/splits_v2/query_splits.json"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", type=Path, default=Path("data/eval_v1"))
    a = ap.parse_args()
    if a.output.exists():
        sys.exit(f"Output đã tồn tại: {a.output}")
    with open(a.queries, encoding="utf-8-sig", newline="") as f:
        Q = list(csv.DictReader(f))
    split = json.loads(a.splits.read_text(encoding="utf-8"))["query_split"]
    a.output.mkdir(parents=True)
    cols = ["query_id", "query", "query_type", "field", "source_article_id", "source_doc_id", "source_group_id"]
    def write(name, rows, extra=()):
        with open(a.output / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols + list(extra), extrasaction="ignore", lineterminator="\n")
            w.writeheader(); w.writerows(rows)
    for s in ("train", "val", "test"):
        write(f"queries_{s}.csv", [r for r in Q if split[r["query_id"]] == s])
    test = [r for r in Q if split[r["query_id"]] == "test"]
    nd, ty, changed = [], [], 0
    for r in test:
        v = no_diacritic(r["query"])
        nd.append({**r, "query_id": r["query_id"] + "_nd", "query": v, "variant_of": r["query_id"], "variant_type": "no_diacritic"})
        rng = random.Random(f"{a.seed}:{r['query_id']}:typo")
        t, kinds = typo(r["query"], rng)
        changed += t != r["query"]
        ty.append({**r, "query_id": r["query_id"] + "_ty", "query": t, "variant_of": r["query_id"],
                   "variant_type": "typo", "typo_kinds": "+".join(kinds)})
    write("queries_test_no_diacritic.csv", nd, ("variant_of", "variant_type"))
    write("queries_test_typo.csv", ty, ("variant_of", "variant_type", "typo_kinds"))
    print({"test": len(test), "typo_changed": changed, "nd_changed": sum(x["query"] != y["query"] for x, y in zip(nd, test))})
    for x, y, z in list(zip(test, nd, ty))[:6]:
        print(x["query"][:70], "|", y["query"][:70], "|", z["query"][:70], z["typo_kinds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
