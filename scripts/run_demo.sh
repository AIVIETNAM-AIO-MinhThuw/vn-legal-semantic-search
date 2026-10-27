#!/usr/bin/env bash
# Demo trên Linux/macOS: API (8000) + Streamlit (8501), dùng artifacts/ và configs/app.yaml.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON=${PYTHON:-python}
STARTUP_TIMEOUT_S=${STARTUP_TIMEOUT_S:-900}

if ! [[ "$STARTUP_TIMEOUT_S" =~ ^[1-9][0-9]*$ ]]; then
  echo "STARTUP_TIMEOUT_S phải là số nguyên dương." >&2
  exit 2
fi

export PYTHONUTF8=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export APP_CONFIG=${APP_CONFIG:-configs/app.yaml}

"$PYTHON" -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --workers 1 &
API_PID=$!

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "API đang nạp model/index (tối đa ${STARTUP_TIMEOUT_S}s)..."
deadline=$((SECONDS + STARTUP_TIMEOUT_S))
ready=0
while (( SECONDS < deadline )); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "API dừng trước khi sẵn sàng." >&2
    exit 1
  fi
  status=$("$PYTHON" -c 'from urllib.error import HTTPError; from urllib.request import urlopen; exec("try:\n print(urlopen(\"http://127.0.0.1:8000/health\", timeout=2).status)\nexcept HTTPError as e:\n print(e.code)\nexcept Exception:\n print(0)")' 2>/dev/null || true)
  if [[ "$status" == "200" ]]; then
    ready=1
    break
  fi
  sleep 2
done

if (( ! ready )); then
  echo "API chưa healthy sau ${STARTUP_TIMEOUT_S}s." >&2
  exit 1
fi

echo "API sẵn sàng: http://127.0.0.1:8000/docs"
API_BASE_URL=http://127.0.0.1:8000 UI_SAMPLE=0 \
  "$PYTHON" -m streamlit run src/ui/app.py --server.address 127.0.0.1 --server.port 8501
