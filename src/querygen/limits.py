"""Giới hạn tốc độ và retry. Đồng hồ và sleep được truyền vào để test không phải chờ thời gian thực."""
from __future__ import annotations

import time
from collections import deque
from typing import Callable


class RetryableError(Exception):
    """Lỗi tạm thời: rate limit, lỗi mạng, phản hồi sai schema."""

    def __init__(self, message: str = "", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitError(RetryableError):
    pass


class RateLimiter:
    """Tối đa `max_calls` lần gọi trong mỗi cửa sổ `window_seconds` (cửa sổ trượt)."""

    def __init__(self, max_calls: int, window_seconds: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if max_calls < 1 or window_seconds <= 0:
            raise ValueError("max_calls >= 1 và window_seconds > 0")
        self.max_calls, self.window, self.clock, self.sleep = max_calls, window_seconds, clock, sleep
        self._calls: deque[float] = deque()

    def acquire(self) -> float:
        """Chặn (qua sleep) cho tới khi được gọi; trả về số giây đã chờ."""
        waited = 0.0
        while True:
            now = self.clock()
            while self._calls and now - self._calls[0] >= self.window:
                self._calls.popleft()
            if len(self._calls) < self.max_calls:
                self._calls.append(now)
                return waited
            wait = self.window - (now - self._calls[0])
            self.sleep(wait)
            waited += wait


def call_with_retry(fn: Callable[[], object], *, max_attempts: int, base_delay: float, max_delay: float,
                    sleep: Callable[[float], None] = time.sleep, on_retry: Callable[[int, Exception, float], None] | None = None):
    """Gọi `fn`; với RetryableError thì chờ lùi theo cấp số nhân (hoặc `retry_after` nếu có) rồi gọi lại.
    Hết số lần thì raise lỗi cuối cùng. Lỗi khác RetryableError không được retry."""
    if max_attempts < 1:
        raise ValueError("max_attempts >= 1")
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except RetryableError as e:
            if attempt == max_attempts:
                raise
            delay = e.retry_after if e.retry_after is not None else min(max_delay, base_delay * 2 ** (attempt - 1))
            if on_retry:
                on_retry(attempt, e, delay)
            sleep(delay)
