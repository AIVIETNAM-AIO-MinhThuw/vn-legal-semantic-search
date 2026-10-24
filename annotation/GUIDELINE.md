# Guideline relevance v1 — bản hiệu chỉnh pilot

Đơn vị chấm là Điều, không phải chunk. Đọc query, tên văn bản, số/tiêu đề và toàn văn Điều.

| Nhãn | Quy tắc |
|---|---|
| 2 | Trả lời trực tiếp, đầy đủ nhu cầu được hỏi, đúng điều kiện và đối tượng. |
| 1 | Có ích để trả lời nhưng chỉ một phần, thiếu điều kiện, hoặc phải kết hợp Điều khác. |
| 0 | Không giúp trả lời; chỉ trùng từ/chủ đề không được coi là hữu ích. |

Không dùng kiến thức ngoài ngữ cảnh để đoán một Điều khác sẽ nói gì. Nếu thiếu ngữ cảnh cần thiết để quyết định, đánh dấu needs_review; không dùng 0 thay cho thiếu thông tin. Query mơ hồ chỉ đánh query_issue khi thật sự không thể đánh giá, không vì không có positive trong pool.

Evidence phải là đoạn liên tiếp có thật trong body. Nhãn 1/2 cần evidence giúp kiểm tra lý do; trích đoạn đúng chữ không tự chứng minh nhãn đúng. Không gộp nhiều đoạn thành một trích dẫn. Nhãn 0 có thể để evidence rỗng.

Các ví dụ chuẩn theo SPEC 10.1 được lưu riêng ở `annotation/examples.jsonl`: ít nhất hai cặp mỗi nhãn 0/1/2, lấy từ pool pilot và có nguồn truy vết. Chưa có ví dụ thì chưa gọi gán nhãn; không điền nhãn giả hoặc tự coi ví dụ minh họa là human gold. Ví dụ đưa vào prompt không được dùng làm cặp đo agreement.

Ví dụ có `review_status: unverified` là bản nháp chưa được người kiểm chứng, không phải nhãn người hay human gold. Không ghi tên người hoặc công cụ soạn ví dụ; vẫn giữ mã cặp và pool nguồn để truy vết.

Người kiểm chứng chấm độc lập, không thấy nhãn/reason/evidence của LLM hoặc nguồn/rank/score truy hồi. Bất đồng do người thứ hai phân xử, giữ lịch sử và lý do. Người giải quyết needs_review phải đọc đủ ngữ cảnh; không tự đổi thành 0.

Agreement, linear weighted kappa và confusion matrix chỉ mô tả mẫu cân bằng theo nhãn LLM, không ước lượng độ đúng toàn pool/dataset. Không khẳng định nhãn LLM chính xác trước kiểm chứng. Prompt/guideline thay đổi phải tăng version và dùng pilot mới theo SPEC.
