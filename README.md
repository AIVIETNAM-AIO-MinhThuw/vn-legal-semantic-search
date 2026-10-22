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

## Lọc, parse, chunk, validate (chưa split)

```bash
python -X utf8 scripts/prepare_data.py --config configs/data.yaml   # SPEC 3.2, 3.4, 3.5
python -X utf8 scripts/validate_data.py --config configs/data.yaml  # SPEC 3.6; dừng với lỗi nếu vi phạm
python -m pytest -q
```

Đầu ra: `data/processed/` (không commit), `logs/{rejected,long_sentence,parse_anomalies}.jsonl`, `logs/filter_counts.json`, `logs/filtered_out.tsv` (từng văn bản bị loại ở bước lọc 1-3, ~10 MB),
`reports/data_stats/after_filter/`. Sau `validate_data` phải dừng chờ nhóm xác nhận trước khi split.

## Tải artifact

## Chạy lại final evaluation từ artifact

## Chạy app
