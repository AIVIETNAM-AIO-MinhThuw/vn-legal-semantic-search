<!-- BẢN NHÁP v0.1, CHƯA FREEZE. Sửa nội dung = tăng version (SPEC 5.1). Không chứa câu mẫu nào. Khác v0: keyword 1–6 âm tiết (nhóm duyệt 2026-10-24). -->
# Nhiệm vụ

Bạn nhận một danh sách Điều của văn bản pháp luật Việt Nam. Với **mỗi** Điều, viết đúng ba câu truy vấn mà một người dùng có thể gõ để tìm đúng Điều đó, hoặc đánh dấu bỏ qua nếu không đặt được câu hỏi.

## Ba kiểu truy vấn

- `natural`: câu hỏi của người dân, ngôn ngữ đời thường; không lặp thuật ngữ pháp lý của Điều khi có cách nói thông thường.
- `scenario`: mô tả một tình huống cụ thể mà Điều có thể trả lời.
- `keyword`: từ 1 đến 6 âm tiết, như gõ vào ô tìm kiếm. Âm tiết là một tiếng, tức phần chữ ngăn cách bởi khoảng trắng hoặc dấu câu.

## Cấm

- Chép nguyên câu hoặc cụm từ dài từ Điều.
- Nhắc số hiệu Điều (ví dụ "Điều" kèm một số).
- Nhắc số hiệu hoặc tên đầy đủ của văn bản.

## Bỏ qua

Nếu Điều không thể đặt câu hỏi hợp lý (ví dụ chỉ định nghĩa thủ tục nội bộ không có người dùng cuối), đặt `"skip": true` và ghi `skip_reason`.

## Định dạng trả về (chỉ JSON, không thêm chữ nào khác)

```json
{
  "results": [
    {
      "article_id": "<article_id đã cho>",
      "skip": false,
      "skip_reason": null,
      "queries": {"natural": "<chuỗi>", "scenario": "<chuỗi>", "keyword": "<chuỗi>"}
    }
  ]
}
```

- Mỗi `article_id` đã cho xuất hiện đúng một lần trong `results`.
- Khi `skip` là `true`, `queries` là `null`.

## Danh sách Điều

{{ARTICLES_JSON}}
