# Mẫu bàn giao một phase

Đây là mẫu, không phải kết quả đã thực hiện. Sao chép thành `docs/phases/NN_ten_phase.md` khi có bàn giao thật; thay các mục “chưa ghi” bằng thông tin thực tế. Không coi mẫu này là quyền vượt điểm chờ của SPEC.

## 1. Phạm vi và phiên bản

- Phase / lần sửa: chưa ghi.
- Ngày, người code, người trình bày, reviewer: chưa ghi.
- Mục SPEC đã đọc và áp dụng: chưa ghi.
- Commit/revision code; phần chưa commit nếu có: chưa ghi.
- Config và dấu nhận diện phiên bản: chưa ghi.
- Việc được giao / việc chưa được phép làm: chưa ghi.

## 2. Bàn giao từ người code

| Đầu vào / đầu ra | Đường dẫn hoặc nơi tải | Phạm vi, đơn vị, trạng thái |
|---|---|---|
| Chưa bàn giao | Chưa ghi | Chưa xác nhận |

- Lệnh chạy lại từ thư mục gốc và điều kiện môi trường: chưa ghi; không ghi API key.
- Thời điểm chạy, exit code, log và kết quả test thực tế: chưa ghi.
- Số liệu xuất bởi script và nơi lưu: chưa ghi.
- Lỗi, thay đổi so với lần trước và giới hạn còn lại: chưa ghi.
- Artifact đã đóng file/ghi xong, không còn bị sửa trong lúc bàn giao: chưa xác nhận.

## 3. Review

| Kiểm tra | Cách kiểm tra / bằng chứng | Kết quả và giới hạn |
|---|---|---|
| Đối chiếu SPEC/config | Chưa ghi | Chưa kiểm tra |
| Tính nhất quán và nguồn số liệu | Chưa ghi | Chưa kiểm tra |
| Ca lỗi hoặc test có ý nghĩa | Chưa ghi | Chưa kiểm tra |
| Lệnh tái lập và đầu ra | Chưa ghi | Chưa kiểm tra |

- Kết luận: chưa review; không suy từ số test pass.
- Phần phải sửa / phần cần người quyết định: chưa ghi.
- Ai phê duyệt, duyệt nội dung nào và bằng chứng quyết định: chưa ghi.

## 4. Bàn giao phần trình bày

- Nội dung thuyết minh có thể dùng: chưa ghi.
- Notebook/hình/bảng đã tạo: chưa ghi; chỉ ghi file thực sự tồn tại.
- Nguồn của từng số/hình và lệnh xuất: chưa ghi.
- Đã chạy notebook từ kernel mới, kiểm tra nhãn/font/đơn vị: chưa kiểm tra hoặc không áp dụng.
- Số dùng trong paper có script tái lập theo SPEC 13: chưa kiểm tra.
- Nội dung chưa chắc, chưa được phép đánh giá hoặc chưa được duyệt đã ghi rõ: chưa xác nhận.
- Chưa tiết lộ thông tin bị cấm hoặc dùng LLM vào OOD/final labels: chưa kiểm tra.

## 5. Đóng mốc và việc tiếp theo

- Trạng thái cuối: WIP / chờ review / chờ nhóm duyệt / đã duyệt (chọn đúng trạng thái thực).
- Những file thuộc mốc này: chưa ghi.
- Dữ liệu/log lớn hoặc phần đang làm tiếp cần để riêng: chưa ghi.
- Điểm chờ SPEC hiện tại và người cần quyết định: chưa ghi.
- Người được giao commit/push và commit thực tế nếu đã có: chưa ghi.
- Việc tiếp theo: chưa ghi; không tự bắt đầu bước bị chặn.
