"""Shared SHA-256 and safe manifest paths for artifact preparation/runtime."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def sha_stream(stream) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1 << 22), b""):
        digest.update(block)
    return digest.hexdigest()


def sha_file(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return sha_stream(stream)


def artifact_path(root: Path, key: str) -> Path:
    """Reject non-canonical paths and Windows paths even on Linux."""
    if not isinstance(key, str) or not key or "\\" in key or ":" in key:
        raise ValueError(f"Đường dẫn artifact không hợp lệ: {key!r}")
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != key:
        raise ValueError(f"Đường dẫn artifact không hợp lệ: {key!r}")
    target = Path(root) / key
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError(f"Đường dẫn artifact nằm ngoài thư mục đích: {key}")
    return target


def manifest_files(manifest: dict) -> dict:
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("MANIFEST.json thiếu danh sách files")
    names = set()
    for key, meta in files.items():
        artifact_path(Path.cwd(), key)
        if key.casefold() in names or key.casefold() == "manifest.json":
            raise ValueError(f"Tên file trùng hoặc dành riêng trong manifest: {key}")
        names.add(key.casefold())
        if (not isinstance(meta, dict)
                or not isinstance(meta.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", meta["sha256"])
                or type(meta.get("bytes")) is not int or meta["bytes"] <= 0):
            raise ValueError(f"Metadata artifact không hợp lệ: {key}")
    return files


def bm25_index_files(manifest: dict) -> set[str]:
    """Inventory declared by the frozen BM25 index, including its binary arrays."""
    files = manifest.get("files")
    if not isinstance(files, dict) or "chunks.jsonl" not in files:
        raise ValueError("BM25 manifest thiếu danh sách file index")
    for name in files:
        artifact_path(Path.cwd(), name)
        if len(PurePosixPath(name).parts) != 1:
            raise ValueError(f"Tên file index BM25 không hợp lệ: {name}")
    return set(files)


def verify_artifacts(root: Path) -> dict:
    """Read only: check every manifest file before the service loads models."""
    manifest = json.loads(artifact_path(root, "MANIFEST.json").read_text(encoding="utf-8"))
    files = manifest_files(manifest)
    for key, meta in files.items():
        target = artifact_path(root, key)
        if not target.is_file():
            raise FileNotFoundError(f"Thiếu artifact: {target}")
        if target.stat().st_size != meta["bytes"] or sha_file(target) != meta["sha256"]:
            raise ValueError(f"Artifact sai SHA-256 hoặc kích thước: {key}")
    return files
