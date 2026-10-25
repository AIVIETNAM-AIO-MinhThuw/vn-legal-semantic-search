# Chạy demo: API (FastAPI, cổng 8000) + giao diện Streamlit (cổng 8501). Từ gốc repo:
#   powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:APP_CONFIG = 'configs/app.yaml'
$api = Start-Process -FilePath $py -ArgumentList '-m','uvicorn','src.api.app:app','--host','127.0.0.1','--port','8000' -PassThru -NoNewWindow
Write-Host "API đang nạp model/index (PID $($api.Id))..."
for ($i = 0; $i -lt 120; $i++) {
  if ($api.HasExited) { Write-Host 'API dừng do lỗi, xem log ở trên.' -ForegroundColor Red; exit 1 }
  try { $r = Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 2; if ($r.status -eq 'ok') { break } }
  catch { if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 503) {
      Write-Host 'API chạy nhưng không nạp được model/index (503). Xem lỗi "Không nạp được SearchService" ở trên.' -ForegroundColor Red
      Stop-Process -Id $api.Id -ErrorAction SilentlyContinue; exit 1 } }
  Start-Sleep -Seconds 2
}
Write-Host "API sẵn sàng: http://127.0.0.1:8000/docs" -ForegroundColor Green
$env:API_BASE_URL = 'http://127.0.0.1:8000'
$env:UI_SAMPLE = '0'
try { & $py -m streamlit run src/ui/app.py --server.port 8501 }
finally { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
