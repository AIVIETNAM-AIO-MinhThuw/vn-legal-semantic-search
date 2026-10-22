"""Ứng dụng FastAPI — bản khung của hợp đồng v1 (SPEC 14.5).

Chưa có SearchService: mọi endpoint cần model trả 503 MODEL_NOT_READY. Logic thật được
gắn vào sau (gói app), không được đổi chữ ký endpoint mà không qua quy trình SPEC mục 0.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response

from src.api.errors import ApiError, install_error_handlers
from src.contracts import (
    CONTRACT_VERSION,
    ErrorCode,
    ErrorResponse,
    FeedbackAck,
    FeedbackRequest,
    HealthResponse,
    InfoResponse,
    SearchRequest,
    SearchResponse,
)

ERR_422 = {422: {"model": ErrorResponse, "description": "EMPTY_QUERY, INVALID_FILTER hoặc INVALID_REQUEST"}}
ERR_422_FEEDBACK = {422: {"model": ErrorResponse, "description":
                          "INVALID_REQUEST: sai schema, search_id không tồn tại, "
                          "hoặc (system, article_id) không thuộc lượt tìm đó"}}
ERR_503 = {503: {"model": ErrorResponse, "description": "MODEL_NOT_READY hoặc INDEX_MANIFEST_MISMATCH"}}
# SPEC 14.5: /health chưa sẵn sàng thì luôn trả MODEL_NOT_READY.
ERR_503_HEALTH = {503: {"model": ErrorResponse, "description": "MODEL_NOT_READY"}}


def _not_ready() -> ApiError:
    return ApiError(ErrorCode.MODEL_NOT_READY, "Model hoặc index chưa được nạp.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="VN Legal Semantic Search API",
        version=CONTRACT_VERSION,
        description="Hợp đồng API v1 — SPEC mục 14.5.",
    )
    install_error_handlers(app)

    @app.get("/health", response_model=HealthResponse, responses=ERR_503_HEALTH, tags=["system"])
    def health() -> HealthResponse:
        raise _not_ready()

    @app.get("/v1/info", response_model=InfoResponse, responses=ERR_503, tags=["system"])
    def info() -> InfoResponse:
        raise _not_ready()

    @app.post("/v1/search", response_model=SearchResponse, responses={**ERR_422, **ERR_503}, tags=["search"])
    def search(req: SearchRequest) -> SearchResponse:
        raise _not_ready()

    @app.post("/v1/feedback", response_model=FeedbackAck, responses={**ERR_422_FEEDBACK, **ERR_503}, tags=["feedback"])
    def feedback(req: FeedbackRequest) -> FeedbackAck:
        raise _not_ready()

    @app.get(
        "/v1/feedback/export",
        response_class=Response,
        responses={200: {"content": {"text/csv": {}}, "description": "CSV UTF-8 có BOM"}, **ERR_503},
        tags=["feedback"],
    )
    def feedback_export() -> Response:
        raise _not_ready()

    return app
