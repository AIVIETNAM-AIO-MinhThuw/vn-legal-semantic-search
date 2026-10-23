# Hướng dẫn đối chiếu ba bảng cảnh báo (đọc trước)

Tạo bởi `scripts/build_review_tables.py` từ output hiện tại. **Script chuẩn bị tự động bằng chứng và đề xuất; không phải người đã xem.**
**Trạng thái xác nhận:** A: 16/16, B: 6/6, C: 25/25. Người duyệt: Minh Thư; ngày: 2026-10-24; kết quả: Đã xác nhận. Nhập theo xác nhận của người duyệt. Xem `confirmation.json`.

## 0. Tệp được commit và cách sinh lại

Thư mục `reports/data_stats/after_filter/review/` chỉ gồm: `README.md`, `confirmation.json` và ba bảng mức văn bản `table_A_unclosed_open_quote.csv`, `table_B_after_signature.csv`, `table_C_stray_closing_quote.csv` (đã được người duyệt). Bảng C là bảng mức văn bản, không chứa chi tiết từng vị trí.
Bảng chi tiết (từng vị trí/đoạn), bản Markdown và bảng phụ trợ không commit; sinh lại vào `.scratch/task_1_review/` bằng:

```bash
python -X utf8 scripts/build_review_tables.py --config configs/data.yaml
```

Script chỉ đọc `confirmation.json`. Với `--publish`, script ghi lại README này và chỉ ghi CSV A/B/C nào còn thiếu; không ghi đè CSV đã duyệt hay `confirmation.json`.

## 1. Ba nhóm (xác định lại từ output, parse lại HTML gốc của 706 văn bản trong index)

| Nhóm | Điều kiện | Số văn bản | Bảng |
|---|---|---|---|
| A | có “ chưa đóng (parser **không** dùng ngữ cảnh đoạn trích) | 16 | `table_A_unclosed_open_quote.csv` |
| B | có Điều/phần sau chữ ký (`after_signature`) | 6 | `table_B_after_signature.csv` |
| C | có ” thừa (parser vẫn dùng ngữ cảnh đoạn trích) | 25 | `table_C_stray_closing_quote.csv` (853 vị trí) |

Giao nhau: A∩B = 0, A∩C = 3 (`110990`, `153630`, `185676`), B∩C = 0, A∩B∩C = 0.
Tổng ba nhóm = 47, **số văn bản duy nhất = 44** (không cộng trùng).
Lưu ý: số nhóm C là 25, khác con số 14 trong báo cáo trước; 14 được suy ra từ `parse_anomalies.jsonl`, chỉ ghi văn bản có thêm cờ khác, nên bỏ sót văn bản chỉ có ” thừa. `prepare_data.py` nay ghi cả cờ này. Nhóm ngoặc thẳng (12 văn bản) không nằm trong ba bảng.

## 2. Quy ước số dòng và cách mở nguồn

- Số dòng = dòng **văn bản đã chuẩn hóa** do `html_to_lines` trả về (HTML → text, NFC, bảng thành `ô | ô`), đánh số từ **1**. Nhãn: `[Đn]` = Điều parser gán (`*` = sau chữ ký), `[đầu]` = trước Điều đầu tiên, `[chương]` = dòng Chương/Mục bị bỏ, `[ký]` = chữ ký/nơi nhận/lời dẫn sau chữ ký bị bỏ, `[cắt]` = phụ lục/biểu mẫu bị cắt; `▶` = tiêu đề Điều parser nhận.
- HTML gốc: `data/raw/data/content.parquet`, cột `id` = `doc_id`, cột `content_html`; bản trích để mở nhanh: `data/processed/review_cache/<doc_id>.html` (không commit).
- Xem dòng a–b kèm đoạn HTML gốc tương ứng:

```bash
python -X utf8 scripts/show_source.py --doc <doc_id> --lines 36-48 --html
```

- Liệt kê Điều parser nhận (số dòng, trạng thái) và xem nội dung Điều trong output:

```bash
python -X utf8 scripts/show_source.py --doc <doc_id> --articles
python -X utf8 scripts/show_source.py --doc <doc_id> --article-id <doc_id>_005
```

- Output parser: `data/processed/articles_index.jsonl` (sau loại trùng), `articles.jsonl` (trước loại trùng), `chunks_index.jsonl`; log loại bỏ: `logs/rejected.jsonl`; cờ: `logs/parse_anomalies.jsonl`. `article_id` = `<doc_id>_<thứ tự Điều parse, 3 chữ số>`.

## 3. Kết quả xác nhận

Mọi ca trong ba bảng ghi: người duyệt `Minh Thư`, ngày `2026-10-24`, kết quả `Đã xác nhận` — chỉ áp dụng cho phần đã đối chiếu (cột `compared_range`). Tổng kết: A: 16/16, B: 6/6, C: 25/25. Bản ghi nhập theo xác nhận của người duyệt. Mức bằng chứng tự động (cột `automated_evidence_level`) là phần chuẩn bị, không thay cho kết quả của người duyệt.

## 4. Ca cần chú ý (mức tự động khác "Đủ bằng chứng")

- Bảng A (9/16):
  - `110872` — Thông tư số 199/2014/TT-BTC Hướng dẫn kế toán áp dụng đối với doanh n… — **Cần người xem** — nhóm A
  - `150886` — Thông tư số 05/2021/TT-BTC Sửa đổi, bổ sung một số điều của Thông tư … — **Cần người xem** — nhóm A
  - `151088` — Thông tư số 83/2021/TT-BTC Hướng dẫn quản lý kinh phí tập huấn, bồi d… — **Cần người xem** — nhóm A
  - `153630` — Nghị định số 124/2021/NĐ-CP sửa đổi, bổ sung một số điều của Nghị địn… — **Cần người xem** — nhóm A+C
  - `156230` — Thông tư số 58/2022/TT-BTC Quy định nội dung và mức chi thực hiện một… — **Cần người xem** — nhóm A
  - `185624` — Nghị định số 342/2025/NĐ-CP Quy định chi tiết một số điều của Luật Qu… — **Cần người xem** — nhóm A
  - `187157` — Nghị định số 49/2026/NĐ-CP Quy định chi tiết và hướng dẫn một số điều… — **Cần người xem** — nhóm A
  - `26067` — Thông tư số 217/2010/TT-BTC Sửa đổi Quyết định số 72/2008/QĐ-BTC ngày… — **Cần người xem** — nhóm A
  - `26323` — Thông tư số 31/2011/TT-BTC Sửa đổi, bổ sung Thông tư số 100/2002/TT-B… — **Cần người xem** — nhóm A
- Bảng B (0/6):
  - (không có)
- Bảng C (0/25):
  - (không có)

Toàn bộ 44 văn bản duy nhất: A: 16/16, B: 6/6, C: 25/25.

## 5. Quét vùng trích dẫn toàn cục

Trong 706 văn bản, parser dùng ngữ cảnh đoạn trích cho các văn bản có ngoặc cân bằng. Có 2 tiêu đề Điều nằm trong vùng trích dẫn (ở 1 văn bản); 0 tiêu đề có số bằng Điều top-level liền trước + 1 (nguy cơ Điều thật bị nuốt). Bảng chi tiết sinh lại local (mục 0).
