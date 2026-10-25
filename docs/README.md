# Mục lục trình bày đồ án

Tài liệu này dẫn từ từng phase đến bằng chứng và nội dung trình bày. Methodology vẫn theo [SPEC](../SPEC.md); thứ tự triển khai, pooling tăng dần và freeze phải theo SPEC, không suy từ thứ tự các dòng trong bảng dưới.

## Tiến độ và nội dung cần bàn giao

Trạng thái ngày **2026-10-26** (bản nộp). Luồng cuối theo Changelog SPEC ngày 2026-10-26.

| Mốc | Trạng thái | Bằng chứng |
|---|---|---|
| 01 — Nguồn dữ liệu, EDA, phạm vi | Xong | [Notebook](../notebooks/01_eda.ipynb), [EDA](../reports/data_stats/eda_summary.md), [config](../configs/data.yaml), SPEC mục 17 (OI-10) |
| 02 — Chuẩn bị corpus | Xong (7.340 Điều, 14.281 chunk) | `scripts/prepare_data.py`, `scripts/validate_data.py`, `reports/data_stats/after_filter/` |
| 03 — Query | 4.641 query (natural/scenario/keyword) sau lọc trùng, chép nguyên văn | `data/interim/full_v2/queries_v2.csv`; provenance trong gói handoff Task 6 |
| 04 — Nhãn | Pseudo-qrels Điều nguồn; pilot gán nhãn LLM đã dừng | `data/interim/source_qrels_v1/`, [annotation.md](phases/annotation.md) |
| 05 — Split | 3.718 / 461 / 462, không chung Điều positive giữa các split | `data/splits_v2/overlap_report.json` |
| 06 — Retrieval và training | BM25 S1₀, SBERT, E5 zero-shot, E5 fine-tune A/B; LR 3e-5 chọn trên val | `models/*/val_metrics.json`, `models/lr_selection.json`, [bm25](phases/bm25.md), [e5](phases/e5.md) |
| 07 — Evaluation và phân tích lỗi | Xong trên test + biến thể không dấu/lỗi gõ; không có OOD | [results.md](../reports/results/results.md), `runs/` |
| 08 — Demo | Chạy được (API + Streamlit), hướng dẫn cho người clone | [README](../README.md), `scripts/run_demo.ps1` |

Không dùng bảng này để ghi “hoàn tất” chỉ vì có code, một file output hoặc một lần test đạt. Người cập nhật phải nêu artifact và kết quả kiểm chứng, đồng thời ghi các giới hạn còn lại.

## Đọc và viết tài liệu

- [Quy trình phối hợp theo phase](workflow.md).
- [Mẫu bàn giao code, review và trình bày](templates/phase_handoff.md).
- [Danh mục artifact và nguồn số liệu](artifacts.md).
- [Tổ chức notebook](../notebooks/README.md).
- [Tổ chức hình xuất](../reports/figures/README.md).

Sau mỗi phase, lưu bản bàn giao ở `docs/phases/NN_ten_phase.md` theo mẫu. Chỉ tạo khi có nội dung thật; không tạo sẵn báo cáo kết quả rỗng cho những phase tương lai. Nếu có nhiều vòng sửa, ghi revision/commit và bản kết quả tương ứng trong cùng hồ sơ hoặc file có version rõ ràng.

## Khung thuyết minh và slide

1. Bài toán, mục tiêu và phạm vi claim — đọc SPEC mục 1–2 khi được giao viết phần này.
2. Dữ liệu, EDA, lựa chọn phạm vi và giới hạn nguồn — mốc 01.
3. Xây corpus, chống leakage và thiết kế query/nhãn — mốc 02–04, 06.
4. Các phương pháp và thiết kế thí nghiệm — mốc 05, đối chiếu SPEC tương ứng.
5. Kết quả, kiểm định, phân tích lỗi và hạn chế — mốc 07; chưa điền số khi chưa được phép đánh giá.
6. Demo, cách tái lập, đóng góp và phần việc tiếp theo — mốc 08 và các bằng chứng đã duyệt.

Đây là khung trình bày, không phải nội dung kết luận hoặc phương pháp mới. Đối chiếu rubric môn học trước khi nộp; rubric chưa được cung cấp ở đây.

## Phân công

| Vai trò | Trách nhiệm | Người phụ trách |
|---|---|---|
| Pipeline | Code, test, chạy theo phạm vi được duyệt; bàn giao artifact và lệnh tái lập. | Nhóm chưa ghi tên. |
| Trình bày | Kiểm tra nguồn số liệu; tạo notebook/hình/thuyết minh của phase vừa được bàn giao. | Nhóm chưa ghi tên. |
| Review | Đối chiếu SPEC và code/artifact; phân biệt lỗi, giới hạn và quyết định cần người duyệt. | Nhóm chưa ghi tên. |
| Phê duyệt và Git | Quyết định tại điểm chờ, xác nhận nội dung bàn giao và commit/push theo phân công. | Nhóm chưa ghi tên. |

Một người có thể đảm nhiệm nhiều vai trò; ghi nhận đóng góp thực tế, không tạo lịch sử đóng góp hoặc kết quả kiểm chứng giả.

## Lịch sử

[Báo cáo baseline và pilot gán nhãn ngày 2026-10-25](phases/annotation.md): pilot gán nhãn LLM, đã dừng và thay bằng nhãn Điều nguồn ngày 2026-10-26.
