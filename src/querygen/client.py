"""Client sinh query. `GeminiClient` gọi Gemini qua HTTP bằng httpx (đã có trong requirements.txt; không thêm SDK).

Quy ước an toàn:
- API key chỉ đọc từ biến môi trường (`llm.api_key_env`), không bao giờ nằm trong config, log, repr hay thông báo lỗi.
- Test truyền `transport=httpx.MockTransport(...)`: không gọi mạng.
- Không tự đổi model; model và temperature lấy từ config.
"""
from __future__ import annotations

import os
from typing import Protocol

from .limits import RateLimitError, RetryableError

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class QueryClient(Protocol):
    def generate(self, prompt: str) -> str:
        """Nhận prompt đầy đủ, trả về chuỗi JSON theo schema trong prompt. Có thể raise RetryableError / RateLimitError."""


class MissingApiKeyError(RuntimeError):
    pass


class GeminiRequestError(RuntimeError):
    """Lỗi không retry được (4xx khác 429). Thông báo không chứa key."""


class GeminiClient:
    def __init__(self, model: str, temperature: float, *, api_key: str | None = None, api_key_env: str = "GEMINI_API_KEY",
                 transport=None, timeout: float = 60.0):
        key = api_key or os.environ.get(api_key_env)
        if not key:
            raise MissingApiKeyError(f"Thiếu API key: đặt biến môi trường {api_key_env} (không ghi key vào config hay repo).")
        if not model:
            raise ValueError("model chưa được chốt trong configs/querygen.yaml")
        self.model, self.temperature, self.timeout, self._transport = model, float(temperature), timeout, transport
        self._key = key

    def __repr__(self) -> str:  # không để lộ key
        return f"GeminiClient(model={self.model!r}, temperature={self.temperature})"

    def generate(self, prompt: str) -> str:
        import httpx

        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": self.temperature, "responseMimeType": "application/json"}}
        try:
            with httpx.Client(transport=self._transport, timeout=self.timeout) as c:
                r = c.post(ENDPOINT.format(model=self.model), json=body, headers={"x-goog-api-key": self._key})
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise RetryableError(f"lỗi mạng/timeout: {type(e).__name__}")
        if r.status_code == 429:
            ra = r.headers.get("retry-after")
            raise RateLimitError("429 rate limit", retry_after=float(ra) if ra and ra.replace(".", "", 1).isdigit() else None)
        if 500 <= r.status_code < 600:
            raise RetryableError(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise GeminiRequestError(f"HTTP {r.status_code}: yêu cầu bị từ chối (kiểm tra model/quyền truy cập AI Studio)")
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise RetryableError("phản hồi không có văn bản (có thể bị chặn hoặc sai định dạng)")
