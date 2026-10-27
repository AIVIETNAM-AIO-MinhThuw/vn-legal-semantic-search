# Demo trên Windows: API (8000) + Streamlit (8501), dùng artifacts/ và configs/app.yaml.
param([int]$StartupTimeoutSeconds = 900)
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if ($StartupTimeoutSeconds -le 0) { throw 'StartupTimeoutSeconds phải lớn hơn 0.' }

$python = if ($env:PYTHON) {
  $env:PYTHON
} elseif (Test-Path -LiteralPath '.\.venv\Scripts\python.exe') {
  '.\.venv\Scripts\python.exe'
} else {
  'python'
}

$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
if (-not $env:APP_CONFIG) { $env:APP_CONFIG = 'configs/app.yaml' }

$api = $null
$uiExitCode = 0
try {
  $api = Start-Process -FilePath $python `
    -ArgumentList @('-m','uvicorn','src.api.app:app','--host','127.0.0.1','--port','8000','--workers','1') `
    -WorkingDirectory $root -PassThru -NoNewWindow
  $deadline = [DateTimeOffset]::UtcNow.AddSeconds($StartupTimeoutSeconds)
  $ready = $false
  Write-Host "API đang nạp model/index (tối đa ${StartupTimeoutSeconds}s; PID $($api.Id))..."

  while ([DateTimeOffset]::UtcNow -lt $deadline) {
    if ($api.HasExited) { throw 'API dừng trước khi sẵn sàng.' }
    try {
      $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3
      if ($health.status -eq 'ok') { $ready = $true; break }
    } catch {
      # API may return 503 while the model and indexes are still loading.
    }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) { throw "API chưa healthy sau ${StartupTimeoutSeconds}s." }

  Write-Host 'API sẵn sàng: http://127.0.0.1:8000/docs' -ForegroundColor Green
  $env:API_BASE_URL = 'http://127.0.0.1:8000'
  $env:UI_SAMPLE = '0'
  & $python -m streamlit run src/ui/app.py --server.address 127.0.0.1 --server.port 8501
  $uiExitCode = $LASTEXITCODE
} finally {
  if ($api -and -not $api.HasExited) {
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
    Wait-Process -Id $api.Id -Timeout 10 -ErrorAction SilentlyContinue
  }
}

exit $uiExitCode
