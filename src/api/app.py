"""Ứng dụng FastAPI (SPEC 14.5). Chữ ký endpoint giữ nguyên hợp đồng `openapi.json`.

`create_app(service)`: service=None → mọi endpoint cần model trả 503 MODEL_NOT_READY (dùng cho test hợp đồng).
Chạy thật: `APP_CONFIG=configs/app.yaml uvicorn src.api.app:app` — nạp SearchService (src/app/service.py).
"""
from __future__ import annotations

import logging
import os

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
ERR_422_REQ = {422: {"model": ErrorResponse, "description": "INVALID_REQUEST: sai schema, search_id không tồn tại, hoặc (system, article_id) không thuộc lượt tìm đó"}}
ERR_503 = {503: {"model": ErrorResponse, "description": "MODEL_NOT_READY hoặc INDEX_MANIFEST_MISMATCH"}}


def _not_ready() -> ApiError:
    return ApiError(ErrorCode.MODEL_NOT_READY, "Model hoặc index chưa được nạp.")


def create_app(service=None) -> FastAPI:
    app = FastAPI(
        title="VN Legal Semantic Search API",
        version=CONTRACT_VERSION,
        description="Hợp đồng API v1 — SPEC mục 14.5.",
    )
    install_error_handlers(app)

    @app.get("/health", response_model=HealthResponse,
             responses={503: {"model": ErrorResponse, "description": "MODEL_NOT_READY"}}, tags=["system"])
    async def health() -> HealthResponse:
        if service is None:
            raise _not_ready()
        return HealthResponse()

    @app.get("/v1/info", response_model=InfoResponse, responses=ERR_503, tags=["system"])
    async def info() -> InfoResponse:
        if service is None:
            raise _not_ready()
        return service.info()

    @app.post("/v1/search", response_model=SearchResponse, responses={**ERR_422, **ERR_503}, tags=["search"])
    async def search(req: SearchRequest) -> SearchResponse:
        if service is None:
            raise _not_ready()
        return service.search(req)

    @app.post("/v1/feedback", response_model=FeedbackAck, responses={**ERR_422_REQ, **ERR_503}, tags=["feedback"])
    async def feedback(req: FeedbackRequest) -> FeedbackAck:
        if service is None:
            raise _not_ready()
        return service.feedback(req)

    @app.get(
        "/v1/feedback/export",
        response_class=Response,
        responses={200: {"content": {"text/csv": {}}, "description": "CSV UTF-8 có BOM"}, **ERR_503},
        tags=["feedback"],
    )
    async def feedback_export() -> Response:
        if service is None:
            raise _not_ready()
        return Response(service.export_csv(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=feedback.csv"})

    return app


def _app_from_env() -> FastAPI:
    cfg = os.environ.get("APP_CONFIG")
    if not cfg:
        return create_app()
    from src.app.service import SearchService
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Let startup errors reach Uvicorn so an invalid index cannot stay serving.
    return create_app(SearchService(cfg))


app = _app_from_env()
