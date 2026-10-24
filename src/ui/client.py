"""Chỉ gọi HTTP ở chế độ thật; validate fixtures ở chế độ mẫu."""
import csv
import io
import os
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import ValidationError

from src.contracts import (
    ErrorResponse, FeedbackAck, FeedbackRequest, InfoResponse, SearchRequest, SearchResponse,
)
from src.ui.errors import ApiFailure

SCENARIOS = (
    "bình thường", "rỗng", "QUERY_TRUNCATED", "EMPTY_QUERY", "INVALID_FILTER",
    "MODEL_NOT_READY", "INDEX_MANIFEST_MISMATCH", "mất kết nối", "feedback lỗi",
    "search_id hết hạn",
)


class ApiClient:
    def __init__(self):
        self.base_url = os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/")
        self.timeout = float(os.environ.get("UI_TIMEOUT_S", "30"))

    def _request(self, method, path, req=None, schema=None):
        try:
            payload = None
            if req is not None:
                exclude = {"filters": {"year_min", "year_max"}} if isinstance(req, SearchRequest) else None
                payload = req.model_dump(mode="json", exclude_none=True, exclude=exclude)
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.request(method, path, json=payload)
            if not response.is_success:
                try:
                    error = ErrorResponse.model_validate(response.json())
                except (ValueError, ValidationError):
                    raise ApiFailure(status=response.status_code) from None
                raise ApiFailure(error.error.code, status=response.status_code)
            if schema is None:
                return response.content
            return schema.model_validate(response.json())
        except httpx.RequestError:
            raise ApiFailure(connection=True) from None
        except (ValueError, ValidationError):
            raise ApiFailure() from None

    def info(self):
        return self._request("GET", "/v1/info", schema=InfoResponse)

    def search(self, req: SearchRequest):
        return self._request("POST", "/v1/search", req, SearchResponse)

    def feedback(self, req: FeedbackRequest):
        return self._request("POST", "/v1/feedback", req, FeedbackAck)

    def export_csv(self):
        return self._request("GET", "/v1/feedback/export")


class SampleClient:
    def __init__(self):
        self.scenario = SCENARIOS[0]
        self.fixtures = {}
        self.searches = {}
        self.votes = {}
        for path in sorted(Path(__file__).with_name("sample_data").glob("*.json")):
            schema = InfoResponse if path.stem == "info" else (
                ErrorResponse if path.stem.startswith("error_") else SearchResponse
            )
            self.fixtures[path.stem] = schema.model_validate_json(path.read_text(encoding="utf-8"))

    def _error(self, name, status):
        raise ApiFailure(self.fixtures[f"error_{name}"].error.code, status=status)

    def _availability(self):
        if self.scenario == "mất kết nối":
            raise ApiFailure(connection=True)
        if self.scenario in ("MODEL_NOT_READY", "INDEX_MANIFEST_MISMATCH"):
            self._error(self.scenario.lower(), 503)

    def info(self):
        self._availability()
        return self.fixtures["info"].model_copy(deep=True)

    def search(self, req: SearchRequest):
        self._availability()
        if self.scenario in ("EMPTY_QUERY", "INVALID_FILTER"):
            self._error(self.scenario.lower(), 422)
        name = {"rỗng": "empty", "QUERY_TRUNCATED": "truncated"}.get(self.scenario, req.mode)
        response = self.fixtures[f"search_{name}"].model_copy(deep=True)
        # Fixtures chỉ mô phỏng trình bày, không có logic truy hồi hay lọc corpus.
        if name in ("empty", "truncated") and req.mode != "semantic":
            response.lists = self.fixtures[f"search_{req.mode}"].model_copy(deep=True).lists
        for result_list in response.lists:
            result_list.items = [] if name == "empty" else result_list.items[:req.top_k]
        if req.mode == "compare":
            shared = set.intersection(*(set(i.article_id for i in r.items) for r in response.lists))
            for result_list in response.lists:
                for item in result_list.items:
                    item.in_both = item.article_id in shared
        response.search_id = uuid4()
        self.searches[response.search_id] = response
        return response

    def feedback(self, req: FeedbackRequest):
        self._availability()
        if self.scenario == "feedback lỗi":
            self._error("feedback", 503)
        if self.scenario == "search_id hết hạn" or req.search_id not in self.searches:
            self._error("search_expired", 422)
        self.votes[(req.search_id, req.system, req.article_id)] = req
        return FeedbackAck.model_validate(req.model_dump())

    def export_csv(self):
        self._availability()
        if self.scenario == "feedback lỗi":
            self._error("feedback", 503)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["search_id", "system", "article_id", "label"])
        for req in self.votes.values():
            writer.writerow([str(req.search_id), req.system, req.article_id, req.label])
        return output.getvalue().encode("utf-8-sig")
