"""Ánh xạ lỗi sang dạng `{"error": {"code", "message"}}` (SPEC 14.5)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.contracts import ErrorBody, ErrorCode, ErrorResponse

HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.EMPTY_QUERY: 422,
    ErrorCode.INVALID_FILTER: 422,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.MODEL_NOT_READY: 503,
    ErrorCode.INDEX_MANIFEST_MISMATCH: 503,
}


class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def error_json(code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=HTTP_STATUS[code], content=body.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_json(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ()))
        return error_json(ErrorCode.INVALID_REQUEST, f"Request sai schema: {loc} {first.get('msg', '')}".strip())
