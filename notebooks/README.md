# Notebook trình bày theo phase

Thư mục dành cho phân tích, minh họa và xuất hình từ artifact đã bàn giao. Pipeline nghiên cứu vẫn nằm trong `scripts/` và `src/`; [SPEC mục 13](../SPEC.md) yêu cầu số trong paper tái lập bằng script, không chép số từ notebook.

## Notebook hiện có

- [01_eda.ipynb](01_eda.ipynb): bản trình bày EDA, chỉ đọc CSV do `scripts/eda.py` sinh và xuất hình vào `reports/figures/eda/`. Đây là file nên mở khi trình bày phase EDA; các CSV là bằng chứng chi tiết phía sau.

## Cách đặt tên khi có nội dung thật

| Notebook dự kiến, chưa tạo | Nội dung | Điều kiện bắt đầu |
|---|---|---|
| `02_corpus_audit.ipynb` | Minh họa parse/chunk, trước/sau lọc và dedup, thống kê validation. | Có bản artifact được bàn giao và trạng thái review rõ ràng; không đọc output đang ghi. |
| `03_split_audit.ipynb` | Thống kê họ, phân bố split và kết quả leakage đã kiểm tra. | Có báo cáo và phê duyệt theo SPEC; notebook không tự chia lại tập. |
| `04_queries_audit.ipynb` | Kiểu query, overlap, lý do loại/duyệt và nguồn split. | Có file query/version được bàn giao; không tạo/gợi ý/sửa OOD hoặc final labels. |
| `05_experiment_analysis.ipynb` | Phân tích run, bảng metric, kiểm định và lỗi từ kết quả được phép dùng. | Phân biệt val và kết quả chính thức; test/OOD chỉ sau freeze theo SPEC. |

Đây là gợi ý tổ chức phần trình bày, không phải thứ tự thực thi mới. Một phase có thể chỉ cần báo cáo Markdown và log thay vì notebook. Không tạo notebook rỗng để biểu thị hoàn tất.

## Quy ước thực hiện

1. Mở đầu bằng mục tiêu, mục SPEC liên quan, file nguồn, phiên bản và trạng thái artifact.
2. Tìm thư mục gốc từ vị trí notebook/thư mục làm việc; dùng đường dẫn tương đối, không hard-code đường dẫn máy cá nhân.
3. Đọc artifact hoặc dùng module của repo; không tự viết lại bộ lọc/parser/split/training trong notebook.
4. Ghi rõ mọi phép tổng hợp. Khi một số mới cần dùng trong paper, phối hợp đưa phép xuất số vào script tái lập trước khi sử dụng.
5. Phân biệt toàn metadata, tập mô tả còn hiệu lực, 8 lĩnh vực được chọn, corpus trước/sau dedup và các split. Không đổi tên giá trị gốc để gộp chúng khi chưa được duyệt.
6. Hình có tiêu đề, đơn vị, nhãn, chú thích phạm vi/nguồn và chữ đọc được. Top N phải ghi rõ; ước lượng không gọi là số thật.
7. Xuất hình theo [quy ước figures](../reports/figures/README.md). Không tải checkpoint hoặc chạy train/evaluate chỉ để có hình.
8. Chạy từ đầu tới cuối bằng kernel mới, lưu output và kiểm tra trực quan trước khi bàn giao. Không lưu credential, HTML thô khối lớn hoặc dữ liệu gán nhãn bị hạn chế trong notebook.

Phụ thuộc notebook được ghim riêng trong `requirements-notebooks.txt`. Cài bằng `python -m pip install -r requirements-notebooks.txt`, rồi đăng ký kernel của môi trường dự án theo lệnh trong README; việc này không đổi logic hay dependency của pipeline chính.

## Bàn giao

Liên kết notebook, hình và lệnh thực thi trong [mẫu phase](../docs/templates/phase_handoff.md), rồi cập nhật [tiến độ](../docs/README.md). Output notebook không thay thế log/test hoặc phê duyệt của nhóm.
