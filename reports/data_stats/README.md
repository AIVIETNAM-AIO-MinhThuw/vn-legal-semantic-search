# Đầu ra thống kê dữ liệu

Nếu cần **xem và trình bày EDA**, mở [notebook EDA](../../notebooks/01_eda.ipynb). Các file CSV trong thư mục này là đầu ra máy sinh của [scripts/eda.py](../../scripts/eda.py), được giữ riêng để kiểm tra và tái lập; không cần mở từng file khi thuyết trình và không sửa số trực tiếp trong CSV.

## Các điểm vào

- [01_eda.ipynb](../../notebooks/01_eda.ipynb): câu chuyện EDA bằng bảng và biểu đồ.
- [eda_summary.md](eda_summary.md): báo cáo chữ đầy đủ do script sinh.
- [schema.md](schema.md): schema và số dòng của ba bảng nguồn.
- [handoff_for_review.md](handoff_for_review.md): biên bản review và bất thường đã ghi nhận.

## Nhóm file bằng chứng

| Nhóm | File |
|---|---|
| Metadata | `doc_type_counts.csv`, `effect_status_counts.csv`, `doc_type_x_effect_status.csv`, `year_counts.csv` |
| Lĩnh vực/ngành | `domain_counts_all.csv`, `domain_counts_core_effective.csv`, `nganh_counts_all.csv` |
| Nội dung/độ dài | `content_missing_empty.csv`, `core_effective_docs.csv`, `core_effective_by_type.csv`, `length_quantiles_core_effective.csv` |
| Quan hệ | `relationship_types.csv` |
| Mẫu kiểm tra | `samples/samples_index.csv`; HTML thô local bị loại khỏi Git |

`after_filter/` thuộc phase chuẩn bị corpus đang review, không phải kết quả EDA gốc và chưa dùng làm kết luận cuối.
