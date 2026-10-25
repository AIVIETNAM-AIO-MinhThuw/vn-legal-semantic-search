# Nguồn số liệu và bằng chứng

Theo [SPEC mục 13](../SPEC.md), số trong paper phải tái lập bằng lệnh ghi trong README. Bảng này là danh mục truy vết, không xác nhận mọi phase đã xong.

## Artifact hiện có

| Phần | Nguồn | Vai trò / giới hạn |
|---|---|---|
| Methodology | [SPEC](../SPEC.md), [config](../configs/data.yaml) | Quy định và tham số thực thi. Số liệu phải gắn với đúng phiên bản config/code. |
| Dữ liệu nguồn | `data/raw/data/{metadata,content,relationships}.parquet` | Không commit; tải bằng [download_data.py](../scripts/download_data.py) theo revision. Đây là đường dẫn local, không phải file có sẵn trên GitHub. |
| EDA tổng quan | [schema](../reports/data_stats/schema.md), [summary](../reports/data_stats/eda_summary.md) | Cấu trúc, phạm vi thống kê và nguồn revision. Sinh bởi [eda.py](../scripts/eda.py). |
| Trình bày EDA | [notebook](../notebooks/01_eda.ipynb), `reports/figures/eda/` | Điểm vào dành cho người xem; chỉ đọc các CSV EDA và xuất biểu đồ, không thay logic thống kê. |
| Phân bố đầu vào | [loại](../reports/data_stats/doc_type_counts.csv), [hiệu lực](../reports/data_stats/effect_status_counts.csv), [bảng chéo](../reports/data_stats/doc_type_x_effect_status.csv), [năm](../reports/data_stats/year_counts.csv) | Các bảng toàn metadata, giữ riêng nhóm thiếu/không đọc được theo cách EDA ghi nhận. |
| Lĩnh vực | [toàn tập](../reports/data_stats/domain_counts_all.csv), [ngành](../reports/data_stats/nganh_counts_all.csv), [tập mô tả](../reports/data_stats/domain_counts_core_effective.csv) | Không trộn cột `nganh` với `linh_vuc`; tập mô tả dùng đúng loại/hiệu lực ghi trong summary. |
| Nội dung và độ dài | [thiếu/rỗng](../reports/data_stats/content_missing_empty.csv), [phân vị](../reports/data_stats/length_quantiles_core_effective.csv), [từng văn bản](../reports/data_stats/core_effective_docs.csv), [theo loại](../reports/data_stats/core_effective_by_type.csv) | Độ dài là ký tự, không phải token E5; số Điều regex chỉ là ước lượng. |
| Quan hệ trước xử lý | [relationship_types.csv](../reports/data_stats/relationship_types.csv) | Cạnh gốc và tỷ lệ hai đầu ánh xạ metadata; không phải kết quả gom họ. |
| Review EDA | [handoff_for_review.md](../reports/data_stats/handoff_for_review.md) | Nhận xét reviewer; không dùng thay nguồn số liệu hoặc quyết định trong SPEC. |
| Mẫu EDA | [samples_index.csv](../reports/data_stats/samples/samples_index.csv) | Chỉ mục mẫu; HTML thô local không commit theo gitignore. |
| Chuẩn bị corpus — WIP | `data/processed/{docs,articles,chunks}.jsonl` và các file `*_index.jsonl` | Output local không commit; file index ở đây là dữ liệu sau dedup, chưa phải hệ thống truy hồi. Chờ review/duyệt. |
| Nhật ký — local | `logs/filter_counts.json`, `logs/filtered_out.tsv`, `logs/rejected.jsonl`, `logs/parse_anomalies.jsonl`, `logs/long_sentence.jsonl` | Truy vết xử lý; kiểm tra dung lượng/nội dung trước khi quyết định đưa vào Git. |
| Báo cáo sau xử lý — WIP | `reports/data_stats/after_filter/` | Đang có ở máy và chưa được Git theo dõi khi lập danh mục. Báo cáo validate đạt chưa thay thế review parser. Không dùng số ở đây làm kết luận cuối. |
| Kiểm thử | [test pipeline](../tests/test_data_pipeline.py), [test lỗi review](../tests/test_review_fixes.py) | Code kiểm thử; khi bàn giao cần kèm kết quả/lệnh/môi trường thực chạy. |

## Artifact cần bổ sung khi phase tương ứng hoàn tất

| Phase | Bằng chứng cần người code cung cấp | Phần trình bày tạo từ bằng chứng |
|---|---|---|
| Split dataset | Mapping họ, đơn vị chia theo OI-12, split dataset đã duyệt, báo cáo chồng lấn, seed/config/hash. `data/splits.json` chỉ là lịch sử. | Sơ đồ minh họa, bảng phân bố và giải thích giới hạn; không tự split lại. |
| Query | File query đã lưu, đầu vào/đầu ra thô, prompt/model/version, log loại/đánh dấu và hash theo SPEC. | Thống kê kiểu query, overlap (chỉ phân tích), lý do loại và các ví dụ được phép dùng. Không để LLM viết/sửa OOD. |
| Retrieval/training | Config/manifest, log, checkpoint/revision, run val và căn cứ chọn cấu hình. BM25: `bm25s`, VNCoreNLP + unigram; S1₀ `k1 = 1.2`, `b = 0.75`, ghi phiên bản/checksum segmenter và biến thể công thức. E5: tokenizer riêng trên văn bản tự nhiên. BM25 và E5 đã chạy local; xem [BM25](phases/bm25.md), [E5](phases/e5.md). Chưa có nhãn hoặc metric chất lượng. | Sơ đồ phương pháp, bảng cấu hình, diễn biến train và kết quả val được phép báo. |
| Pooling/gán nhãn | Pool tạo dataset và các phiên bản pool bổ sung, protocol blind, judgment LLM thô, nhãn người kiểm chứng pilot, lịch sử nhãn, dataset có nhãn, qrels và bằng chứng freeze. | Sơ đồ quy trình, thống kê nhãn, đồng thuận người–LLM trên mẫu và giới hạn; không gọi nhãn là human gold. |
| Final evaluation | Run file, per-query metrics, script xuất bảng, kiểm định, qrels/query/split đã freeze. | Bảng/hình kết quả chính thức và phân tích lỗi; chỉ thực hiện khi SPEC cho phép. |
| Demo | App dùng loader/retriever chung, artifact/revision, lệnh chạy CPU đã kiểm chứng và ví dụ thật. | Kịch bản, ảnh/video thực chạy và hướng dẫn người xem tái lập. |

Đường dẫn/tên file tương lai xác định theo SPEC và code đã bàn giao, không tự tạo file giả để làm đầy danh mục. Checkpoint/index lớn theo nơi lưu trong SPEC 13.2; không commit binary lớn.

## Thông tin tối thiểu cho mỗi bảng/hình

- Phase và trạng thái: WIP, đã review hoặc đã được duyệt.
- File nguồn, phạm vi, đơn vị và cách tổng hợp; phân biệt ước lượng với số đo.
- Script/lệnh tạo artifact; phiên bản code/config và môi trường.
- Notebook/lệnh xuất hình nếu có, đường dẫn file xuất và nhận xét có căn cứ.
- Giới hạn và điều chưa kiểm tra. Không có dữ liệu thì ghi chưa có, không điền số mẫu vào bảng kết quả.
