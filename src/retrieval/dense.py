"""Bi-encoder tổng quát cho SBERT đa ngôn ngữ và E5 fine-tune (mean pooling, L2-normalize).

Khác E5Encoder (S2): cho phép tắt tiền tố, đặt max_length và truncation theo model; dùng chung MaxP
(`rank_articles`) và thứ tự chunk với S2 nên điểm số các hệ thống so sánh được.
"""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from src.retrieval.common import file_hash, read_jsonl, rank_articles, validate_chunks


def model_fingerprint(path: Path) -> dict:
    return {p.name: file_hash(p) for p in sorted(Path(path).iterdir())
            if p.is_file() and p.suffix in {".json", ".safetensors", ".model", ".txt"}}


def runtime_versions() -> dict:
    versions = {}
    for name in ("transformers", "tokenizers", "sentence-transformers", "torch"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValueError(f"Dense runtime missing dependency: {name}") from exc
    versions["torch"] = versions["torch"].split("+")[0]
    return versions


def encoder_manifest(encoder, files: dict) -> dict:
    config = json.loads((encoder.path / "config.json").read_text(encoding="utf-8"))
    return {
        "model_name": config.get("_name_or_path") or config.get("model_type"),
        "model_revision": files["model.safetensors"],
        "tokenizer": type(encoder.tok).__name__,
        "settings": encoder.s,
        "pooling": "mean", "normalize": True, "dtype": "float32",
        "dimension": encoder.model.config.hidden_size,
        "preprocessing_version": "dense-prefix-only-v1",
    }


def mean_pool(hidden, mask):
    m = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * m).sum(1) / m.sum(1).clamp(min=1e-9)


class DenseEncoder:
    def __init__(self, path: Path, settings: dict, device: str):
        self.path = Path(path)
        self.s = dict(settings)
        self.device = torch.device(device)
        self.tok = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(path), local_files_only=True, use_safetensors=True)
        self.model.to(self.device).eval()
        self.truncated = 0

    def _prep(self, texts, kind):
        pre = self.s.get("query_prefix" if kind == "query" else "passage_prefix", "")
        return [pre + t for t in texts]

    @torch.inference_mode()
    def encode(self, texts: list[str], kind: str) -> np.ndarray:
        out = []
        bs = self.s["batch_size"]
        ml = self.s["max_length"]
        use_amp = self.device.type == "cuda" and self.s.get("fp16_inference", False)
        for i in range(0, len(texts), bs):
            batch = self._prep(texts[i:i + bs], kind)
            full = self.tok(batch, padding=False, truncation=False)["input_ids"]
            self.truncated += sum(1 for x in full if len(x) > ml)
            enc = self.tok(batch, padding=True, truncation=True, max_length=ml, return_tensors="pt").to(self.device)
            with torch.autocast("cuda", dtype=torch.float16, enabled=use_amp):
                h = self.model(**enc).last_hidden_state
            v = F.normalize(mean_pool(h.float(), enc["attention_mask"]), p=2, dim=1)
            out.append(v.cpu().numpy().astype(np.float32))
        return np.concatenate(out) if out else np.empty((0, self.model.config.hidden_size), np.float32)


class DenseRetriever:
    def __init__(self, chunks, vectors, encoder, chunk_top_k=200):
        self.chunks, self.vectors, self.encoder, self.chunk_top_k = chunks, vectors, encoder, chunk_top_k

    @classmethod
    def build(cls, chunks, encoder, chunk_top_k=200):
        validate_chunks(chunks)
        chunks = sorted(chunks, key=lambda c: (c["article_id"], c["chunk_index"]))
        return cls(chunks, encoder.encode([c["text"] for c in chunks], "passage"), encoder, chunk_top_k)

    def save(self, target: Path, meta: dict):
        files = model_fingerprint(self.encoder.path)
        identity = encoder_manifest(self.encoder, files)
        versions = runtime_versions()
        target.mkdir(parents=True, exist_ok=False)
        np.save(target / "vectors.npy", self.vectors, allow_pickle=False)
        ids = [c["chunk_id"] for c in self.chunks]
        (target / "chunk_ids.json").write_text(json.dumps(ids), encoding="utf-8")
        meta = {**meta, "model_files": files, "versions": versions, "encoder": identity,
                "n_chunks": len(ids), "vectors_sha256": file_hash(target / "vectors.npy")}
        (target / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, target: Path, chunks, encoder, chunk_top_k=200, *, chunks_path: Path):
        meta = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        required = {"versions", "encoder", "config", "model_files", "chunks_sha256", "n_chunks", "vectors_sha256"}
        if not isinstance(meta, dict) or not required <= meta.keys():
            raise ValueError("Dense manifest missing required metadata; frozen artifacts must not be patched at runtime")
        versions = runtime_versions()
        saved_versions = meta["versions"]
        if not isinstance(saved_versions, dict) or not versions.keys() <= saved_versions.keys():
            raise ValueError("Dense manifest missing dependency versions")
        for name, actual in versions.items():
            expected = saved_versions[name]
            if name == "torch" and isinstance(expected, str):
                expected = expected.split("+")[0]
            if expected != actual:
                raise ValueError(f"Dense manifest version mismatch: {name}: {expected!r} != {actual!r}")
        files = model_fingerprint(encoder.path)
        if meta["model_files"] != files or meta["encoder"] != encoder_manifest(encoder, files):
            raise ValueError("Dense manifest model/tokenizer/encoding mismatch")
        config = meta["config"]
        if (not isinstance(config, dict) or config.get("encoding") != encoder.s
                or config.get("retrieval", {}).get("chunk_top_k") != chunk_top_k):
            raise ValueError("Dense manifest config mismatch")
        if file_hash(chunks_path) != meta["chunks_sha256"] or chunks != read_jsonl(chunks_path):
            raise ValueError("Dense manifest source chunks mismatch")
        validate_chunks(chunks)
        if file_hash(target / "vectors.npy") != meta["vectors_sha256"]:
            raise ValueError("Dense index checksum mismatch")
        ordered = sorted(chunks, key=lambda c: (c["article_id"], c["chunk_index"]))
        ids = json.loads((target / "chunk_ids.json").read_text(encoding="utf-8"))
        if ids != [c["chunk_id"] for c in ordered] or type(meta["n_chunks"]) is not int or meta["n_chunks"] != len(ids):
            raise ValueError("Dense manifest chunk inventory/order mismatch")
        vectors = np.load(target / "vectors.npy", allow_pickle=False)
        if (vectors.dtype != np.float32 or vectors.shape != (len(ids), encoder.model.config.hidden_size)
                or not np.isfinite(vectors).all()
                or not np.allclose(np.linalg.norm(vectors, axis=1), 1., atol=1e-5)):
            raise ValueError("Dense manifest vectors shape/dtype/normalization mismatch")
        return cls(ordered, vectors, encoder, chunk_top_k)

    def search(self, query: str, k: int, allowed_articles: set | None = None):
        if not query.strip():
            return []
        q = self.encoder.encode([query], "query")[0]
        scores = self.vectors @ q
        if allowed_articles is not None:
            mask = np.array([c["article_id"] in allowed_articles for c in self.chunks])
            if not mask.any():
                return []
            scores = np.where(mask, scores, -1e9)
        return rank_articles(self.chunks, scores, self.chunk_top_k, k)
