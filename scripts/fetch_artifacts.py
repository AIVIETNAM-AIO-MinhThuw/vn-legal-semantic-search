"""Giải nén gói artifact vào repo và kiểm tra SHA-256 từng file.

python -X utf8 scripts/fetch_artifacts.py --zip <đường dẫn vnlegal-demo-v1.zip> [--sha256 <hash của zip>]
Không ghi đè file đã có khác nội dung (trừ khi --force).
"""
from __future__ import annotations

import argparse, hashlib, json, sys, zipfile
from pathlib import Path


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--sha256", help="hash của file zip (trong file .sha256 đi kèm)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.sha256:
        got = sha_file(a.zip)
        if got != a.sha256.strip().lower():
            sys.exit(f"Zip sai hash: {got}")
        print("Zip đúng hash.")
    with zipfile.ZipFile(a.zip) as z:
        manifest = json.loads(z.read("MANIFEST.json"))
        for key, meta in manifest["files"].items():
            target = Path(key)
            if ".." in target.parts or target.is_absolute():
                sys.exit(f"Đường dẫn không hợp lệ trong gói: {key}")
            if target.exists():
                if sha_file(target) == meta["sha256"]:
                    continue
                if not a.force:
                    sys.exit(f"{key} đã tồn tại và khác nội dung; dùng --force để ghi đè")
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(key) as src, open(target, "wb") as dst:
                while chunk := src.read(1 << 22):
                    dst.write(chunk)
            if sha_file(target) != meta["sha256"]:
                sys.exit(f"Sai hash sau giải nén: {key}")
            print("ok", key)
    sel = Path("models/lr_selection.json")
    print(f"Xong: {len(manifest['files'])} file khớp MANIFEST." + ("" if sel.exists() else " (thiếu models/lr_selection.json — lấy từ git)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
