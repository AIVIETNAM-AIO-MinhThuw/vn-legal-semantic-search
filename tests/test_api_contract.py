"""Test hợp đồng API v1 (SPEC 14.5; 14.7 mục 1)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from scripts.export_openapi import render
from src.api.app import create_app
from src.contracts import ErrorCode, Highlight, ResultItem, ResultList, SearchRequest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))


def _assert_error(resp, status: int, code: str) -> None:
    assert resp.status_code == status
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code


# --- 14.7 mục 1: snapshot ---

def test_openapi_snapshot_matches_code(spec):
    assert spec == json.loads(render()), "openapi.json lệch code: chạy scripts/export_openapi.py và ghi Changelog"


# --- nội dung hợp đồng ---

def test_endpoints(spec):
    assert set(spec["paths"]) == {"/health", "/v1/info", "/v1/search", "/v1/feedback", "/v1/feedback/export"}
    assert set(spec["paths"]["/v1/search"]) == {"post"}
    assert set(spec["paths"]["/v1/feedback"]) == {"post"}


def test_article_id_is_string(spec):
    s = spec["components"]["schemas"]
    for name in ("ResultItem", "FeedbackRequest", "FeedbackAck"):
        assert s[name]["properties"]["article_id"]["type"] == "string"


def test_enums(spec):
    s = spec["components"]["schemas"]
    assert set(s["ErrorCode"]["enum"]) == {
        "EMPTY_QUERY", "INVALID_FILTER", "INVALID_REQUEST", "MODEL_NOT_READY", "INDEX_MANIFEST_MISMATCH"}
    assert s["SearchRequest"]["properties"]["mode"]["enum"] == ["bm25", "semantic", "hybrid", "compare"]
    assert s["ResultList"]["properties"]["score_type"]["enum"] == ["bm25", "cosine", "rrf"]
    assert s["ResultList"]["properties"]["system"]["enum"] == ["bm25", "semantic", "hybrid"]
    assert s["WarningCode"]["enum"] == ["QUERY_TRUNCATED"]


def test_timing_ms_is_number(spec):
    assert spec["components"]["schemas"]["SearchResponse"]["properties"]["timing_ms"]["type"] == "number"


def test_no_default_fastapi_422_schema(spec):
    assert "HTTPValidationError" not in spec["components"]["schemas"]


# --- schema ---

@pytest.mark.parametrize("top_k", [0, 21])
def test_top_k_out_of_range_rejected(top_k):
    with pytest.raises(ValidationError):
        SearchRequest(query="thuế", mode="bm25", top_k=top_k)


def test_search_defaults():
    r = SearchRequest(query="thuế", mode="semantic")
    assert r.top_k == 10 and r.highlight is True and r.filters.doc_types == []


def test_empty_query_not_blocked_by_schema():
    # EMPTY_QUERY do service trả, không phải INVALID_REQUEST (SPEC 14.3).
    SearchRequest(query="   ", mode="bm25")


@pytest.mark.parametrize("start,end", [(5, 5), (6, 5), (-1, 3)])
def test_highlight_invalid(start, end):
    with pytest.raises(ValidationError):
        Highlight(start=start, end=end)


def test_highlight_slice_on_vietnamese():
    content = "Điều 5. Thuế thu nhập cá nhân"
    h = Highlight(start=8, end=12)
    assert content[h.start:h.end] == "Thuế"


def test_article_id_not_coerced_from_int():
    with pytest.raises(ValidationError):
        ResultItem(rank=1, article_id=123, doc_title="", article_number="1", article_title="",
                   effect_status="", content="", score=0.0, in_both=False)


# --- ánh xạ lỗi qua HTTP ---

def test_health_not_ready(client):
    _assert_error(client.get("/health"), 503, ErrorCode.MODEL_NOT_READY.value)


@pytest.mark.parametrize("body", [
    {"query": "thuế", "mode": "bm25", "top_k": 21},
    {"query": "thuế", "mode": "dense"},
    {"query": "thuế", "mode": "bm25", "extra": 1},
    {"mode": "bm25"},
])
def test_search_invalid_request(client, body):
    _assert_error(client.post("/v1/search", json=body), 422, "INVALID_REQUEST")


def test_search_valid_request_reaches_stub(client):
    _assert_error(client.post("/v1/search", json={"query": "thuế", "mode": "compare"}), 503, "MODEL_NOT_READY")


def test_feedback_invalid_label(client):
    body = {"search_id": str(uuid.uuid4()), "system": "bm25", "article_id": "x_001", "label": "maybe"}
    _assert_error(client.post("/v1/feedback", json=body), 422, "INVALID_REQUEST")


# --- B: system <-> score_type ---

def _item(**kw):
    base = dict(rank=1, article_id="d_001", doc_title="", article_number="5", article_title="",
                effect_status="", content="Điều 5. Thuế thu nhập cá nhân", score=1.0, in_both=False)
    base.update(kw)
    return ResultItem(**base)


@pytest.mark.parametrize("system,score_type", [("bm25", "bm25"), ("semantic", "cosine"), ("hybrid", "rrf")])
def test_score_type_pairs_ok(system, score_type):
    ResultList(system=system, score_type=score_type, items=[_item()])


@pytest.mark.parametrize("system,score_type", [("bm25", "cosine"), ("semantic", "bm25"), ("hybrid", "cosine")])
def test_score_type_pairs_rejected(system, score_type):
    with pytest.raises(ValidationError):
        ResultList(system=system, score_type=score_type, items=[])


# --- C: highlights tăng dần, không chồng, đã gộp, trong content ---

def test_highlights_ok():
    it = _item(highlights=[Highlight(start=8, end=12), Highlight(start=13, end=16)])
    assert [it.content[h.start:h.end] for h in it.highlights] == ["Thuế", "thu"]


@pytest.mark.parametrize("spans", [
    [(13, 17), (8, 12)],   # không tăng dần
    [(8, 14), (12, 17)],   # chồng nhau
    [(8, 12), (12, 16)],   # liền kề chưa gộp
    [(8, 999)],            # vượt content
])
def test_highlights_rejected(spans):
    with pytest.raises(ValidationError):
        _item(highlights=[Highlight(start=a, end=b) for a, b in spans])


# --- D, A1: mô tả lỗi trong openapi ---

def test_health_503_only_model_not_ready(spec):
    assert spec["paths"]["/health"]["get"]["responses"]["503"]["description"] == "MODEL_NOT_READY"


def test_feedback_422_describes_unknown_search(spec):
    assert "search_id không tồn tại" in spec["paths"]["/v1/feedback"]["post"]["responses"]["422"]["description"]
