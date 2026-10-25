"""Build/load offline E5 S2 and export unlabelled article candidates."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import os
import platform
import random
import sys
import time
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.common import (  # noqa: E402
    export_run,
    file_hash,
    read_jsonl,
    read_queries,
    valid_id,
    validate_corpus,
)
from src.retrieval.e5_format import PASSAGE_PREFIX, QUERY_PREFIX  # noqa: E402


def prepare_runtime(cfg: dict) -> dict:
    runtime = cfg["runtime"]
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = runtime["cublas_workspace_config"]
    import torch

    if type(runtime["cpu_threads"]) is not int or runtime["cpu_threads"] <= 0:
        raise ValueError("cpu_threads must be positive")
    torch.set_num_threads(runtime["cpu_threads"])
    torch.use_deterministic_algorithms(runtime["deterministic"])
    torch.backends.cuda.matmul.allow_tf32 = runtime["allow_tf32"]
    torch.backends.cudnn.allow_tf32 = runtime["allow_tf32"]
    random.seed(cfg["seed"])
    np.random.seed(cfg["seed"])
    torch.manual_seed(cfg["seed"])
    device = torch.device(runtime["device"])
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError(
            "Configured CUDA device unavailable; select CPU explicitly in config"
        )
    return {
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }


def provenance(cfg: dict, paths: dict[str, Path]) -> dict:
    versions = {}
    for package, expected in cfg["versions"].items():
        installed = importlib.metadata.version(package)
        comparable = installed.split("+")[0] if package == "torch" else installed
        if comparable != str(expected):
            raise ValueError(f"Version mismatch: {package}: {installed} != {expected}")
        versions[package] = comparable
    try:
        versions["sentence-transformers"] = importlib.metadata.version(
            "sentence-transformers"
        )
    except importlib.metadata.PackageNotFoundError:
        versions["sentence-transformers"] = (
            None  # Direct AutoModel encoder does not depend on it.
        )
    downloaded = json.loads(
        (paths["model"] / "download.json").read_text(encoding="utf-8")
    )
    if downloaded["model"] != cfg["model"] or set(downloaded["files"]) != set(
        cfg["model"]["files"]
    ):
        raise ValueError("Downloaded model manifest mismatch")
    for name, checksum in downloaded["files"].items():
        if Path(name).name != name or file_hash(paths["model"] / name) != checksum:
            raise ValueError(f"Model checksum mismatch: {name}")
    return {
        "sources": {
            name: file_hash(paths[name]) for name in ("chunks", "articles", "docs")
        },
        "model": cfg["model"],
        "model_files": downloaded["files"],
        "versions": versions,
        "python": platform.python_version(),
        "query_prefix": QUERY_PREFIX,
        "passage_prefix": PASSAGE_PREFIX,
        "runtime": cfg["runtime"],
        "seed": cfg["seed"],
        "preprocessing_version": cfg["encoding"]["preprocessing_version"],
    }


def run(
    cfg: dict,
    config_path: Path,
    build: bool,
    query_override: Path | None,
    output_override: Path | None = None,
) -> dict:
    top_k, tag = cfg["retrieval"]["top_k"], cfg["retrieval"]["run_tag"]
    if type(top_k) is not int or top_k <= 0 or not valid_id(tag):
        raise ValueError("Invalid retrieval top_k/run_tag")
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    if query_override is not None:
        paths["queries"] = query_override
    if output_override is not None:
        paths["output"] = output_override
    for output in ("index", "output"):
        target = paths[output].resolve()
        for name, value in paths.items():
            if name == output:
                continue
            other = value.resolve()
            if target == other or target in other.parents or other in target.parents:
                raise ValueError(f"Overlapping paths: {output}/{name}")
    if paths["output"].exists() or (build and paths["index"].exists()):
        raise FileExistsError("Index/output already exists; choose new paths")
    queries = read_queries(paths["queries"])
    chunks = read_jsonl(paths["chunks"])
    arts, docs = validate_corpus(
        chunks, read_jsonl(paths["articles"]), read_jsonl(paths["docs"])
    )
    source = provenance(cfg, paths)
    hardware = prepare_runtime(cfg)
    from src.retrieval.e5 import E5Encoder, E5Retriever

    encoder = E5Encoder.load(paths["model"], cfg["encoding"], cfg["runtime"]["device"])
    settings = {"chunk_top_k": cfg["retrieval"]["chunk_top_k"]}
    started = time.perf_counter()
    if build:
        retriever = E5Retriever.build(chunks, encoder, settings)
        retriever.save(paths["index"], source)
    else:
        retriever = E5Retriever.load(paths["index"], encoder, settings, source)
    index_seconds = time.perf_counter() - started
    logging.info("Hardware: %s", hardware)
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
        execution=hardware,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    try:
        summary = run(cfg, args.config, args.build, args.queries, args.output)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        parser.exit(1, f"E5 failed: {exc}\n")
    logging.info(
        "Finished: %d queries, %d candidates",
        summary["n_queries"],
        summary["n_candidates"],
    )


if __name__ == "__main__":
    main()
