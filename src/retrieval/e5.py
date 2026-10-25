"""Offline fp32 multilingual E5 encoder and exact article retriever."""

from __future__ import annotations

import json
import importlib.metadata
import logging
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from src.retrieval.common import (
    file_hash,
    rank_articles,
    read_jsonl,
    validate_chunks,
    write_jsonl,
)
from src.retrieval.e5_format import format_passage, format_query
from src.retrieval.text import normalize_query

LOG = logging.getLogger(__name__)


def dependency_versions() -> dict:
    versions = {}
    for package in (
        "torch",
        "transformers",
        "tokenizers",
        "sentence-transformers",
        "numpy",
        "safetensors",
    ):
        try:
            value = importlib.metadata.version(package)
            versions[package] = value.split("+")[0] if package == "torch" else value
        except importlib.metadata.PackageNotFoundError:
            if package != "sentence-transformers":
                raise
            versions[package] = None
    return versions


def mean_pool(hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    counts = mask.sum(dim=1)
    if torch.any(counts == 0):
        raise ValueError("Empty attention mask")
    return hidden.masked_fill(~mask[..., None].bool(), 0).sum(dim=1) / counts[..., None]


def check_encoding(settings: dict) -> None:
    if (
        not isinstance(settings["preprocessing_version"], str)
        or not settings["preprocessing_version"].strip()
    ):
        raise ValueError("A preprocessing version is required")
    for key in ("max_length", "batch_size", "dimension", "log_every_batches"):
        if type(settings[key]) is not int or settings[key] <= 0:
            raise ValueError(f"Invalid encoding {key}")
    if (
        settings["dtype"] != "float32"
        or settings["pooling"] != "mean"
        or settings["normalize"] is not True
    ):
        raise ValueError("E5 requires fp32, mean pooling and L2 normalization")
    if not np.isfinite(settings["norm_atol"]) or settings["norm_atol"] <= 0:
        raise ValueError("Invalid norm tolerance")


class E5Encoder:
    def __init__(self, tokenizer, model, settings: dict, device: str):
        check_encoding(settings)
        self.tokenizer = tokenizer
        self.settings = settings.copy()
        self.device = torch.device(device)
        self.model = model.to(device=self.device, dtype=torch.float32).eval()

    @classmethod
    def load(cls, path: Path, settings: dict, device: str) -> E5Encoder:
        tokenizer = AutoTokenizer.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False
        )
        model = AutoModel.from_pretrained(
            str(path),
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            torch_dtype=torch.float32,
            attn_implementation=settings["attention"],
        )
        if model.config.hidden_size != settings["dimension"]:
            raise ValueError("Model embedding dimension differs from config")
        return cls(tokenizer, model, settings, device)

    def encode(self, texts: list[str], kind: str) -> np.ndarray:
        if kind not in {"query", "passage"}:
            raise ValueError("Expected query or passage")
        if not texts:
            return np.empty((0, self.settings["dimension"]), dtype=np.float32)
        prefix = format_query if kind == "query" else format_passage
        prepared = []
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Empty {kind}")
            normalized = normalize_query(text) if kind == "query" else text
            prepared.append(prefix(normalized))
        batches = []
        batch_size = self.settings["batch_size"]
        with (
            torch.inference_mode(),
            torch.autocast(device_type=self.device.type, enabled=False),
        ):
            for start in range(0, len(prepared), batch_size):
                encoded = self.tokenizer(
                    prepared[start : start + batch_size],
                    padding=True,
                    truncation=False,
                    return_tensors="pt",
                )
                lengths = encoded["attention_mask"].sum(dim=1)
                if torch.any(lengths > self.settings["max_length"]):
                    bad = start + int(torch.argmax(lengths).item())
                    raise ValueError(
                        f"{kind} length exceeds max_length at input {bad}: {int(lengths.max())}"
                    )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                hidden = self.model(**encoded).last_hidden_state
                vectors = F.normalize(
                    mean_pool(hidden, encoded["attention_mask"]), p=2, dim=1
                )
                array = vectors.cpu().numpy().astype(np.float32, copy=False)
                if not np.isfinite(array).all() or not np.allclose(
                    np.linalg.norm(array, axis=1),
                    1,
                    atol=self.settings["norm_atol"],
                    rtol=0,
                ):
                    raise ValueError("Invalid normalized E5 vectors")
                batches.append(array)
                if (start // batch_size + 1) % self.settings["log_every_batches"] == 0:
                    LOG.info(
                        "Encoded %d/%d %s inputs",
                        min(start + batch_size, len(prepared)),
                        len(prepared),
                        kind,
                    )
        return np.concatenate(batches)


class E5Retriever:
    def __init__(
        self,
        chunks: list[dict],
        vectors: np.ndarray,
        encoder: E5Encoder,
        settings: dict,
    ):
        if type(settings["chunk_top_k"]) is not int or settings["chunk_top_k"] <= 0:
            raise ValueError("Invalid chunk_top_k")
        self.chunks, self.vectors, self.encoder = chunks, vectors, encoder
        self.settings = settings.copy()

    @classmethod
    def build(
        cls, chunks: list[dict], encoder: E5Encoder, settings: dict
    ) -> E5Retriever:
        validate_chunks(chunks)
        chunks = sorted(chunks, key=lambda c: (c["article_id"], c["chunk_index"]))
        vectors = encoder.encode([c["text"] for c in chunks], "passage")
        return cls(chunks, vectors, encoder, settings)

    def search(
        self, query: str, k: int, filters: dict | None = None
    ) -> list[tuple[str, float]]:
        if type(k) is not int or k <= 0:
            raise ValueError("k must be positive")
        if filters:
            raise ValueError("Baseline evaluation does not support app filters")
        if not isinstance(query, str):
            raise ValueError("Query must be a string")
        if not query.strip():
            return []
        vector = self.encoder.encode([query], "query")[0]
        scores = self.vectors @ vector
        return rank_articles(self.chunks, scores, self.settings["chunk_top_k"], k)

    def save(self, target: Path, provenance: dict) -> None:
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
        try:
            np.save(staging / "vectors.npy", self.vectors, allow_pickle=False)
            write_jsonl(staging / "chunks.jsonl", self.chunks)
            manifest = {
                "settings": self.settings,
                "encoding": self.encoder.settings,
                "libraries": dependency_versions(),
                "provenance": provenance,
                "n_chunks": len(self.chunks),
                "files": {p.name: file_hash(p) for p in staging.iterdir()},
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.rename(staging, target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    @classmethod
    def load(
        cls, target: Path, encoder: E5Encoder, settings: dict, provenance: dict
    ) -> E5Retriever:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if manifest["libraries"] != dependency_versions():
            raise ValueError("E5 dependency versions differ from index manifest")
        if (
            manifest["settings"] != settings
            or manifest["encoding"] != encoder.settings
            or manifest["provenance"] != provenance
        ):
            raise ValueError("E5 manifest mismatch")
        if set(manifest["files"]) != {"vectors.npy", "chunks.jsonl"}:
            raise ValueError("E5 manifest inventory mismatch")
        for name, checksum in manifest["files"].items():
            path = target / name
            if not path.is_file() or file_hash(path) != checksum:
                raise ValueError(f"E5 index checksum mismatch: {name}")
        chunks = read_jsonl(target / "chunks.jsonl")
        validate_chunks(chunks)
        if len(chunks) != manifest["n_chunks"] or chunks != sorted(
            chunks, key=lambda c: (c["article_id"], c["chunk_index"])
        ):
            raise ValueError("E5 index mapping mismatch")
        vectors = np.load(target / "vectors.npy", allow_pickle=False)
        if (
            vectors.dtype != np.float32
            or vectors.shape != (len(chunks), encoder.settings["dimension"])
            or not np.isfinite(vectors).all()
        ):
            raise ValueError("Invalid E5 vector matrix")
        if not np.allclose(
            np.linalg.norm(vectors, axis=1),
            1,
            atol=encoder.settings["norm_atol"],
            rtol=0,
        ):
            raise ValueError("E5 vector matrix is not L2 normalized")
        return cls(chunks, vectors, encoder, settings)
