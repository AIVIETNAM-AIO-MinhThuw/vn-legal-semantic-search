"""Bi-encoder tổng quát cho SBERT đa ngôn ngữ và E5 fine-tune (mean pooling, L2-normalize).

Khác E5Encoder (S2): cho phép tắt tiền tố, đặt max_length và truncation theo model; dùng chung MaxP
(`rank_articles`) và thứ tự chunk với S2 nên điểm số các hệ thống so sánh được.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from src.retrieval.common import rank_articles, validate_chunks


def mean_pool(hidden, mask):
    m = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * m).sum(1) / m.sum(1).clamp(min=1e-9)


class DenseEncoder:
    def __init__(self, path: Path, settings: dict, device: str):
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
        target.mkdir(parents=True, exist_ok=False)
        np.save(target / "vectors.npy", self.vectors, allow_pickle=False)
        ids = [c["chunk_id"] for c in self.chunks]
        (target / "chunk_ids.json").write_text(json.dumps(ids), encoding="utf-8")
        meta = {**meta, "n_chunks": len(ids),
                "vectors_sha256": hashlib.sha256((target / "vectors.npy").read_bytes()).hexdigest()}
        (target / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, target: Path, chunks, encoder, chunk_top_k=200):
        meta = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if hashlib.sha256((target / "vectors.npy").read_bytes()).hexdigest() != meta["vectors_sha256"]:
            raise ValueError("Dense index checksum mismatch")
        by_id = {c["chunk_id"]: c for c in chunks}
        ids = json.loads((target / "chunk_ids.json").read_text(encoding="utf-8"))
        return cls([by_id[i] for i in ids], np.load(target / "vectors.npy"), encoder, chunk_top_k)

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
