"""Schema Pydantic của API v1 (SPEC 14.5).

Quyết định của nhóm khi lập hợp đồng (2026-10-22):
- `timing_ms` là một số (tổng thời gian xử lý request, mili giây).
- `system` là tên chế độ cố định: `bm25`, `semantic`, `hybrid`. Model thật nằm ở `/v1/info`
  và bảng `searches` phía server (SPEC 14.4).
- Cảnh báo có dạng `{code, message}`, giống định dạng lỗi; UI hiển thị theo `code` (SPEC 14.3).

Đổi bất kỳ schema nào ở đây là đổi hợp đồng: phải qua quy trình SPEC mục 0, sinh lại
`openapi.json` và ghi Changelog.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.0.0"

# Giới hạn top-k là một phần của hợp đồng (SPEC 14.2, 14.5), không phải tham số tune.
TOP_K_MIN = 1
TOP_K_MAX = 20
TOP_K_DEFAULT = 10

Mode = Literal["bm25", "semantic", "hybrid", "compare"]
SystemName = Literal["bm25", "semantic", "hybrid"]
ScoreType = Literal["bm25", "cosine", "rrf"]
FeedbackLabel = Literal["useful", "not_useful"]

# Mỗi system chỉ đi với đúng một thang điểm; không trộn thang (SPEC 14.5 "Quy ước chung").
SCORE_TYPE_OF_SYSTEM: dict[str, str] = {"bm25": "bm25", "semantic": "cosine", "hybrid": "rrf"}


class ErrorCode(str, Enum):
    EMPTY_QUERY = "EMPTY_QUERY"                          # 422
    INVALID_FILTER = "INVALID_FILTER"                    # 422
    INVALID_REQUEST = "INVALID_REQUEST"                  # 422
    MODEL_NOT_READY = "MODEL_NOT_READY"                  # 503
    INDEX_MANIFEST_MISMATCH = "INDEX_MANIFEST_MISMATCH"  # 503


class WarningCode(str, Enum):
    QUERY_TRUNCATED = "QUERY_TRUNCATED"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Lỗi ----------

class ErrorBody(_Strict):
    code: ErrorCode
    message: str


class ErrorResponse(_Strict):
    error: ErrorBody


# ---------- /health ----------

class HealthResponse(_Strict):
    status: Literal["ok"] = "ok"


# ---------- /v1/search ----------

class SearchFilters(_Strict):
    """Giá trị hợp lệ lấy từ `GET /v1/info`; danh sách rỗng = không lọc theo trường đó."""
    doc_types: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    issuers: list[str] = Field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None


class SearchRequest(_Strict):
    # Query rỗng/chỉ khoảng trắng/ký tự đặc biệt KHÔNG bị chặn ở schema: service trả
    # EMPTY_QUERY (SPEC 14.3, 14.5), để UI phân biệt với INVALID_REQUEST.
    query: str
    mode: Mode
    top_k: int = Field(default=TOP_K_DEFAULT, ge=TOP_K_MIN, le=TOP_K_MAX)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    highlight: bool = True


class Highlight(_Strict):
    """Khoảng nửa mở `content[start:end]`, chỉ số code point Unicode trên `content` dạng NFC."""
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _end_after_start(self) -> "Highlight":
        if self.end <= self.start:
            raise ValueError("end phải lớn hơn start")
        return self


class ResultItem(_Strict):
    # Nguồn dữ liệu (data/processed/*.jsonl do scripts/prepare_data.py sinh):
    #   doc_title      <- docs.title
    #   article_number <- articles.number
    #   article_title  <- articles.title
    #   effect_status  <- docs.tinh_trang_hieu_luc
    #   content        <- nội dung Điều, dạng NFC (highlights tính trên chuỗi này)
    rank: int = Field(ge=1)
    article_id: str
    doc_title: str
    article_number: str
    article_title: str
    effect_status: str
    content: str
    score: float
    in_both: bool  # chỉ có ý nghĩa ở chế độ compare; server tính
    highlights: list[Highlight] = Field(default_factory=list)

    @model_validator(mode="after")
    def _highlights_valid(self) -> "ResultItem":
        # Tăng dần, không chồng nhau, không liền kề (đã gộp), nằm trong content (SPEC 14.5 "Highlight").
        prev_end = -1
        for h in self.highlights:
            if h.start <= prev_end:
                raise ValueError("highlights phải tăng dần, không chồng nhau và đã gộp đoạn liền kề")
            if h.end > len(self.content):
                raise ValueError("highlight vượt quá độ dài content")
            prev_end = h.end
        return self


class ResultList(_Strict):
    system: SystemName
    score_type: ScoreType
    items: list[ResultItem]

    @model_validator(mode="after")
    def _score_type_matches_system(self) -> "ResultList":
        expected = SCORE_TYPE_OF_SYSTEM[self.system]
        if self.score_type != expected:
            raise ValueError(f"system '{self.system}' phải đi với score_type '{expected}'")
        return self


class SearchWarning(_Strict):
    code: WarningCode
    message: str


class SearchResponse(_Strict):
    search_id: UUID
    query_normalized: str
    warnings: list[SearchWarning] = Field(default_factory=list)
    timing_ms: float = Field(ge=0)
    lists: list[ResultList]


# ---------- /v1/feedback ----------

class FeedbackRequest(_Strict):
    # Query, chế độ và thứ hạng lấy từ bảng `searches` phía server, không nhận từ client (SPEC 14.4).
    # search_id không tồn tại, hoặc (system, article_id) không thuộc lượt tìm đó -> 422 INVALID_REQUEST
    # (nhóm chọn phương án A1, 2026-10-22; không thêm mã lỗi mới).
    search_id: UUID
    system: SystemName
    article_id: str
    label: FeedbackLabel


class FeedbackAck(_Strict):
    search_id: UUID
    system: SystemName
    article_id: str
    label: FeedbackLabel


# ---------- /v1/info ----------

class InfoLimits(_Strict):
    top_k_min: int = TOP_K_MIN
    top_k_max: int = TOP_K_MAX
    query_max_tokens: int


class FilterValues(_Strict):
    doc_types: list[str]
    domains: list[str]
    issuers: list[str]
    year_min: int | None
    year_max: int | None


class InfoResponse(_Strict):
    contract_version: str = CONTRACT_VERSION
    semantic_system: str          # giá trị `app.semantic_system` trong config (S2 khi phát triển)
    model_name: str
    model_revision: str
    manifest_hashes: dict[str, str]  # tên index -> hash manifest
    git_commit: str
    limits: InfoLimits
    filter_values: FilterValues
    modes: list[Mode]
