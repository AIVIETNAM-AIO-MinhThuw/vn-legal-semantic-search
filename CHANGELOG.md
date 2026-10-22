# Changelog (repo)

Thay đổi methodology được duyệt ghi ở bảng Changelog cuối `SPEC.md`. File này ghi thay đổi kỹ thuật của repo.

| Ngày | Thay đổi | File |
|---|---|---|
| 2026-10-22 | Phiên 2: thêm lọc/parse/chunk/validate_data (chưa split); tokenizer E5 ghim revision; hàm tiền tố E5 duy nhất | `scripts/prepare_data.py`, `scripts/validate_data.py`, `src/data/*`, `src/retrieval/e5_format.py`, `tests/test_data_pipeline.py`, `configs/data.yaml` |
| 2026-10-22 | Sửa 6 phát hiện code review: nhận diện chữ ký, ngữ cảnh đoạn trích, ô bảng, validate_data chỉ ghi khi đạt, n_articles sau dedup, log từng văn bản bị loại | `src/data/{parse,html_text}.py`, `scripts/{prepare_data,validate_data}.py`, `configs/data.yaml` (processed.filtered_out_log), `tests/test_review_fixes.py`, `pytest.ini` |
