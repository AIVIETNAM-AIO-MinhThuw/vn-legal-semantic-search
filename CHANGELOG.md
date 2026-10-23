# Changelog (repo)

Thay đổi methodology được duyệt ghi ở bảng Changelog cuối `SPEC.md`. File này ghi thay đổi kỹ thuật của repo.

| Ngày | Thay đổi | File |
|---|---|---|
| 2026-10-23 | Sửa review PR #2: kiểm tra cặp system/score_type và danh sách highlights; đồng bộ mô tả lỗi với OpenAPI; ghim dependencies API/test. Giữ nguyên schema v1, chưa freeze. | `src/contracts/schemas.py`, `src/api/app.py`, `openapi.json`, `requirements.txt` |
| 2026-10-22 | Phiên 2: thêm lọc/parse/chunk/validate_data (chưa split); tokenizer E5 ghim revision; hàm tiền tố E5 duy nhất | `scripts/prepare_data.py`, `scripts/validate_data.py`, `src/data/*`, `src/retrieval/e5_format.py`, `tests/test_data_pipeline.py`, `configs/data.yaml` |
| 2026-10-22 | Sửa 6 phát hiện code review: nhận diện chữ ký, ngữ cảnh đoạn trích, ô bảng, validate_data chỉ ghi khi đạt, n_articles sau dedup, log từng văn bản bị loại | `src/data/{parse,html_text}.py`, `scripts/{prepare_data,validate_data}.py`, `configs/data.yaml` (processed.filtered_out_log), `tests/test_review_fixes.py`, `pytest.ini` |
| 2026-10-22 | Gói 1 — hợp đồng API v1 (SPEC 14.5, mốc freeze 12; chưa freeze): schema Pydantic, FastAPI khung 5 endpoint (chưa có SearchService, trả 503 `MODEL_NOT_READY`), sinh `openapi.json` 1.0.0, test snapshot. Quyết định của nhóm: `timing_ms` là một số; `system` ∈ {`bm25`,`semantic`,`hybrid`}; cảnh báo dạng `{code, message}`; feedback có `search_id`/`article_id` không thuộc lượt tìm → 422 `INVALID_REQUEST` (A1). Ràng buộc thêm: cặp `system`↔`score_type`, highlights tăng dần/không chồng/đã gộp/trong `content` | `src/contracts/{__init__,schemas}.py`, `src/api/{__init__,app,errors}.py`, `scripts/export_openapi.py`, `openapi.json`, `tests/test_api_contract.py`, `CHANGELOG.md` |
