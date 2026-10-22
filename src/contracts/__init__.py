"""Schema dữ liệu dùng chung cho API và UI (SPEC 14.1, 14.5).

`ui/` chỉ được import gói này và thư viện bên thứ ba.
"""
from src.contracts.schemas import (  # noqa: F401
    CONTRACT_VERSION,
    TOP_K_DEFAULT,
    TOP_K_MAX,
    TOP_K_MIN,
    ErrorBody,
    ErrorCode,
    ErrorResponse,
    FeedbackAck,
    FeedbackLabel,
    FeedbackRequest,
    FilterValues,
    HealthResponse,
    Highlight,
    InfoLimits,
    InfoResponse,
    Mode,
    ResultItem,
    ResultList,
    ScoreType,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SystemName,
    SearchWarning,
    WarningCode,
)
