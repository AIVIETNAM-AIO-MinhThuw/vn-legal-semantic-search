"""Đóng gói artifact lớn (ngoài git) để người khác chạy demo không cần dựng lại.

python -X utf8 scripts/package_artifacts.py            -> release/vnlegal-demo-v1.zip (+ .sha256)
Gói chứa MANIFEST.json (SHA-256 từng file); scripts/fetch_artifacts.py kiểm tra khi giải nén.
"""
from __future__ import annotations

import hashlib, json, sys, zipfile
from pathlib import Path

NAME = "vnlegal-demo-v1"
INCLUDE = [
    "data/processed/articles_index.jsonl", "data/processed/chunks_index.jsonl", "data/processed/docs_index.jsonl",
    "data/raw/vncorenlp",
    "indexes/bm25_s10", "indexes/e5_ft_B",
    "models/e5_ft_B_lr3e-05/model",
]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    files = []
    for item in INCLUDE:
        p = Path(item)
        if not p.exists():
            sys.exit(f"Thiếu {p}")
        files += sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
    out = Path("release") / f"{NAME}.zip"
    if out.exists():
        sys.exit(f"Đã có {out}")
    out.parent.mkdir(exist_ok=True)
    manifest = {"name": NAME, "files": {}}
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for f in files:
            key = f.as_posix()
            manifest["files"][key] = {"sha256": sha(f), "bytes": f.stat().st_size}
            z.write(f, key)
            print("+", key, flush=True)
        z.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    digest = sha(out)
    (out.parent / f"{NAME}.sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    print(f"{out} {out.stat().st_size / 2**20:.0f} MB sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
