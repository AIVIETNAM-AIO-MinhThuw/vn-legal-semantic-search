# Hình dùng trong báo cáo và slide

Lưu hình xuất thực tế theo phase. Thư mục `eda/` được tạo bởi [notebook EDA](../../notebooks/01_eda.ipynb) từ các CSV thống kê; đây là hình dẫn xuất để trình bày, còn CSV và `scripts/eda.py` là nguồn tái lập.

Ví dụ đường dẫn dự kiến:

```text
reports/figures/
  01_eda/           Phân bố và chất lượng dữ liệu
  02_corpus/        Trước/sau xử lý, ví dụ và validation
  03_split/         Họ văn bản, phân bố và kiểm tra split
  04_queries/       Thống kê query được phép công bố
  05_experiments/   Phân tích thực nghiệm được phép theo SPEC
  08_demo/          Ảnh ứng dụng thực chạy
```

Chỉ tạo thư mục khi có hình thật. Không có hình không có nghĩa code của phase chưa tồn tại; tiến độ ghi tại [docs/README.md](../../docs/README.md).

- Đặt tên theo nội dung, ví dụ `doc_type_counts.png`; tên không chứa kết luận chưa được chứng minh.
- Ưu tiên PNG cho báo cáo/slide, có thể thêm SVG/PDF nếu cần. Kiểm tra font tiếng Việt, nhãn không bị cắt và màu/phân biệt nhóm dễ đọc.
- Ghi file nguồn, script/notebook tạo hình, phạm vi, đơn vị, ngày/version và chú thích trong hồ sơ phase. Lưu config/phiên bản phù hợp để xuất lại, không chỉ lưu ảnh chụp màn hình.
- Nếu sửa dữ liệu biểu diễn (ví dụ log scale hoặc top N), ghi rõ; không bỏ nhóm bất thường để biểu đồ trông đẹp hơn.
- Sơ đồ phương pháp phải theo SPEC. Ảnh demo phải từ lần chạy thật; mockup nếu có phải ghi rõ là minh họa.
- Không tạo hình metric test/OOD trước thời điểm SPEC cho phép. Không đưa thông tin bị cấm (mục 10.2 SPEC) vào dữ liệu gửi cho LLM gán nhãn hoặc người kiểm chứng.

Số xuất hiện trong hình và dùng trong paper phải truy được về script/artifact, theo [SPEC](../../SPEC.md). Notebook có thể dùng để xuất hình, không trở thành nguồn số liệu độc lập với pipeline.
