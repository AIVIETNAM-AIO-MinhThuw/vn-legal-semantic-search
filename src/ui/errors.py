"""Thông báo cố định; không đưa message từ API lên giao diện."""
from src.contracts import ErrorCode, WarningCode

ERRORS = {
    ErrorCode.EMPTY_QUERY: "Hãy nhập câu hỏi có nội dung.",
    ErrorCode.INVALID_FILTER: "Bộ lọc không còn hợp lệ.",
    ErrorCode.INVALID_REQUEST: "Yêu cầu không hợp lệ.",
    ErrorCode.MODEL_NOT_READY: "Hệ thống đang khởi động.",
    ErrorCode.INDEX_MANIFEST_MISMATCH: "Index không khớp cấu hình, cần người vận hành kiểm tra.",
}
WARNINGS = {WarningCode.QUERY_TRUNCATED: "Câu hỏi quá dài, đã được rút gọn."}
UNAVAILABLE = "Dịch vụ tìm kiếm chưa sẵn sàng."
FEEDBACK_FAILED = "Chưa ghi được phản hồi."
SEARCH_EXPIRED = "Lượt tìm đã hết hạn, hãy tìm lại."
EXPORT_FAILED = "Chưa tải được feedback."


class ApiFailure(Exception):
    def __init__(self, code=ErrorCode.INVALID_REQUEST, *, status=None, connection=False):
        self.code = code
        self.status = status
        self.connection = connection
        super().__init__(UNAVAILABLE if connection else ERRORS.get(code, ERRORS[ErrorCode.INVALID_REQUEST]))


def error_text(code):
    return ERRORS.get(code, ERRORS[ErrorCode.INVALID_REQUEST])
