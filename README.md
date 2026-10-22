# Tìm kiếm ngữ nghĩa văn bản pháp luật (Đề tài 8)

Methodology: xem `SPEC.md` (nguồn sự thật duy nhất).

## Cài đặt

Yêu cầu Python 3.11.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # Linux/macOS
```

## Tải dữ liệu

Dataset `th1nhng0/vietnamese-legal-documents`, revision ghim trong `configs/data.yaml` (`dataset.revision`).

```bash
python scripts/download_data.py --config configs/data.yaml
```

File parquet được lưu vào `data/raw/` (không commit).

## Chạy EDA

```bash
python -X utf8 scripts/eda.py --config configs/data.yaml
```

Kết quả ở `reports/data_stats/`: `schema.md`, `eda_summary.md`, các file CSV, và `samples/` (10 HTML mẫu).

## Tải artifact

## Chạy lại final evaluation từ artifact

## Chạy app
