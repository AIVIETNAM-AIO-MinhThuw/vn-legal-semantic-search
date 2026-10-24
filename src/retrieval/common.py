"""Shared corpus IO, deterministic MaxP and blind run exports for both baselines."""

from __future__ import annotations
import csv
import hashlib
import json
import logging
import os
import random
import shutil
import tempfile
import time
from pathlib import Path
import numpy as np

LOG = logging.getLogger(__name__)


def file_hash(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = []
        for line_no, line in enumerate(f, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected object")
            rows.append(row)
        return rows


def write_jsonl(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def valid_id(value) -> bool:
    return (
        isinstance(value, str) and bool(value) and not any(c.isspace() for c in value)
    )


def validate_chunks(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Empty corpus")
    ids, positions = set(), set()
    for row in rows:
        if any(not valid_id(row.get(k)) for k in ("chunk_id", "article_id", "doc_id")):
            raise ValueError("Missing/invalid chunk, article or document ID")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError(f"Empty chunk text: {row['chunk_id']}")
        position = row.get("chunk_index")
        if type(position) is not int or position < 0:
            raise ValueError(f"Invalid chunk_index: {row['chunk_id']}")
        key = (row["article_id"], position)
        if row["chunk_id"] in ids or key in positions:
            raise ValueError(f"Duplicate chunk: {row['chunk_id']}")
        ids.add(row["chunk_id"])
        positions.add(key)


def read_queries(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not {"query_id", "query"} <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: required columns query_id, query")
        rows = list(reader)
    seen = set()
    for row in rows:
        qid, text = row.get("query_id"), row.get("query")
        if (
            not valid_id(qid)
            or qid in seen
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValueError(
                f"{path}: duplicate/invalid query ID or empty query: {qid}"
            )
        seen.add(qid)
    if not rows:
        raise ValueError(f"{path}: empty queries")
    return [{"query_id": r["query_id"], "query": r["query"]} for r in rows]


def keyed(rows: list[dict], field: str) -> dict:
    result = {}
    for row in rows:
        key = row.get(field)
        if not valid_id(key) or key in result:
            raise ValueError(f"Invalid/duplicate {field}: {key}")
        result[key] = row
    if not result:
        raise ValueError(f"Empty {field} table")
    return result


def validate_corpus(
    chunks: list[dict], articles: list[dict], docs: list[dict]
) -> tuple[dict, dict]:
    validate_chunks(chunks)
    arts, documents = keyed(articles, "article_id"), keyed(docs, "doc_id")
    for article in articles:
        if (
            article.get("doc_id") not in documents
            or not isinstance(article.get("body"), str)
            or not article["body"].strip()
        ):
            raise ValueError(f"Orphan/empty article: {article['article_id']}")
    for chunk in chunks:
        article = arts.get(chunk["article_id"])
        if article is None or article["doc_id"] != chunk["doc_id"]:
            raise ValueError(f"Orphan/inconsistent chunk: {chunk['chunk_id']}")
    return arts, documents


def rank_articles(
    chunks: list[dict], scores: np.ndarray, chunk_top_k: int, k: int
) -> list[tuple[str, float]]:
    if type(k) is not int or k <= 0 or type(chunk_top_k) is not int or chunk_top_k <= 0:
        raise ValueError("Retrieval depths must be positive")
    if scores.shape != (len(chunks),) or not np.isfinite(scores).all():
        raise ValueError("Invalid chunk scores")
    # Both indexes store chunks ordered by article_id/chunk_index; stable sorting fixes cutoff ties.
    order = np.argsort(-scores, kind="stable")[:chunk_top_k]
    articles = {}
    for i in order:
        articles.setdefault(chunks[i]["article_id"], float(scores[i]))
    return sorted(articles.items(), key=lambda item: (-item[1], item[0]))[:k]


def export_run(
    retriever,
    queries: list[dict],
    arts: dict,
    docs: dict,
    paths: dict,
    cfg: dict,
    config_path: Path,
    source: dict,
    build: bool,
    index_seconds: float,
    execution: dict | None = None,
) -> dict:
    top_k, tag = cfg["retrieval"]["top_k"], cfg["retrieval"]["run_tag"]
    paths["output"].parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=paths["output"].name + ".", dir=paths["output"].parent)
    )
    candidates, timings, warnings = [], [], []
    rng = random.Random(cfg["seed"])
    try:
        with (staging / "run.trec").open(
            "w", encoding="utf-8", newline="\n"
        ) as run_file:
            for query in queries:
                query_candidates = []
                started = time.perf_counter()
                results = retriever.search(query["query"], top_k, None)
                timings.append(time.perf_counter() - started)
                if len(results) < top_k or (results and results[0][1] == 0):
                    warnings.append(
                        {
                            "query_id": query["query_id"],
                            "returned": len(results),
                            "all_zero": bool(results and results[0][1] == 0),
                        }
                    )
                for rank, (article_id, score) in enumerate(results, 1):
                    run_file.write(
                        f"{query['query_id']} Q0 {article_id} {rank} {score:.9g} {tag}\n"
                    )
                    article = arts[article_id]
                    # Blind input deliberately contains no source-query metadata or retrieval scores.
                    query_candidates.append(
                        {
                            **query,
                            "article_id": article_id,
                            "article": article,
                            "document": docs[article["doc_id"]],
                        }
                    )
                rng.shuffle(query_candidates)
                candidates.extend(query_candidates)
                LOG.info("Retrieved %s: %d articles", query["query_id"], len(results))
        write_jsonl(staging / "candidates.jsonl", candidates)
        write_jsonl(staging / "warnings.jsonl", warnings)
        summary = {
            "system": tag,
            "n_queries": len(queries),
            "n_chunks": len(retriever.chunks),
            "n_candidates": len(candidates),
            "warnings": len(warnings),
            "index_mode": "build" if build else "load",
            "index_seconds": index_seconds,
            "query_seconds": timings,
            "query_sha256": file_hash(paths["queries"]),
            "config_sha256": file_hash(config_path),
            "effective_config": cfg,
            "query_path": str(paths["queries"].resolve()),
            "provenance": source,
            "index_manifest_sha256": file_hash(paths["index"] / "manifest.json"),
            "index_bytes": sum(
                p.stat().st_size for p in paths["index"].rglob("*") if p.is_file()
            ),
            "outputs": {p.name: file_hash(p) for p in staging.iterdir()},
            "quality_metrics": "NOT RUN: unlabelled candidates",
        }
        if execution is not None:
            summary["execution"] = execution
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.rename(staging, paths["output"])
        return summary
    finally:
        if staging.exists():
            shutil.rmtree(staging)
