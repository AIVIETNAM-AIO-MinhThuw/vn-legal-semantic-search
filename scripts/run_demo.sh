#!/usr/bin/env bash
# Demo trên Linux/macOS: API (8000) + Streamlit (8501). Chạy từ gốc repo, đã kích hoạt venv và có JAVA_HOME.
set -euo pipefail
export PYTHONUTF8=1 APP_CONFIG=configs/app.yaml
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
echo "API đang nạp model/index..."
for _ in $(seq 120); do
  if ! kill -0 $API 2>/dev/null; then echo "API dừng do lỗi"; exit 1; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)
  [ "$code" = 200 ] && break
  [ "$code" = 503 ] && { echo "API không nạp được model/index (503), xem log ở trên"; exit 1; }
  sleep 2
done
API_BASE_URL=http://127.0.0.1:8000 UI_SAMPLE=0 python -m streamlit run src/ui/app.py --server.port 8501
