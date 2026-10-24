"""Pool preparation and strict judgment integrity checks, independent of API calls."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
import tempfile
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr
from typing import Literal

from src.retrieval.common import file_hash, keyed, read_jsonl, valid_id, write_jsonl


class Judgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: StrictStr
    label: StrictInt | None
    status: Literal["labeled", "needs_review"]
    reason: StrictStr
    evidence: StrictStr
    context_incomplete: StrictBool
    query_issue: StrictBool


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    judgments: list[Judgment]


def fingerprint(value) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


@contextmanager
def new_directory(target: Path):
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        yield staging
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as f:
            f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_metadata(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keyed(rows, "query_id")
    if any(not isinstance(r.get("query"), str) or not r["query"].strip() for r in rows):
        raise ValueError("Missing query text")
    return rows


def select_queries(rows: list[dict], settings: dict) -> list[dict]:
    by_id = keyed(rows, "query_id")
    count = settings["query_count"]
    if type(count) is not int or not 0 < count <= len(rows):
        raise ValueError("Invalid query_count")
    if settings["query_ids"]:
        ids = settings["query_ids"]
        if len(ids) != count or len(set(ids)) != count or not set(ids) <= by_id.keys():
            raise ValueError("Invalid explicit query selection")
        return [by_id[q] for q in ids]
    ordered = sorted(rows, key=lambda r: r["query_id"])
    random.Random(settings["seed"]).shuffle(ordered)
    selected, types, fields, intents = [], set(), set(), set()
    for _ in range(count):
        choices = [
            r for r in ordered if r.get("intent_id", r["query_id"]) not in intents
        ]
        if not choices:
            raise ValueError(
                "Not enough distinct intent IDs; provide explicit query_ids"
            )
        row = max(
            choices,
            key=lambda r: (r.get("query_type") not in types)
            + (r.get("field") not in fields),
        )
        selected.append(row)
        types.add(row.get("query_type"))
        fields.add(row.get("field"))
        intents.add(row.get("intent_id", row["query_id"]))
        ordered.remove(row)
    return selected


def read_run(path: Path) -> dict:
    groups = {}
    seen = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            qid, _, aid, rank, score, _ = line.split()
            rank, score = int(rank), float(score)
            if (
                not valid_id(qid)
                or not valid_id(aid)
                or (qid, aid) in seen
                or rank <= 0
            ):
                raise ValueError("Invalid/duplicate TREC pair")
            if not math.isfinite(score):
                raise ValueError("Nonfinite TREC score")
            seen.add((qid, aid))
            groups.setdefault(qid, []).append((aid, rank, score))
    for rows in groups.values():
        if sorted(rank for _, rank, _ in rows) != list(range(1, len(rows) + 1)):
            raise ValueError("TREC ranks are not consecutive")
    return groups


def merge_candidates(first: dict, second: dict) -> dict:
    if first.keys() != second.keys():
        raise ValueError("Baseline query sets differ")
    pool = {}
    for system, runs in (("bm25", first), ("e5", second)):
        for qid, rows in runs.items():
            for aid, rank, score in rows:
                pool.setdefault(qid, {}).setdefault(aid, []).append(
                    {"system": system, "rank": rank, "score": score}
                )
    return pool


def blind_payload(row: dict) -> dict:
    allowed = ("candidate_id", "body", "document_title", "number", "title")
    return {
        "query": row["query"],
        "candidates": [{k: c[k] for k in allowed} for c in row["candidates"]],
    }


def prepare(cfg: dict, queries_override: Path | None = None) -> Path:
    paths = cfg["paths"]
    query_path = queries_override or Path(paths["queries"])
    queries = read_metadata(query_path)
    query_hash = file_hash(query_path)
    summaries, runs = [], []
    for name in ("bm25", "e5"):
        folder = Path(paths["baselines"][name])
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        if summary["query_sha256"] != query_hash:
            raise ValueError("Baseline query hash differs from CSV")
        for file, expected in summary["outputs"].items():
            if Path(file).name != file or file_hash(folder / file) != expected:
                raise ValueError(f"Baseline checksum mismatch: {name}/{file}")
        summaries.append(summary)
        runs.append(read_run(folder / "run.trec"))
        if any(len(items) != cfg["pool_depth"] for items in runs[-1].values()):
            raise ValueError("Baseline run depth differs from configured pool depth")
    if summaries[0]["provenance"]["sources"] != summaries[1]["provenance"]["sources"]:
        raise ValueError("Baseline corpus hashes differ")
    for name in ("articles", "docs"):
        if file_hash(Path(paths[name])) != summaries[0]["provenance"]["sources"][name]:
            raise ValueError(f"Corpus checksum mismatch: {name}")
    if set(runs[0]) != {r["query_id"] for r in queries}:
        raise ValueError("Run query IDs differ from CSV")
    merged = merge_candidates(*runs)
    chosen = select_queries(queries, {**cfg["selection"], "seed": cfg["seed"]})
    articles = keyed(read_jsonl(Path(paths["articles"])), "article_id")
    docs = keyed(read_jsonl(Path(paths["docs"])), "doc_id")
    rng = random.Random(cfg["seed"])
    pool = []
    for q in chosen:
        candidates = []
        for aid, origins in sorted(merged[q["query_id"]].items()):
            a = articles[aid]
            d = docs[a["doc_id"]]
            candidates.append(
                {
                    "candidate_id": fingerprint([q["query_id"], aid]),
                    "article_id": aid,
                    "doc_id": a["doc_id"],
                    "body": a["body"],
                    "document_title": d["title"],
                    "number": a["number"],
                    "title": a["title"],
                    "origins": origins,
                }
            )
        rng.shuffle(candidates)
        pool.append(
            {
                "query_id": q["query_id"],
                "query": q["query"],
                "metadata": q,
                "candidates": candidates,
            }
        )
    target = Path(paths["run"])
    with new_directory(target) as staging:
        write_jsonl(staging / "pool.jsonl", pool)
        write_jsonl(
            staging / "requests.jsonl",
            [{"query_id": r["query_id"], "payload": blind_payload(r)} for r in pool],
        )
        # Empty labels prevent unreviewed defaults from becoming examples.
        with (staging / "calibration.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "candidate_id",
                    "query",
                    "document_title",
                    "number",
                    "title",
                    "body",
                    "label",
                    "reason",
                    "evidence",
                    "review_status",
                ],
            )
            w.writeheader()
            for r in pool:
                for c in r["candidates"]:
                    w.writerow(
                        {
                            k: ({**c, "query": r["query"]}).get(k, "")
                            for k in w.fieldnames
                        }
                    )
        write_json(
            staging / "manifest.json",
            {
                "config": cfg,
                "config_hash": fingerprint(cfg),
                "query_sha256": query_hash,
                "source_hashes": summaries[0]["provenance"]["sources"],
                "files": {p.name: file_hash(p) for p in staging.iterdir()},
                "selection": {
                    "query_ids": [r["query_id"] for r in pool],
                    "intent_ids": [r.get("intent_id") for r in chosen],
                    "types": dict(Counter(r.get("query_type") for r in chosen)),
                    "fields": dict(Counter(r.get("field") for r in chosen)),
                },
            },
        )
    return target


def load_pool(cfg: dict) -> list[dict]:
    root = Path(cfg["paths"]["run"])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["config_hash"] != fingerprint(cfg):
        raise ValueError("Prepared run config changed; use a new run directory")
    for name in ("pool.jsonl", "requests.jsonl"):
        if file_hash(root / name) != manifest["files"][name]:
            raise ValueError(f"Prepared file checksum mismatch: {name}")
    return read_jsonl(root / "pool.jsonl")


def validate_response(row: dict, raw: dict, run_id: str) -> list[dict]:
    response = Response.model_validate(raw)
    candidates = keyed(row["candidates"], "candidate_id")
    ids = [r.candidate_id for r in response.judgments]
    if len(set(ids)) != len(ids) or set(ids) != candidates.keys():
        raise ValueError("Response missing/extra/duplicate candidates")
    result = []
    for item in response.judgments:
        c = candidates[item.candidate_id]
        if (
            not item.reason.strip()
            or (item.status == "labeled" and item.label not in (0, 1, 2))
            or (item.status != "labeled" and item.label is not None)
        ):
            raise ValueError("Invalid label/status/reason")
        data = item.model_dump()
        problem = None
        if item.evidence and item.evidence not in c["body"]:
            problem = "evidence_not_in_body"
        if item.label in (1, 2) and not item.evidence:
            problem = "positive_without_evidence"
        if item.context_incomplete or item.query_issue:
            problem = "context_or_query_issue"
        if problem:
            data.update(status="needs_review", label=None)
        result.append(
            {
                **data,
                "llm_label": item.label,
                "validation_issue": problem,
                "query_id": row["query_id"],
                "article_id": c["article_id"],
                "doc_id": c["doc_id"],
                "query_type": row["metadata"].get("query_type"),
                "field": row["metadata"].get("field"),
                "label_run_id": run_id,
            }
        )
    return result
