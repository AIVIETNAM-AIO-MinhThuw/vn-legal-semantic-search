"""Blind human review, sample-scoped metrics, and guarded dataset export."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

from src.annotation.api import load_examples, protocol, validated_rows
from src.annotation.pipeline import fingerprint, load_pool, new_directory, write_json
from src.retrieval.common import keyed, read_jsonl, write_jsonl


def sample_review(
    rows: list[dict], per_label: int, seed: int
) -> tuple[list[dict], dict]:
    if type(per_label) is not int or per_label <= 0:
        raise ValueError("per_label must be positive")
    ordered = sorted(rows, key=lambda r: (r["query_id"], r["article_id"]))
    rng = random.Random(seed)
    rng.shuffle(ordered)
    selected, seen_q, seen_type, seen_field, missing = [], set(), set(), set(), {}
    for label in (0, 1, 2):
        candidates = [
            r for r in ordered if r["label"] == label and r["status"] == "labeled"
        ]
        for _ in range(min(per_label, len(candidates))):
            row = max(
                candidates,
                key=lambda r: (r["query_id"] not in seen_q)
                + (r.get("query_type") not in seen_type)
                + (r.get("field") not in seen_field),
            )
            selected.append(row)
            candidates.remove(row)
            seen_q.add(row["query_id"])
            seen_type.add(row.get("query_type"))
            seen_field.add(row.get("field"))
        missing[str(label)] = max(
            0, per_label - sum(r["label"] == label for r in selected)
        )
    rng.shuffle(selected)
    return selected, missing


def agreement(pairs: list[tuple[int, int]]) -> dict:
    matrix = [[0] * 3 for _ in range(3)]
    for llm, human in pairs:
        if (
            type(llm) is not int
            or type(human) is not int
            or llm not in (0, 1, 2)
            or human not in (0, 1, 2)
        ):
            raise ValueError("Invalid metric label")
        matrix[llm][human] += 1
    n = len(pairs)
    if not n:
        return {
            "n": 0,
            "raw_agreement": None,
            "linear_weighted_kappa": None,
            "confusion_matrix": matrix,
            "undefined_reason": "No paired judgments",
        }
    observed = sum(abs(a - b) / 2 for a, b in pairs) / n
    rows = [sum(row) for row in matrix]
    cols = [sum(matrix[i][j] for i in range(3)) for j in range(3)]
    expected = sum(
        abs(a - b) / 2 * rows[a] * cols[b] for a in range(3) for b in range(3)
    ) / (n * n)
    return {
        "n": n,
        "raw_agreement": sum(a == b for a, b in pairs) / n,
        "linear_weighted_kappa": 1 - observed / expected if expected else None,
        "confusion_matrix": matrix,
        "matrix_axes": "rows=LLM, columns=independent human",
        "undefined_reason": None if expected else "Zero expected disagreement",
        "scope": "Label-balanced diagnostic sample only; not whole-pool accuracy",
    }


def index_pool(cfg: dict) -> dict:
    return {c["candidate_id"]: (q, c) for q in load_pool(cfg) for c in q["candidates"]}


def export_review(cfg: dict, target: Path) -> dict:
    rows, info = validated_rows(cfg)
    _, example_ids = load_examples(cfg)
    eligible = [r for r in rows if r["candidate_id"] not in example_ids]
    selected, missing = sample_review(eligible, cfg["review"]["per_label"], cfg["seed"])
    source = index_pool(cfg)
    fields = [
        "candidate_id",
        "query",
        "document_title",
        "number",
        "title",
        "body",
        "human_label",
        "reviewer",
        "note",
        "adjudicated_label",
        "adjudicator",
    ]
    with new_directory(target) as folder:
        for filename, candidates in (
            ("sample.csv", selected),
            ("pending.csv", info["pending"]),
        ):
            with (folder / filename).open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for row in candidates:
                    q, c = source[row["candidate_id"]]
                    writer.writerow(
                        {
                            **{
                                k: c[k]
                                for k in (
                                    "candidate_id",
                                    "document_title",
                                    "number",
                                    "title",
                                    "body",
                                )
                            },
                            "query": q["query"],
                        }
                    )
        write_jsonl(folder / "private_sample.jsonl", selected)
        report = {
            "protocol_hash": info["protocol_hash"],
            "sample_size": len(selected),
            "missing_per_label": missing,
            "pending_count": len(info["pending"]),
            "excluded_example_pairs": len(example_ids),
            "sample_ids": [r["candidate_id"] for r in selected],
            "pending_ids": [r["candidate_id"] for r in info["pending"]],
            "sample_label_counts": dict(Counter(r["label"] for r in selected)),
            "pool_label_counts": dict(Counter(r["label"] for r in rows)),
            "metrics": "NOT RUN: independent human labels missing",
        }
        write_json(folder / "selection.json", report)
    return report


def import_review(cfg: dict, source: Path, review_dir: Path, target: Path) -> dict:
    pool = index_pool(cfg)
    manifest = json.loads((review_dir / "selection.json").read_text(encoding="utf-8"))
    if manifest["protocol_hash"] != protocol(cfg)[1]:
        raise ValueError("Review protocol changed")
    allowed = set(manifest["sample_ids"] + manifest["pending_ids"])
    llm = {r["candidate_id"]: r for r in validated_rows(cfg)[0]}
    with source.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keyed(rows, "candidate_id")
    accepted, pairs = [], []
    for row in rows:
        cid = row["candidate_id"]
        if cid not in allowed or cid not in pool:
            raise ValueError("Human response outside requested sample/pending set")
        if not row.get("human_label", "").strip():
            continue
        if (
            row["human_label"] not in {"0", "1", "2"}
            or not row.get("reviewer", "").strip()
        ):
            raise ValueError("Human label/reviewer required")
        human = int(row["human_label"])
        original = llm.get(cid, {}).get("label")
        disagreement = original is not None and human != original
        final = None if disagreement else human
        adjudicated = row.get("adjudicated_label", "").strip()
        if adjudicated:
            if (
                adjudicated not in {"0", "1", "2"}
                or not row.get("adjudicator", "").strip()
                or row["adjudicator"].strip().casefold()
                == row["reviewer"].strip().casefold()
                or not row.get("note", "").strip()
            ):
                raise ValueError("Adjudication needs another person and reason")
            final = int(adjudicated)
        if original is None and not row.get("note", "").strip():
            raise ValueError("Manual resolution requires a reason")
        accepted.append(
            {
                "candidate_id": cid,
                "llm_label": original,
                "human_label": human,
                "final_label": final,
                "reviewer": row["reviewer"],
                "adjudicator": row.get("adjudicator"),
                "reason": row.get("note", ""),
                "label_source": "human_manual"
                if original is None
                else ("human_verified" if final == original else "human_corrected"),
                "status": "needs_adjudication" if final is None else "resolved",
            }
        )
        if cid in manifest["sample_ids"] and original is not None:
            pairs.append((original, human))
    report = {
        **agreement(pairs),
        "pending_adjudication": sum(r["final_label"] is None for r in accepted),
        "sample_requested": len(manifest["sample_ids"]),
        "reviewed": len(pairs),
        "protocol_hash": manifest["protocol_hash"],
    }
    with new_directory(target) as folder:
        write_jsonl(folder / "human.jsonl", accepted)
        write_json(folder / "report.json", report)
    return report


def import_examples(cfg: dict, source: Path, target: Path) -> int:
    pool = index_pool(cfg)
    with source.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keyed(rows, "candidate_id")
    examples = []
    for row in rows:
        if not row.get("label", "").strip():
            continue
        if row["candidate_id"] not in pool or row["label"] not in {"0", "1", "2"}:
            raise ValueError("Invalid calibration row")
        examples.append(
            {
                **{k: row[k] for k in ("candidate_id", "reason", "evidence")},
                "review_status": "unverified",
                "label": int(row["label"]),
                "source_run": str(Path(cfg["paths"]["run"]).resolve()),
            }
        )
    if target.exists() and target.stat().st_size:
        raise FileExistsError(target)
    # Validate all examples in a temporary config before publishing.
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as f:
            for row in examples:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        test_cfg = {**cfg, "paths": {**cfg["paths"], "examples": str(temporary)}}
        load_examples(test_cfg)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return len(examples)


def finalize(cfg: dict, target: Path, human_dir: Path | None, draft: bool) -> dict:
    rows, info = validated_rows(cfg)
    pool = index_pool(cfg)
    humans = (
        keyed(read_jsonl(human_dir / "human.jsonl"), "candidate_id")
        if human_dir
        else {}
    )
    if human_dir:
        report = json.loads((human_dir / "report.json").read_text(encoding="utf-8"))
        if report["protocol_hash"] != info["protocol_hash"]:
            raise ValueError("Human labels belong to another protocol")
    if not set(humans) <= pool.keys():
        raise ValueError("Human labels outside pool")
    accepted = {r["candidate_id"]: r for r in rows}
    for cid, human in humans.items():
        if human["final_label"] is None:
            accepted.pop(cid, None)
        else:
            q, c = pool[cid]
            accepted[cid] = {
                **accepted.get(cid, {}),
                **human,
                "query_id": q["query_id"],
                "article_id": c["article_id"],
            }
    metadata_path = cfg["paths"]["metadata"]
    metadata = (
        keyed(read_jsonl(Path(metadata_path)), "query_id") if metadata_path else {}
    )
    positives = {
        r["query_id"]
        for r in accepted.values()
        if r.get("final_label", r.get("label")) in (1, 2)
    }
    output, missing = [], []
    for cid, row in accepted.items():
        q, c = pool[cid]
        meta = {**q["metadata"], **metadata.get(q["query_id"], {})}
        absent = [
            name
            for name in (
                "dup_group_id",
                "source_article_id",
                "source_doc_id",
                "source_group_id",
            )
            if not meta.get(name)
        ]
        if absent:
            missing.append({"query_id": q["query_id"], "fields": absent})
        output.append(
            {
                "query_id": q["query_id"],
                "article_id": c["article_id"],
                "final_label": row.get("final_label", row.get("label")),
                "llm_label": row.get("llm_label"),
                "human_label": row.get("human_label"),
                "label_source": row.get("label_source", "llm"),
                "query_type": meta.get("query_type"),
                **{
                    name: meta.get(name)
                    for name in (
                        "dup_group_id",
                        "source_article_id",
                        "source_doc_id",
                        "source_group_id",
                    )
                },
                "no_positive_in_pool": q["query_id"] not in positives,
                "label_run_id": row.get("label_run_id"),
                "pilot": cfg["selection"]["mode"] == "pilot",
                "intent_id": meta.get("intent_id"),
            }
        )
    pending_ids = set(pool) - accepted.keys()
    if not draft and (missing or pending_ids):
        raise ValueError(
            "Formal export blocked: required grouping metadata or judgments unresolved; --draft only"
        )
    with new_directory(target) as folder:
        write_jsonl(
            folder / ("dataset_draft.jsonl" if draft else "dataset.jsonl"), output
        )
        report = {
            "draft": draft,
            "accepted": len(output),
            "unresolved": len(pending_ids),
            "missing_metadata": missing,
            "protocol_hash": info["protocol_hash"],
            "automatic_quality_pass": False,
            "split": "NOT RUN",
            "frozen": False,
            "dataset_hash": fingerprint(output),
        }
        write_json(folder / "report.json", report)
    return report
