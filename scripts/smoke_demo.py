"""Build and smoke-test the Compose demo, then stop only this run's containers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.contracts import HealthResponse, SearchRequest, SearchResponse  # noqa: E402

API_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_S = int(os.environ.get("SMOKE_TIMEOUT_S", "900"))
POLL_INTERVAL_S = float(os.environ.get("SMOKE_POLL_INTERVAL_S", "3"))
COMPOSE_FILE = ROOT / "docker-compose.yml"


def compose(project: str, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-p", project, "-f", str(COMPOSE_FILE), *args],
        cwd=ROOT,
        check=False,
        timeout=timeout,
    )


def check_health(deadline: float) -> None:
    url = f"{API_BASE_URL}/health"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status == 200:
                    HealthResponse.model_validate_json(response.read())
                    print("API /health: healthy")
                    return
        except HTTPError as error:
            if error.code not in (502, 503, 504):
                raise RuntimeError(f"API /health trả HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(min(POLL_INTERVAL_S, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"API chưa healthy sau {TIMEOUT_S} giây")


def send_smoke_query() -> None:
    query = os.environ.get(
        "SMOKE_QUERY", "Người lao động có những quyền và nghĩa vụ gì theo quy định pháp luật?"
    )
    for mode, systems in (
        ("bm25", ["bm25"]), ("semantic", ["semantic"]),
        ("hybrid", ["hybrid"]), ("compare", ["bm25", "semantic"]),
    ):
        send_query(SearchRequest(query=query, mode=mode, top_k=1), systems)


def send_query(request_model: SearchRequest, systems: list[str]) -> None:
    payload = json.dumps(request_model.model_dump(mode="json", exclude_none=True)).encode("utf-8")
    request = Request(
        f"{API_BASE_URL}/v1/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"API /v1/search trả HTTP {response.status}")
            result = SearchResponse.model_validate_json(response.read())
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API /v1/search trả HTTP {error.code}: {body}") from error
    if [group.system for group in result.lists] != systems:
        raise RuntimeError(f"Response smoke sai danh sách hệ thống: {request_model.mode}")
    if any(not group.items for group in result.lists):
        raise RuntimeError(f"Response smoke không có kết quả: {request_model.mode}")
    print(
        "API query: OK "
        f"({request_model.mode}, {result.timing_ms:.1f} ms)"
    )


def main() -> int:
    if TIMEOUT_S <= 0 or POLL_INTERVAL_S <= 0:
        print("SMOKE_TIMEOUT_S và SMOKE_POLL_INTERVAL_S phải lớn hơn 0", file=sys.stderr)
        return 2
    project = f"vnlegal-smoke-{uuid4().hex[:12]}"
    up_started = False
    exit_code = 0
    try:
        version = subprocess.run(
            ["docker", "compose", "version"], cwd=ROOT, check=False, timeout=15
        )
        if version.returncode:
            raise RuntimeError("Docker Compose không khả dụng")
        result = compose(project, "build", timeout=TIMEOUT_S)
        if result.returncode:
            raise RuntimeError(f"docker compose build thất bại (mã {result.returncode})")
        print(f"Khởi động stack smoke riêng: {project}")
        up_started = True
        result = compose(project, "up", "--detach", "--wait", "--wait-timeout", str(TIMEOUT_S),
                         timeout=TIMEOUT_S + 30)
        if result.returncode:
            raise RuntimeError(f"docker compose up thất bại (mã {result.returncode})")
        check_health(time.monotonic() + TIMEOUT_S)
        send_smoke_query()
        with urlopen("http://127.0.0.1:8501/_stcore/health", timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"UI health trả HTTP {response.status}")
        print("SMOKE PASS")
    except (OSError, subprocess.SubprocessError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"SMOKE FAIL: {error}", file=sys.stderr)
        exit_code = 1
        if up_started:
            try:
                compose(project, "ps", "--all", timeout=15)
                compose(project, "logs", "--no-color", "--tail", "80", timeout=15)
            except (OSError, subprocess.SubprocessError) as diagnostic_error:
                print(f"Không đọc được log Compose: {diagnostic_error}", file=sys.stderr)
    finally:
        if up_started:
            print(f"Dừng containers do smoke tạo ({project}); giữ nguyên volume feedback.")
            try:
                cleanup = compose(project, "down", "--remove-orphans", timeout=120)
                if cleanup.returncode:
                    exit_code = 1
                    print(
                        f"CẢNH BÁO: cleanup Compose thất bại (mã {cleanup.returncode}); "
                        "hãy dọn project này thủ công, không dùng -v.",
                        file=sys.stderr,
                    )
            except (OSError, subprocess.SubprocessError) as error:
                exit_code = 1
                print(f"CẢNH BÁO: không dọn được stack smoke: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
