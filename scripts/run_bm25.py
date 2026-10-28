"""Build/load S1₀ and export TREC runs plus unlabelled article candidates."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.bm25 import BM25Retriever, provenance, validate_settings  # noqa: E402
from src.retrieval.common import (  # noqa: E402
    file_hash,
    read_jsonl,
    valid_id,
    read_queries as read_queries,
    validate_corpus as validate_corpus,
    export_run,
)
from src.retrieval.text import load_segmenter  # noqa: E402

LOG = logging.getLogger(__name__)


def run(
    cfg: dict,
    config_path: Path,
    build: bool,
    query_override: Path | None,
    output_override: Path | None = None,
) -> dict:
    validate_settings(cfg["bm25"])
    top_k = cfg["retrieval"]["top_k"]
    tag = cfg["retrieval"]["run_tag"]
    if type(top_k) is not int or top_k <= 0 or not valid_id(tag):
        raise ValueError("Invalid retrieval top_k/run_tag")
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    if query_override is not None:
        paths["queries"] = query_override
    if output_override is not None:
        paths["output"] = output_override
    index_path, output_path = paths["index"].resolve(), paths["output"].resolve()
    if (
        index_path == output_path
        or index_path in output_path.parents
        or output_path in index_path.parents
    ):
        raise ValueError("Index and output directories must be separate")
    for name in ("index", "output"):
        target = paths[name].resolve()
        for source in ("chunks", "articles", "docs", "queries"):
            if (
                target == paths[source].resolve()
                or target in paths[source].resolve().parents
            ):
                raise ValueError(f"Output contains source: {name}/{source}")
    if paths["output"].exists():
        raise FileExistsError(paths["output"])
    if build and paths["index"].exists():
        raise FileExistsError(paths["index"])
    queries = read_queries(paths["queries"])
    chunks = read_jsonl(paths["chunks"])
    arts, docs = validate_corpus(
        chunks, read_jsonl(paths["articles"]), read_jsonl(paths["docs"])
    )
    source = provenance(cfg, paths)
    segmenter = load_segmenter(cfg["segmenter"])
    started = time.perf_counter()
    if build:
        retriever = BM25Retriever.build(chunks, cfg["bm25"], segmenter)
        retriever.save(paths["index"], source)
    else:
        retriever = BM25Retriever.load(paths["index"], cfg["bm25"], segmenter, source)
    index_seconds = time.perf_counter() - started
    return export_run(
        retriever,
        queries,
        arts,
        docs,
        paths,
        cfg,
        config_path,
        source,
        build,
        index_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--queries", type=Path, help="Override CSV path without changing the input"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="New output directory; existing results are never overwritten",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build a new index; otherwise load existing index",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    try:
        summary = run(cfg, args.config, args.build, args.queries, args.output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"BM25 failed: {exc}\n")
    LOG.info(
        "Finished: %d queries, %d candidates",
        summary["n_queries"],
        summary["n_candidates"],
    )


if __name__ == "__main__":
    main()
