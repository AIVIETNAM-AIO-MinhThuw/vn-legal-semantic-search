"""Artifact trust boundaries and runtime paths; no model download or frozen data."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fetch_artifacts import fetch_artifacts
from src.app.artifacts import verify_artifacts
from src.app.service import SearchService


@pytest.fixture
def payload():
    names = [
        "data/processed/articles_index.jsonl", "data/processed/chunks_index.jsonl",
        "data/processed/docs_index.jsonl", "data/raw/vncorenlp/revision.txt",
        "data/raw/vncorenlp/VnCoreNLP-1.2.jar",
        "data/raw/vncorenlp/models/wordsegmenter/vi-vocab",
        "data/raw/vncorenlp/models/wordsegmenter/wordsegmenter.rdr",
        "indexes/bm25_s10/chunks.jsonl", "indexes/bm25_s10/data.csc.index.npy",
        "indexes/e5_ft_B/manifest.json", "indexes/e5_ft_B/vectors.npy",
        "indexes/e5_ft_B/chunk_ids.json",
    ]
    names += [f"models/e5_ft_B_lr3e-05/model/{name}" for name in (
        "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")]
    data = {name: b"fixture" for name in names}
    data["indexes/bm25_s10/manifest.json"] = json.dumps({"files": {
        name: hashlib.sha256(b"fixture").hexdigest()
        for name in ("chunks.jsonl", "data.csc.index.npy")
    }}).encode()
    return data


def bundle(tmp_path, data, *, corrupt=None):
    manifest = {"files": {name: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                          for name, value in data.items()}}
    path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in data.items():
            archive.writestr(name, b"tampered" if name == corrupt else value)
        archive.writestr("MANIFEST.json", json.dumps(manifest))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_fetch_preserves_bytes_and_is_idempotent(tmp_path, payload):
    archive, digest = bundle(tmp_path, payload)
    target = tmp_path / "artifacts"
    assert fetch_artifacts(archive, target, digest) == len(payload)
    before = {p: p.stat().st_mtime_ns for p in target.rglob("*") if p.is_file()}
    fetch_artifacts(archive, target, digest)
    assert before == {p: p.stat().st_mtime_ns for p in before}
    for name, value in payload.items():
        assert (target / name).read_bytes() == value
    verify_artifacts(target)


@pytest.mark.parametrize("failure", ["zip_hash", "file_hash", "missing_corpus", "missing_bm25", "escape"])
def test_bad_bundle_fails_before_writing(tmp_path, payload, failure):
    if failure == "missing_corpus":
        del payload["data/processed/articles_index.jsonl"]
    if failure == "missing_bm25":
        del payload["indexes/bm25_s10/data.csc.index.npy"]
    if failure == "escape":
        payload["../outside"] = b"unsafe"
    archive, digest = bundle(tmp_path, payload, corrupt=(
        "data/processed/docs_index.jsonl" if failure == "file_hash" else None))
    target = tmp_path / "artifacts"
    with pytest.raises(ValueError):
        fetch_artifacts(archive, target, "0" * 64 if failure == "zip_hash" else digest)
    assert not target.exists()


def test_conflict_does_not_partially_extract(tmp_path, payload):
    archive, digest = bundle(tmp_path, payload)
    target = tmp_path / "artifacts"
    conflict = target / "indexes/e5_ft_B/vectors.npy"
    conflict.parent.mkdir(parents=True)
    conflict.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        fetch_artifacts(archive, target, digest)
    assert conflict.read_bytes() == b"existing"
    assert not (target / "data").exists()


@pytest.mark.skipif(os.name != "posix", reason="Linux bind mount permission contract")
@pytest.mark.parametrize("existing", [False, True])
def test_fetch_readable_by_container_uid_with_restrictive_umask(tmp_path, payload, existing):
    archive, digest = bundle(tmp_path, payload)
    target = tmp_path / "artifacts"
    if existing:
        target.mkdir(mode=0o700)
        (target / "indexes").mkdir(mode=0o700)
    previous = os.umask(0o077)
    try:
        fetch_artifacts(archive, target, digest)
    finally:
        os.umask(previous)
    for path in [target, *target.rglob("*")]:
        assert path.stat().st_mode & 0o005 == (0o005 if path.is_dir() else 0o004)


def prepared_service(tmp_path, monkeypatch, payload):
    from src.app import service
    # Config and LR metadata live with code; they are deliberately absent from ZIP.
    monkeypatch.setattr(service, "ROOT", tmp_path)
    (tmp_path / "configs").mkdir()
    for name in ("bm25.yaml", "dense_e5_ft.yaml", "e5.yaml"):
        (tmp_path / "configs" / name).write_bytes((ROOT / "configs" / name).read_bytes())
    (tmp_path / "models").mkdir()
    (tmp_path / "models/lr_selection.json").write_text('{"selected_lr":"3e-05"}')
    instance = SearchService.__new__(SearchService)
    instance.cfg = yaml.safe_load((ROOT / "configs/app.yaml").read_text(encoding="utf-8"))
    archive, digest = bundle(tmp_path, payload)
    fetch_artifacts(archive, tmp_path / "artifacts", digest)
    return instance


def test_runtime_paths_and_sqlite_outside_artifacts(tmp_path, monkeypatch, payload):
    instance = prepared_service(tmp_path, monkeypatch, payload)
    monkeypatch.chdir(tmp_path.parent)
    instance._prepare_artifacts()
    assert instance.spaths["model"] == tmp_path / "artifacts/models/e5_ft_B_lr3e-05/model"
    assert instance.bpaths["index"] == tmp_path / "artifacts/indexes/bm25_s10"
    before = {p: p.read_bytes() for p in (tmp_path / "artifacts").rglob("*") if p.is_file()}
    instance._init_db()
    try:
        assert instance.db.execute("SELECT count(*) FROM feedback").fetchone() == (0,)
        assert (tmp_path / "data/app/feedback.sqlite").is_file()
        assert before == {p: p.read_bytes() for p in before}
    finally:
        instance.db.close()


def test_runtime_rejects_feedback_inside_artifacts(tmp_path, monkeypatch, payload):
    instance = prepared_service(tmp_path, monkeypatch, payload)
    instance.cfg["feedback_db"] = "artifacts/feedback.sqlite"
    with pytest.raises(ValueError, match="feedback_db"):
        instance._prepare_artifacts()


def test_runtime_rejects_unavailable_selected_lr(tmp_path, monkeypatch, payload):
    instance = prepared_service(tmp_path, monkeypatch, payload)
    (tmp_path / "models/lr_selection.json").write_text('{"selected_lr":"1e-05"}')
    with pytest.raises(FileNotFoundError, match="Thiếu file runtime"):
        instance._prepare_artifacts()


def test_runtime_detects_tampering(tmp_path, monkeypatch, payload):
    instance = prepared_service(tmp_path, monkeypatch, payload)
    (tmp_path / "artifacts/data/processed/docs_index.jsonl").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        instance._prepare_artifacts()


def test_s2_provenance_retains_resolved_corpus_paths(tmp_path, monkeypatch, payload):
    for name in ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"):
        payload[f"data/raw/multilingual-e5-base/{name}"] = b"fixture"
    for name in ("manifest.json", "vectors.npy", "chunks.jsonl"):
        payload[f"indexes/e5_s2/{name}"] = b"fixture"
    instance = prepared_service(tmp_path, monkeypatch, payload)
    instance.cfg["semantic_system"] = "e5_s2"
    instance._prepare_artifacts()
    assert instance.spaths["articles"] == tmp_path / "artifacts/data/processed/articles_index.jsonl"
    assert instance.spaths["docs"] == tmp_path / "artifacts/data/processed/docs_index.jsonl"
