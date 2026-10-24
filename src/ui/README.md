# P4-UI — giao diện demo

Chạy từ gốc repo, Python 3.11 trở lên:

```sh
python -m pip install -r requirements-ui.txt
UI_SAMPLE=1 streamlit run src/ui/app.py
```

PowerShell:

```powershell
python -m pip install -r requirements-ui.txt
$env:UI_SAMPLE=1; streamlit run src/ui/app.py
```

Để dùng HTTP thật, bỏ `UI_SAMPLE` hoặc đặt `0`, đặt `API_BASE_URL` nếu cần
(mặc định `http://api:8000`). `UI_TIMEOUT_S` mặc định `30` giây.
API hiện là stub trả 503; chế độ mẫu không cần API, model, index hoặc torch.

## Cách xem demo

Nhập câu hỏi bất kỳ và nhấn Tìm (hoặc Enter). UI gửi nguyên văn chuỗi nhập,
không kiểm tra rỗng, chuẩn hóa Unicode, tách từ hay rút gọn query.
Đổi chế độ hoặc bộ lọc sẽ dùng lại **câu hỏi đã gửi gần nhất**, kể cả khi đang
gõ một câu hỏi mới trong form. Bấm tiêu đề Điều để đọc và gửi phản hồi.

Trong expander cuối trang, chọn `Kịch bản (chế độ mẫu)`. Các kịch bản lỗi
query/filter và cảnh báo tác động tới lần tìm; lỗi model/manifest/kết nối
tác động cả thông tin hệ thống. Đổi kịch bản khi đã tìm sẽ tải lại info và
tìm lại. Nếu chưa tìm lần nào, hãy bấm Tìm để thấy lỗi query/filter.
`feedback lỗi` cũng mô phỏng lỗi xuất CSV qua nút Chuẩn bị CSV feedback.

## Giới hạn và giả định

- Nội dung, tên Điều, văn bản và cơ quan trong JSON là **hư cấu**, không lấy từ
  `data/processed`. Tên 8 lĩnh vực lấy nguyên chuỗi đã chốt trong
  `configs/data.yaml`; model/revision là thông tin cấu hình, không chứng minh
  model đã chạy. Hash manifest và git commit trong info được ghi rõ là mẫu.
- JSON là fixture biên soạn cho trình bày; chỉnh trực tiếp khi cần đổi kịch bản.
  `SampleClient` nạp và validate **tất cả** JSON bằng schema hợp đồng tương ứng.
  Không có pipeline lấy corpus hay logic retrieval trong UI.
- Mẫu có 10 item mỗi danh sách. Top-k nhỏ hơn 10 cắt danh sách; lớn hơn 10 vẫn
  chỉ có 10 item. Bộ lọc mô phỏng chọn/xóa/tìm lại và không lọc nội dung fixture;
  chọn `rỗng` để xem trạng thái không có kết quả. Feedback mẫu chỉ nằm trong RAM
  của phiên trình duyệt; CSV mẫu chỉ chứa 4 trường của FeedbackRequest.
- `InfoLimits` không có trường top-k mặc định; UI dùng mặc định 10 theo brief,
  chặn trong khoảng do info cung cấp. Khi giới hạn min=max, hiển thị số cố định
  vì slider gốc yêu cầu min < max. Khi Semantic không khả dụng, chọn chế độ
  đầu tiên từ info. Không tự thêm chế độ hoặc giá trị bộ lọc.
- Hợp đồng feedback dùng chung `422 INVALID_REQUEST` cho search_id không tồn
  tại và item không thuộc lượt tìm. Sau khi dựng request đúng schema, UI coi
  mã này là lượt tìm hết hạn. Không đọc `error.message` để đoán nguyên nhân;
  cần mã lỗi riêng từ hợp đồng tương lai để phân biệt chính xác.
- Dùng Streamlit 1.50.0 để có nút tertiary, segmented control và container
  căn giữa rộng tối đa 1200px. `.streamlit/config.toml` chọn theme light mặc định
  và toolbar viewer, không đặt màu. Một khối CSS trong `app.py` chỉ căn trái và
  đặt độ đậm 600 cho nút tiêu đề Điều qua class `st-key-article-…`.
  Tiêu đề nút tự xuống dòng. Số dòng caption tên văn bản và đoạn trích tùy
  chiều rộng viewport; không ép 1 dòng hoặc 2–3 dòng bằng CSS. Đoạn trích bỏ
  xuống dòng thành khoảng trắng cùng độ dài code point; toàn văn giữ xuống dòng.
- Semantic/Hybrid hiện đúng câu highlight trong thẻ; BM25 hiện cửa sổ khoảng
  250 ký tự quanh span đầu. Một câu rất dài có thể vượt 250 ký tự để không cắt
  mất câu highlight. Reader dùng container cuộn cao 420px và dialog lớn gốc.
- Không viết hoặc chạy bộ test UI trong P4-UI. Ảnh mẫu chỉ là bằng chứng trình
  bày, chưa phải nghiệm thu API thật hoặc kiểm thử đủ các tương tác.

## File bàn giao

| File | Chức năng |
|---|---|
| `app.py` | Điểm vào, tải info và điều phối tìm/lỗi |
| `client.py` | HTTP client và client mẫu cùng 4 phương thức |
| `errors.py` | Thông báo tiếng Việt theo mã lỗi/cảnh báo |
| `highlight.py` | Escape HTML, tô span, cắt và dịch vị trí đoạn trích |
| `compare.py` | Đếm trùng/riêng và tra hạng theo article_id |
| `layout.py` | Đầu trang, form, chế độ, bộ lọc/chip, trạng thái, chân trang |
| `cards.py` | Thẻ một cột hoặc so sánh hai cột |
| `reader.py` | Dialog đọc và feedback theo lượt tìm/hệ thống/Điều |
| `state.py` | Trạng thái phiên và callback tìm lại |
| `README.md` | Lệnh chạy, giới hạn, kiểm kê và kiểm thử để lại |
| `sample_data/info.json` | Info mẫu, giới hạn và giá trị bộ lọc |
| `sample_data/search_semantic.json` | 10 Điều, thang cosine |
| `sample_data/search_bm25.json` | 10 Điều, highlight nhiều đoạn rời |
| `sample_data/search_hybrid.json` | 10 Điều, thang rrf |
| `sample_data/search_compare.json` | 10+10 Điều, 6 ID chung có thứ hạng khác |
| `sample_data/search_empty.json` | Kết quả rỗng |
| `sample_data/search_truncated.json` | Cảnh báo QUERY_TRUNCATED |
| `sample_data/error_empty_query.json` | Lỗi EMPTY_QUERY |
| `sample_data/error_invalid_filter.json` | Lỗi INVALID_FILTER |
| `sample_data/error_invalid_request.json` | Lỗi INVALID_REQUEST |
| `sample_data/error_model_not_ready.json` | Lỗi MODEL_NOT_READY |
| `sample_data/error_index_manifest_mismatch.json` | Lỗi INDEX_MANIFEST_MISMATCH |
| `sample_data/error_feedback.json` | Lỗi feedback mẫu |
| `sample_data/error_search_expired.json` | Lỗi feedback hết hạn mẫu |
| `../../requirements-ui.txt` (từ gốc repo: `requirements-ui.txt`) | 3 dependency UI ghim cứng |
| `.streamlit/config.toml` (từ gốc repo) | Toolbar viewer và theme light mặc định |
| `data/FROZEN.md` (từ gốc repo) | Mốc 12, commit riêng `3d92837` |

`data/FROZEN.md` ghi SHA-256 trên blob LF của `openapi.json`:
`69f087ec963c74a16280d13882c13386e62b156dfdd675c322b6679c887b2e8c`.
Trước khi viết UI: `python -m pytest tests/test_api_contract.py` đạt
**35 passed**. Lần chạy trong sandbox treo tại socketpair của Windows; chạy
lại cùng bộ test ngoài sandbox đạt. Không sửa test/API/hợp đồng để làm pass.

## Test cần viết khi nối API

1. Luật import (SPEC 14.7 #3): quét AST toàn `src/ui/`, cấm import
   retrieval/service/api/data/querygen; dependency/image UI không có torch.
2. Highlight: tiếng Việt NFC/NFD, code point, span nửa mở, nhiều span, span
   chạm biên cửa sổ, không highlight, câu dài; escape `<`, `>`, `&`, dấu nháy
   và chuỗi giống HTML/script. Đối chiếu span sau cắt, dấu ba chấm và xuống dòng.
3. Compare: rỗng, trùng một phần/toàn bộ, khác thứ hạng, không có hạng bên kia;
   chỉ đối chiếu article_id và không so điểm khác thang.
4. Map đủ ErrorCode/WarningCode; lỗi kết nối/timeout, JSON sai schema, mã lạ;
   không hiển thị message thô hoặc traceback. INVALID_FILTER phải gọi lại info;
   model/manifest phải khóa tìm. Feedback 422 và lỗi export chỉ hiện toast.
5. Auto re-search: đổi mode, top-k, từng nhóm filter, bỏ chip, xóa lọc; giữ
   nguyên câu hỏi đã submit, không dùng bản đang gõ; thay hoàn toàn kết quả cũ,
   đóng reader, không tìm lặp vô hạn khi refresh info hoặc chọn lại mode.
6. HTTP request đúng schema; query giữ nguyên; không có year_min/year_max kể
   cả null; options/limits/modes lấy từ info. Info chỉ tải một lần trừ refresh.
7. Reader giữ đúng highlights/score/system từ bên được bấm, feedback theo
   `(search_id, system, article_id)`, đổi nhãn và xuất CSV UTF-8 BOM.
