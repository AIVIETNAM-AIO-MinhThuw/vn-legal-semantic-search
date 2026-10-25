"""Chạy truy hồi dense (SBERT đa ngôn ngữ / E5 fine-tune) và xuất run.trec + summary.json.

python -X utf8 scripts/run_dense.py --config configs/dense_sbert.yaml --queries data/eval_v1/queries_test.csv \
    --output runs/test/sbert [--build]
"""
from __future__ import annotations

import argparse, hashlib, json, platform, random, sys, time
from pathlib import Path

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval.common import read_jsonl, read_queries  # noqa: E402
from src.retrieval.dense import DenseEncoder, DenseRetriever  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def model_fingerprint(path: Path) -> dict:
    return {p.name: sha(p) for p in sorted(Path(path).iterdir()) if p.is_file() and p.suffix in {".json", ".safetensors", ".model", ".txt"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--queries", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--model", type=Path, help="ghi đè paths.model")
    ap.add_argument("--index", type=Path, help="ghi đè paths.index")
    ap.add_argument("--tag", help="ghi đè retrieval.run_tag")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    if a.model: cfg["paths"]["model"] = str(a.model)
    if a.index: cfg["paths"]["index"] = str(a.index)
    if a.tag: cfg["retrieval"]["run_tag"] = a.tag
    if a.output.exists():
        sys.exit(f"Output đã tồn tại: {a.output}")
    seed = cfg.get("seed", 42)
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    device = cfg["runtime"]["device"]
    if device == "cuda" and not torch.cuda.is_available():
        sys.exit("CUDA không có; đặt runtime.device: cpu nếu muốn chạy CPU")
    paths = {k: Path(v) for k, v in cfg["paths"].items()}
    enc = DenseEncoder(paths["model"], cfg["encoding"], device)
    chunks = read_jsonl(paths["chunks"])
    t0 = time.perf_counter()
    if a.build:
        if paths["index"].exists():
            sys.exit(f"Index đã tồn tại: {paths['index']}")
        r = DenseRetriever.build(chunks, enc, cfg["retrieval"]["chunk_top_k"])
        r.save(paths["index"], {"config": cfg, "model_files": model_fingerprint(paths["model"]),
                                "chunks_sha256": sha(paths["chunks"]), "truncated_passages": enc.truncated})
    else:
        r = DenseRetriever.load(paths["index"], chunks, enc, cfg["retrieval"]["chunk_top_k"])
    index_seconds = time.perf_counter() - t0
    trunc_passages = enc.truncated
    enc.truncated = 0
    queries = read_queries(a.queries)
    k, tag = cfg["retrieval"]["top_k"], cfg["retrieval"]["run_tag"]
    a.output.mkdir(parents=True)
    timings = []
    with open(a.output / "run.trec", "w", encoding="utf-8", newline="\n") as f:
        for q in queries:
            s = time.perf_counter()
            res = r.search(q["query"], k)
            if device == "cuda":
                torch.cuda.synchronize()
            timings.append(time.perf_counter() - s)
            for i, (aid, score) in enumerate(res, 1):
                f.write(f"{q['query_id']} Q0 {aid} {i} {score:.9f} {tag}\n")
    summary = {"system": tag, "n_queries": len(queries), "n_chunks": len(r.chunks), "index_mode": "build" if a.build else "load",
               "index_seconds": index_seconds, "query_seconds": timings, "truncated_queries": enc.truncated,
               "truncated_passages_at_build": trunc_passages if a.build else None,
               "query_sha256": sha(a.queries), "config": cfg, "model_files": model_fingerprint(paths["model"]),
               "index_vectors_sha256": json.loads((paths["index"] / "manifest.json").read_text(encoding="utf-8"))["vectors_sha256"],
               "execution": {"device": device, "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
                             "torch": torch.__version__, "python": platform.python_version()}}
    (a.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done {len(queries)} queries -> {a.output}")


if __name__ == "__main__":
    main()
