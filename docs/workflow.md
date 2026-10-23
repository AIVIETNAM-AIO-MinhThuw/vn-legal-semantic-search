# Phối hợp sau mỗi phase nhỏ

Áp dụng từ EDA đến demo. Mục đích là bàn giao và trình bày bằng chứng; mọi điều kiện chạy, sửa methodology, split, nhãn và freeze vẫn theo [SPEC](../SPEC.md) và [CLAUDE](../CLAUDE.md).

## 1. Người code bàn giao

Sử dụng [mẫu](templates/phase_handoff.md), ghi phạm vi vừa làm, phiên bản code/config, lệnh chạy, môi trường, file đầu ra và kết quả test. Phân biệt code đã viết, lần chạy thành công và nội dung chưa chắc. Báo lỗi hoặc thay đổi số liệu, không giấu sau câu “test đều pass”.

Kết quả phải đóng file/ghi xong trước khi người khác đọc. Không dùng file 0 byte hoặc đang ghi như bằng chứng phase đã hoàn tất. Khi có thể, dùng một bản output có version/hash đã bàn giao; không sửa output gốc để làm hình đẹp hơn.

## 2. Reviewer kiểm tra

Đối chiếu đúng mục SPEC liên quan, đọc code/test và kiểm tra artifact. Ghi cách tái hiện với từng lỗi; phân biệt lỗi thực tế với giả định. Chỉ kết luận trong phạm vi đã kiểm tra.

Nếu cần người quyết định vì điểm mơ hồ ảnh hưởng dữ liệu/split/nhãn/metric, báo theo điểm chờ. Người trình bày có thể tổ chức nội dung đã chắc chắn, nhưng ghi rõ phần chưa duyệt và không coi số WIP là kết quả cuối.

## 3. Người trình bày tiếp nhận

- Chỉ xử lý phase được bàn giao, không chạy trước bước tiếp theo để có thêm hình hoặc metric.
- Notebook dùng để khám phá, giải thích và minh họa; dùng script/module của repo và artifact để tránh hai cách tính khác nhau.
- Số đưa vào paper phải sinh lại bằng script theo SPEC mục 13. Nếu một con số mới chỉ được tính trong notebook, phối hợp bổ sung đầu ra tái lập trước khi dùng làm số chính thức; không chép số tay.
- Ghi rõ đầu vào, phạm vi, đơn vị, nguồn file, trạng thái và giới hạn cho bảng/hình. Phân biệt EDA ước lượng, dữ liệu trước/sau dedup, val và test/OOD.
- Lưu hình vào thư mục của phase trong `reports/figures/`, notebook vào `notebooks/`, phần bàn giao/thuyết minh vào `docs/phases/`.
- Ghi lệnh thực thi notebook và version phụ thuộc khi notebook được triển khai. Không ép mọi phase phải có notebook; log, test và báo cáo có thể là bằng chứng phù hợp hơn.

## 4. Nhóm chốt mốc

Cập nhật [bảng tiến độ](README.md), ghi ai review/duyệt và nội dung còn mở. Việc này không tự cấp quyền vượt điểm chờ của SPEC. Freeze chỉ ghi vào [data/FROZEN.md](../data/FROZEN.md) khi đúng thời điểm và được phép.

Nhóm tự chọn commit hoàn tất hoặc WIP. Xem file staged trước khi commit; tách tài liệu trình bày và code đang làm dở nếu thuộc hai mốc khác nhau. Không dùng `git add .` như mặc định khi repo đang có log lớn hoặc output chưa duyệt. Người/agent chỉ được commit/push khi được giao.

## 5. Giữ bằng chứng qua các vòng sửa

Giữ bản kết quả trước khi chạy lại nếu cần so sánh; ghi nguyên nhân chênh lệch sau sửa. Sự thay đổi parser hoặc số lượng không tự động chứng minh chất lượng tăng. Phân biệt số đã đo, suy luận và điều chưa biết.

Hồ sơ [evidence-loop](../.evidence-loop/PROJECT.md) ghi quan sát và giới hạn của quy trình. Nó không thay thế thí nghiệm, review hoặc methodology trong SPEC.
