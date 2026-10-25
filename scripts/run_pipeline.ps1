# Chạy toàn bộ thực nghiệm trên Windows có GPU (RTX 4050 6GB đã thử). Idempotent: bước nào đã có output thì bỏ qua.
# Từ gốc repo:  powershell -ExecutionPolicy Bypass -File scripts\run_pipeline.ps1
$ErrorActionPreference = 'Continue'  # PS 5.1: stderr của python không được coi là lỗi; kiểm tra bằng $LASTEXITCODE
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
New-Item -ItemType Directory -Force logs\pipeline | Out-Null
$log = "logs\pipeline\run_$(Get-Date -Format yyyyMMdd_HHmmss).log"
function Step($name, [scriptblock]$cmd) {
    Write-Host "==> $name" -ForegroundColor Cyan
    "==> $name  $(Get-Date -Format o)" | Add-Content $log
    & $cmd 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "Lỗi ở bước: $name (exit $LASTEXITCODE). Xem $log" }
}
$sets = @{
  'test' = 'data/eval_v1/queries_test.csv'
  'val' = 'data/eval_v1/queries_val.csv'
  'test_no_diacritic' = 'data/eval_v1/queries_test_no_diacritic.csv'
  'test_typo' = 'data/eval_v1/queries_test_typo.csv'
}
$order = 'test','val','test_no_diacritic','test_typo'

# 0. Model SBERT đa ngôn ngữ
if (!(Test-Path data/raw/paraphrase-multilingual-MiniLM-L12-v2/download.json)) {
  Step 'Tải SBERT' { & $py -X utf8 scripts/download_sbert.py }
}

# 1. Baseline + zero-shot
foreach ($s in $order) {
  if (!(Test-Path "runs/$s/bm25_s10")) { Step "BM25 $s" { & $py -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries $sets[$s] --output "runs/$s/bm25_s10" } }
  if (!(Test-Path "runs/$s/e5_s2"))    { Step "E5 zero-shot $s" { & $py -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries $sets[$s] --output "runs/$s/e5_s2" } }
  $build = @(); if (!(Test-Path indexes/sbert_mminilm)) { $build = @('--build') }
  if (!(Test-Path "runs/$s/sbert_mminilm")) { Step "SBERT $s" { & $py -X utf8 scripts/run_dense.py --config configs/dense_sbert.yaml --queries $sets[$s] --output "runs/$s/sbert_mminilm" @build } }
}

# 2. Fine-tune A: chọn LR trên val
$lrs = @('1e-05','3e-05')
foreach ($lr in $lrs) {
  if (!(Test-Path "models/e5_ft_A_lr$lr/val_metrics.json")) { Step "Train A lr=$lr" { & $py -X utf8 scripts/train_e5.py --config configs/train_e5.yaml --variant A --lr $lr } }
}
$best = $lrs | Sort-Object { -(Get-Content "models/e5_ft_A_lr$_/val_metrics.json" -Raw | ConvertFrom-Json).best } | Select-Object -First 1
"LR chọn trên val (A): $best" | Tee-Object -FilePath $log -Append
@{ selected_lr = $best; rule = 'max val NDCG@10 của cấu hình A'; candidates = $lrs } | ConvertTo-Json | Set-Content models/lr_selection.json -Encoding utf8

# 3. Fine-tune B với LR đã chọn
if (!(Test-Path "models/e5_ft_B_lr$best/val_metrics.json")) { Step "Train B lr=$best" { & $py -X utf8 scripts/train_e5.py --config configs/train_e5.yaml --variant B --lr $best } }

# 4. Truy hồi bằng model fine-tune
foreach ($v in 'A','B') {
  $model = "models/e5_ft_${v}_lr$best/model"
  foreach ($s in $order) {
    $build = @(); if (!(Test-Path "indexes/e5_ft_$v")) { $build = @('--build') }
    if (!(Test-Path "runs/$s/e5_ft_$v")) { Step "E5 FT $v $s" { & $py -X utf8 scripts/run_dense.py --config configs/dense_e5_ft.yaml --model $model --index "indexes/e5_ft_$v" --tag "e5_ft_$v" --queries $sets[$s] --output "runs/$s/e5_ft_$v" @build } }
  }
}

# 5. Bảng kết quả
Step 'Đánh giá' { & $py -X utf8 scripts/evaluate.py --config configs/eval.yaml }
Write-Host "XONG. Kết quả: reports/results/results.md" -ForegroundColor Green
