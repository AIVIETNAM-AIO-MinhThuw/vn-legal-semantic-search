"""Offline fixtures only; none of these labels are pilot evidence."""

import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.annotation.pipeline import merge_candidates, select_queries, validate_response
from src.annotation.review import agreement, sample_review
from src.annotation.api import load_examples
from src.retrieval.common import file_hash, write_jsonl


def candidate(cid, aid):
    return {
        "candidate_id": cid,
        "article_id": aid,
        "doc_id": "d",
        "body": "Không phải nộp thuế.",
        "document_title": "Luật",
        "number": "1",
        "title": "Thuế",
        "origins": [],
    }


def pool():
    return {
        "query_id": "q",
        "query": "Có phải nộp thuế?",
        "metadata": {"query_type": "natural", "field": "thuế"},
        "candidates": [candidate("c1", "a1"), candidate("c2", "a2")],
    }


def response():
    return {
        "judgments": [
            {
                "candidate_id": c,
                "label": 2,
                "status": "labeled",
                "reason": "Có căn cứ",
                "evidence": "Không phải nộp thuế.",
                "context_incomplete": False,
                "query_issue": False,
            }
            for c in ["c1", "c2"]
        ]
    }


def test_union_is_per_query_and_keeps_origins():
    merged = merge_candidates(
        {"q": [("a", 1, 3.0), ("b", 2, 2.0)]}, {"q": [("b", 1, 0.9), ("c", 2, 0.8)]}
    )
    assert set(merged["q"]) == {"a", "b", "c"}
    assert len(merged["q"]["b"]) == 2
    with pytest.raises(ValueError):
        merge_candidates({"q": []}, {"other": []})


def test_selection_deterministic_and_distinct_intent():
    rows = [
        {
            "query_id": str(i),
            "query_type": str(i % 3),
            "field": str(i % 2),
            "intent_id": str(i // 2),
        }
        for i in range(12)
    ]
    settings = {"query_count": 4, "query_ids": [], "seed": 42}
    chosen = select_queries(rows, settings)
    assert chosen == select_queries(list(reversed(rows)), settings)
    assert len({r["intent_id"] for r in chosen}) == 4


def test_validate_ids_schema_and_evidence():
    valid = validate_response(pool(), response(), "run")
    assert len(valid) == 2 and all(r["status"] == "labeled" for r in valid)
    for bad in [
        [],
        response()["judgments"] + [response()["judgments"][0]],
        response()["judgments"][:1],
    ]:
        with pytest.raises(ValueError):
            validate_response(pool(), {"judgments": bad}, "run")
    bad = response()
    bad["judgments"][0]["evidence"] = "bịa"
    rows = validate_response(pool(), bad, "run")
    assert rows[0]["status"] == "needs_review" and rows[0]["label"] is None
    bad = response()
    bad["judgments"][0]["label"] = True
    with pytest.raises(ValueError):
        validate_response(pool(), bad, "run")
    bad = response()
    bad["judgments"][0]["context_incomplete"] = True
    assert validate_response(pool(), bad, "run")[0]["status"] == "needs_review"


def test_balanced_sample_does_not_fill_missing_label():
    rows = [
        dict(
            query_id=str(i),
            article_id=str(i),
            candidate_id=str(i),
            label=i % 2,
            status="labeled",
            query_type="natural",
            field="x",
        )
        for i in range(40)
    ]
    chosen, missing = sample_review(rows, per_label=10, seed=42)
    assert len(chosen) == 20 and missing == {"0": 0, "1": 0, "2": 10}
    assert chosen == sample_review(list(reversed(rows)), per_label=10, seed=42)[0]


def test_agreement_independent_expected_and_degenerate():
    result = agreement([(0, 0), (1, 1), (2, 2), (0, 2)])
    assert result["raw_agreement"] == 0.75
    # Linear observed disagreement .25; chance .5 -> weighted kappa .5.
    assert result["linear_weighted_kappa"] == pytest.approx(0.5)
    assert agreement([(0, 0)])["linear_weighted_kappa"] is None


def test_examples_without_author_preserve_review_status_and_source(tmp_path):
    source = tmp_path / "pilot"
    source.mkdir()
    row = pool()
    row["candidates"] = [candidate(f"c{i}", f"a{i}") for i in range(6)]
    write_jsonl(source / "pool.jsonl", [row])
    (source / "manifest.json").write_text(
        json.dumps({"files": {"pool.jsonl": file_hash(source / "pool.jsonl")}}),
        encoding="utf-8",
    )
    examples = [
        dict(
            candidate_id=f"c{i}",
            label=i // 2,
            reason="Căn cứ",
            evidence="Không phải nộp thuế.",
            source_run=str(source),
            review_status="unverified",
        )
        for i in range(6)
    ]
    path = tmp_path / "examples.jsonl"
    write_jsonl(path, examples)
    cfg = {"paths": {"examples": str(path)}, "review": {"examples_per_label": 2}}
    public, excluded = load_examples(cfg)
    assert len(public) == len(excluded) == 6
    assert all("author" not in r for r in public)
    examples[0].pop("review_status")
    write_jsonl(path, examples)
    with pytest.raises(ValueError, match="review_status"):
        load_examples(cfg)
