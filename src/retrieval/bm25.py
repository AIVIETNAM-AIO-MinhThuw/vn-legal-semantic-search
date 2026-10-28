"""BM25S chunk index, checked persistence and deterministic article MaxP."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import math
import os
import platform
import shutil
import tempfile
from pathlib import Path

import bm25s

from src.retrieval.text import java_version, word_tokens
from src.retrieval.common import (
    file_hash as file_hash,
    read_jsonl as read_jsonl,
    write_jsonl as write_jsonl,
    valid_id as valid_id,
    validate_chunks as validate_chunks,
    rank_articles,
)

LOG = logging.getLogger(__name__)


def provenance(cfg: dict, paths: dict[str, Path], *, model_dir: Path | None = None) -> dict:
    """Actual runtime identity, shared by evaluation and app; paths are IO locations only."""
    for package, expected in cfg["versions"].items():
        if importlib.metadata.version(package) != str(expected):
            raise ValueError(f"Version mismatch: {package}")
    settings = cfg["segmenter"]
    if settings["annotators"] != ["wseg"]:
        raise ValueError("Only wseg is supported")
    prep = cfg["preprocessing"]
    if (prep["unicode"] != "NFC" or not prep["lowercase_after_segmentation"]
            or not prep["remove_punctuation_only"] or prep["remove_stopwords"] or prep["stemming"]):
        raise ValueError("Unsupported preprocessing config")
    model = Path(model_dir) if model_dir is not None else Path(settings["model_dir"])
    if (model / "revision.txt").read_text(encoding="utf-8").strip() != settings["revision"]:
        raise ValueError("VNCoreNLP revision mismatch")
    return {
        "sources": {name: file_hash(paths[name]) for name in ("chunks", "articles", "docs")},
        "segmenter": settings,
        "segmenter_files": {name: file_hash(model / name) for name in settings["files"]},
        "java": java_version(settings), "preprocessing": prep,
        "versions": {p: importlib.metadata.version(p) for p in cfg["versions"]},
        "numerics": {p: importlib.metadata.version(p) for p in ("numpy", "scipy")},
        "python": platform.python_version(),
    }


def validate_settings(settings: dict) -> None:
    if not math.isfinite(settings["k1"]) or settings["k1"] <= 0:
        raise ValueError("k1 must be finite and positive")
    if not math.isfinite(settings["b"]) or not 0 <= settings["b"] <= 1:
        raise ValueError("b must be finite and between zero and one")
    if settings["method"] not in {"lucene", "robertson", "atire", "bm25l", "bm25+"}:
        raise ValueError("Unsupported BM25 method")
    if settings["ngram_range"] != [1, 1]:
        raise ValueError("This baseline requires word unigrams")
    if type(settings["chunk_top_k"]) is not int or settings["chunk_top_k"] <= 0:
        raise ValueError("chunk_top_k must be positive")
    if (
        type(settings["log_every_chunks"]) is not int
        or settings["log_every_chunks"] <= 0
    ):
        raise ValueError("log_every_chunks must be positive")


class BM25Retriever:
    def __init__(self, index, chunks: list[dict], settings: dict, segmenter):
        self.index = index
        self.chunks = chunks
        self.settings = settings
        self.segmenter = segmenter

    @classmethod
    def build(cls, chunks: list[dict], settings: dict, segmenter) -> BM25Retriever:
        validate_settings(settings)
        validate_chunks(chunks)
        chunks = sorted(chunks, key=lambda c: (c["article_id"], c["chunk_index"]))
        tokens = []
        for row in chunks:
            try:
                tokenized = word_tokens(row["text"], segmenter)
            except Exception as exc:
                raise ValueError(f"Segmentation failed: {row['chunk_id']}") from exc
            if not tokenized:
                raise ValueError(f"No word tokens: {row['chunk_id']}")
            tokens.append(tokenized)
            if len(tokens) % settings["log_every_chunks"] == 0:
                LOG.info("Segmented %d/%d chunks", len(tokens), len(chunks))
        index = bm25s.BM25(
            k1=settings["k1"],
            b=settings["b"],
            method=settings["method"],
            backend="numpy",
        )
        index.index(tokens, show_progress=False)
        return cls(index, chunks, settings.copy(), segmenter)

    def search(
        self, query: str, k: int, filters: dict | None = None
    ) -> list[tuple[str, float]]:
        if type(k) is not int or k <= 0:
            raise ValueError("k must be positive")
        if filters:
            raise ValueError("Baseline evaluation does not support app filters")
        tokens = word_tokens(query, self.segmenter)
        if not tokens:
            return []
        scores = self.index.get_scores(tokens)
        return rank_articles(self.chunks, scores, self.settings["chunk_top_k"], k)

    def save(self, target: Path, provenance: dict) -> None:
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
        try:
            self.index.save(str(staging))
            write_jsonl(staging / "chunks.jsonl", self.chunks)
            manifest = {
                "settings": self.settings,
                "provenance": provenance,
                "bm25s": importlib.metadata.version("bm25s"),
                "n_chunks": len(self.chunks),
                "files": {
                    p.name: file_hash(p) for p in staging.iterdir() if p.is_file()
                },
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
        cls, target: Path, settings: dict, segmenter, provenance: dict
    ) -> BM25Retriever:
        validate_settings(settings)
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if (
            manifest["settings"] != settings
            or manifest["provenance"] != provenance
            or manifest["bm25s"] != importlib.metadata.version("bm25s")
        ):
            raise ValueError("BM25 manifest mismatch")
        actual_files = {
            p.name
            for p in target.iterdir()
            if p.is_file() and p.name != "manifest.json"
        }
        if set(manifest["files"]) != actual_files or "chunks.jsonl" not in actual_files:
            raise ValueError("Index manifest file inventory mismatch")
        for name, checksum in manifest["files"].items():
            path = target / name
            if (
                Path(name).name != name
                or not path.is_file()
                or file_hash(path) != checksum
            ):
                raise ValueError(f"Index checksum mismatch: {name}")
        chunks = read_jsonl(target / "chunks.jsonl")
        validate_chunks(chunks)
        if len(chunks) != manifest["n_chunks"]:
            raise ValueError("Index chunk count mismatch")
        if chunks != sorted(chunks, key=lambda c: (c["article_id"], c["chunk_index"])):
            raise ValueError("Index chunk order mismatch")
        index = bm25s.BM25.load(str(target), load_corpus=False)
        return cls(index, chunks, settings.copy(), segmenter)
