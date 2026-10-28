"""Giải nén ZIP đã kiểm tra SHA-256 vào ./artifacts, giữ nguyên byte artifact.

python -X utf8 scripts/fetch_artifacts.py --zip <file.zip> --sha256 <hash> [--output-dir artifacts]
Không ghi đè file khác nội dung trừ khi người chạy chỉ định --force.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.app.artifacts import artifact_path, bm25_index_files, manifest_files, sha_file, sha_stream  # noqa: E402


def required_files() -> set[str]:
    # LR metadata stays with the checkout/image, not in the artifact ZIP.
    selection = json.loads((ROOT / "models/lr_selection.json").read_text(encoding="utf-8-sig"))
    model = f"models/e5_ft_B_lr{selection['selected_lr']}/model"
    return {
        "data/processed/articles_index.jsonl", "data/processed/chunks_index.jsonl",
        "data/processed/docs_index.jsonl", "data/raw/vncorenlp/revision.txt",
        "data/raw/vncorenlp/VnCoreNLP-1.2.jar",
        "data/raw/vncorenlp/models/wordsegmenter/vi-vocab",
        "data/raw/vncorenlp/models/wordsegmenter/wordsegmenter.rdr",
        "indexes/bm25_s10/manifest.json", "indexes/bm25_s10/chunks.jsonl",
        "indexes/e5_ft_B/manifest.json", "indexes/e5_ft_B/vectors.npy",
        "indexes/e5_ft_B/chunk_ids.json",
        *(f"{model}/{name}" for name in (
            "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")),
    }


def _write_file(target: Path, stream, expected_hash: str) -> None:
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".fetch-", delete=False) as temporary:
        staging = Path(temporary.name)
        try:
            shutil.copyfileobj(stream, temporary, length=1 << 22)
        except BaseException:
            temporary.close()
            staging.unlink(missing_ok=True)
            raise
    try:
        if sha_file(staging) != expected_hash:
            raise ValueError(f"Sai hash sau giải nén: {target}")
        # NamedTemporaryFile defaults to 0600; API UID must read the host bind mount.
        staging.chmod(0o644)
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)


def fetch_artifacts(zip_path: Path, output_dir: Path, sha256: str, force: bool = False) -> int:
    output_dir = output_dir.resolve()
    if sha_file(zip_path) != sha256.strip().lower():
        raise ValueError("ZIP sai SHA-256; không giải nén")
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("ZIP chứa tên file trùng")
        for info in infos:
            artifact_path(output_dir, info.filename.rstrip("/") if info.is_dir() else info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"ZIP chứa symlink: {info.filename}")
        manifest_data = archive.read("MANIFEST.json")
        files = manifest_files(json.loads(manifest_data))
        missing = required_files() - files.keys()
        if missing:
            raise ValueError(f"Gói demo thiếu file runtime: {', '.join(sorted(missing))}")
        bm25 = json.loads(archive.read("indexes/bm25_s10/manifest.json"))
        missing = {f"indexes/bm25_s10/{name}" for name in bm25_index_files(bm25)} - files.keys()
        if missing:
            raise ValueError(f"Gói demo thiếu file index BM25: {', '.join(sorted(missing))}")
        actual_files = {info.filename for info in infos if not info.is_dir()}
        if actual_files != set(files) | {"MANIFEST.json"}:
            raise ValueError("Danh sách file ZIP không khớp MANIFEST.json")
        # Validate the whole archive and all destination conflicts before writing.
        for key, meta in files.items():
            with archive.open(key) as stream:
                if archive.getinfo(key).file_size != meta["bytes"] or sha_stream(stream) != meta["sha256"]:
                    raise ValueError(f"File trong ZIP sai SHA-256 hoặc kích thước: {key}")
        writes = {**files, "MANIFEST.json": {"sha256": hashlib.sha256(manifest_data).hexdigest()}}
        for key, meta in writes.items():
            target = artifact_path(output_dir, key)
            if target.exists() and (not target.is_file() or (sha_file(target) != meta["sha256"] and not force)):
                raise FileExistsError(f"{target} đã tồn tại và khác nội dung; không ghi đè")
        for key, meta in writes.items():
            target = artifact_path(output_dir, key)
            target.parent.mkdir(parents=True, exist_ok=True)
            for directory in (target.parent, *target.parent.parents):
                if not directory.is_relative_to(output_dir):
                    break
                mode = directory.stat().st_mode
                if mode & 0o055 != 0o055:
                    directory.chmod(mode | 0o055)
            if target.is_file() and sha_file(target) == meta["sha256"]:
                mode = target.stat().st_mode
                if mode & 0o044 != 0o044:
                    target.chmod(mode | 0o044)
                continue
            with (io.BytesIO(manifest_data) if key == "MANIFEST.json" else archive.open(key)) as stream:
                _write_file(target, stream, meta["sha256"])
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sha256", required=True, help="SHA-256 tin cậy của ZIP từ README hoặc file .sha256")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        count = fetch_artifacts(args.zip, args.output_dir, args.sha256, args.force)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Không chuẩn bị được artifact: {error}\n")
    print(f"Xong: {count} file khớp MANIFEST tại {args.output_dir.resolve()}. LR metadata lấy từ checkout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
