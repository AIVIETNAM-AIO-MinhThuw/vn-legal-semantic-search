# Mục lục trình bày đồ án

Tài liệu này dẫn từ từng phase đến bằng chứng và nội dung trình bày. Methodology vẫn theo [SPEC](../SPEC.md); thứ tự triển khai, pooling tăng dần và freeze phải theo SPEC, không suy từ thứ tự các dòng trong bảng dưới.

## Tiến độ và nội dung cần bàn giao

Trạng thái được ghi nhận ngày **2026-10-22**, dựa trên repo và lần review gần nhất. Đây là ảnh chụp tiến độ, không tự đồng bộ khi code hoặc artifact thay đổi.

| Mốc tài liệu | Trạng thái quan sát | Phần trình bày cần hoàn thiện | Bằng chứng hiện có / còn chờ |
|---|---|---|---|
| 01 — Nguồn dữ liệu, EDA và phạm vi | Có kết quả EDA và notebook trình bày; OI-10 đã ghi trong SPEC/config. | Nguồn/revision/schema, phân bố, dữ liệu thiếu, bất thường, căn cứ và hạn chế của phạm vi được nhóm chọn. | [Notebook](../notebooks/01_eda.ipynb), [EDA](../reports/data_stats/eda_summary.md), [schema](../reports/data_stats/schema.md), [config](../configs/data.yaml), SPEC mục 17. |
| 02 — Chuẩn bị corpus | WIP, chưa duyệt. Review gần nhất còn ba lỗi: nhận diện chữ ký, xử lý ngoặc không cân bằng và validation đầu vào rỗng. | Sơ đồ xử lý, bảng trước/sau, ví dụ Điều/chunk, lý do loại, dedup, test và giới hạn parser. | Code trong `scripts/`/`src/data/`; output local trong `data/processed/`, `logs/`, `reports/data_stats/after_filter/`. Chờ bản sửa được kiểm chứng. |
| 03 — Họ văn bản, split dataset và chồng lấn | Chưa có bằng chứng hoàn tất khi kiểm kê. (Cập nhật 2026-10-25: split theo họ trước sinh query đã bị thay thế; `data/splits.json` chỉ còn là lịch sử. Split dataset thực hiện sau mốc 04 và 06.) | Minh họa họ và nút trung gian; đơn vị chia theo OI-12; số query/cặp nhãn theo split; số liệu chồng lấn Điều/văn bản/họ và phê duyệt. | Chờ dataset có nhãn và quyết định OI-12. |
| 04 — Query và chuẩn bị đánh giá | Chưa có artifact được bàn giao. | Điều nguồn từ toàn corpus, thống kê kiểu query, lý do loại/đánh dấu, version prompt/model, provenance và freeze. | Chờ file query, cấu hình và log; OOD do người viết, không để LLM tạo/gợi ý/sửa. |
| 05 — Retrieval và training | Mới có helper tiền tố E5; chưa có bằng chứng các hệ thống được chạy. | Sơ đồ hệ thống, cấu hình, dữ liệu đầu vào, manifest, log train và căn cứ chọn cấu hình trên val. | Chờ run/config/log/checkpoint theo phase; không dùng test/OOD để lựa chọn. |
| 06 — Pooling và gán nhãn | Chưa có artifact được bàn giao. | Pool tạo dataset, protocol gán nhãn LLM, pilot và đồng thuận người–LLM, lịch sử nhãn, dataset có nhãn; pool bổ sung và freeze qrels. | Chờ dữ liệu thực; giữ blind; nhãn LLM là nhãn dataset, kiểm chứng bằng người trên mẫu (SPEC mục 9–10). |
| 07 — Evaluation và phân tích lỗi | Chưa thực hiện chính thức. | Bảng metric, per-query results, kiểm định và phân tích lỗi/giới hạn có bằng chứng. | Chỉ tạo kết quả test/OOD sau khi đủ điều kiện freeze theo SPEC. Trước đó chỉ integrity và phân tích được phép. |
| 08 — Demo và tổng hợp báo cáo | App hiện là khung; báo cáo/slide cuối chưa được bàn giao. | Kịch bản demo, hướng dẫn CPU/artifact, ảnh ứng dụng thật, kết luận và hạn chế; tổng hợp các mốc đã duyệt. | Chờ ứng dụng chạy được và bằng chứng các phase trước. |

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
