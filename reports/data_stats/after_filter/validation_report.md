# Báo cáo validation sau lọc / parse / chunk (ba bảng A/B/C đã xác nhận, chưa split)

Trạng thái: `prepare_data`, `validate_data` (0 lỗi), `family_stats` và test đạt. Phạm vi báo cáo: Task 1 (lọc, parse, chunk, dedup, validate, review corpus, thống kê họ). Split và leakage thuộc Task 2, không nằm trong báo cáo này. **Chưa chạy split, chưa tạo `splits.json`, chưa sinh query.**
Số máy sinh lấy từ `validate_report.json` và `family_stats.json`.
Mọi số sinh lại được bằng lệnh ở cuối file. Kiểm tra tự động là script đối chiếu HTML gốc với output; **không phải người đã xem tay**. Giới hạn đã biết ghi ở mục 5.

## 1. Kết quả và so sánh

| | v1 (phiên 2) | v5 (trước sửa OCR "Điểu") | v6 (hiện tại, sau sửa) |
|---|---|---|---|
| Văn bản trong index | 704 | 706 | 706 |
| Điều đã parse (trước dedup) | 7.511 | 7.456 | 7.457 |
| Điều trong index (sau dedup) | 7.386 | 7.339 | **7.340** |
| Chunk trong index | 14.387 | 14.280 | **14.281** |
| Nhóm trùng / Điều bị loại do trùng | 107 / 125 | 103 / 117 | 103 / 117 |
| Điều loại `form_template` | 0 | 24 | 24 |
| Điều gắn cờ `form_uncertain` (giữ tạm) | – | – | 0 |
| Điều trong phần phụ lục / biểu mẫu bị cắt (đã log) | không log | 102 | 102 |
| Họ có ≥ 1 văn bản trong corpus | – | 569 | 569 |

Thay đổi v5 → v6: chỉ văn bản `135753` (24 Điều thay vì 23; 41 chunk thay vì 40). Nguồn có dòng `Điểu 1. Phạm vi điều chỉnh và đối tượng áp dụng` (lỗi OCR `Điểu` thay `Điều`) nên Điều 1 bị mất; parser nay nhận từ đầu dòng đã bỏ dấu là "dieu" (gồm `Ðiều`) khi có số + dấu chấm/hai chấm/gạch và số đúng bằng số Điều kế tiếp. Quét toàn bộ văn bản: chỉ 1 dòng khớp trong cả corpus. Số nhóm trùng/Điều bị loại do trùng và số họ (569) không đổi.

Lần chạy này không đổi số liệu corpus: sửa rule biểu mẫu (mục 2) không khôi phục Điều nào và không loại thêm Điều nào. Chunk: min/median/p95/max = 37/307/441,8/450 token (tính lại độc lập bằng tokenizer E5); không chunk nào > 450; mọi passage ≤ 512 sau khi gắn `passage: `.

## 2. Rule loại biểu mẫu sau chữ ký (đã siết)

Trước đây một dấu `...` hoặc `…` bất kỳ trong đoạn đính kèm sau chữ ký có thể làm cả đoạn quy chế bị loại. Nay chỉ loại khi có bằng chứng rõ ràng, tính trên từng đoạn đính kèm (một đoạn bắt đầu khi số Điều quay lại từ đầu):

- **Loại (`form_template`)** khi có lời dẫn của quyết định mẫu (dòng `QUYẾT ĐỊNH`, `Căn cứ…` hoặc `Theo đề nghị…` ngay trước đoạn) **và** (có ít nhất một dòng có chỗ trống dài `……` / `......` **hoặc** ít nhất 2 dòng ba chấm thông thường kèm ô `(tên …)`, `(số …)`, `(nếu có)`).
- **Giữ và gắn cờ `form_uncertain`** khi chỉ có dấu ba chấm thông thường, hoặc có lời dẫn nhưng bằng chứng chưa đủ; người xác nhận sau.
- Dòng lời dẫn của mẫu kế tiếp rò vào cuối Điều đứng trước được tách ra khỏi bằng chứng của đoạn trước.

Test mới: quy chế sau chữ ký có `...` thông thường vẫn được giữ; lời dẫn kèm một dấu ba chấm không đủ để loại; quy chế có `Căn cứ` ở lời dẫn và `...` thông thường vẫn được giữ; ghi nhận bằng chứng cho mẫu bị loại.

Kiểm tra lại Điều đã bị loại: 24 Điều `form_template` trước và sau giống hệt nhau, **0 Điều được khôi phục**, 0 Điều bị loại thêm. Bằng chứng từng đoạn (từ `rejected.jsonl`, trường `evidence`):

| Văn bản | Đoạn | Lời dẫn | Dòng chỗ trống dài | Kết luận |
|---|---|---|---|---|
| `187280` | 7 đoạn mẫu quyết định | có | 4–18 | Loại |
| `0da53250…` | 2 đoạn mẫu phê duyệt | có | 1 và 0 (5 dòng ba chấm + 4 ô `(tên …)`) | Loại |
| `174190`, `185170`, `184824`, `7920add0…` | quy chuẩn / quy chế kèm theo | không | 0 | Giữ; không có dấu ba chấm nào |

Mọi Điều bị loại đều có dòng log lý do trong `logs/rejected.jsonl` (`form_template` có bằng chứng; `appendix_or_form_cut` ghi số Điều, tiêu đề, dòng bắt đầu cắt và dấu hiệu cắt).

## 3. Bộ bằng chứng review (ba bảng, thư mục `review/`)

Danh sách xác định lại từ output hiện tại bằng cách parse lại HTML gốc của mọi văn bản trong index (`scripts/build_review_tables.py`); không đọc từ log. Hướng dẫn mở nguồn/output và cách điền kết quả: `review/README.md`; công cụ xem nguồn: `scripts/show_source.py`.

| Nhóm | Điều kiện | Số văn bản | Bảng |
|---|---|---|---|
| A | “ chưa đóng (parser không dùng ngữ cảnh đoạn trích) | 16 | `table_A_unclosed_open_quote.csv` |
| B | có phần `after_signature` | 6 | `table_B_after_signature.csv` |
| C | ” thừa (parser vẫn dùng ngữ cảnh đoạn trích) | 25 (853 vị trí) | `table_C_stray_closing_quote.csv` |

Commit gồm `review/README.md`, `review/confirmation.json` và ba bảng mức văn bản trên; bảng C là bảng mức văn bản, không chứa chi tiết đầy đủ 853 vị trí. Bảng chi tiết từng vị trí/đoạn, bản Markdown và bảng phụ trợ sinh lại local vào `.scratch/task_1_review/` bằng `scripts/build_review_tables.py`.

Giao nhau: A∩C = 3 (`110990`, `153630`, `185676`); A∩B = B∩C = 0. Tổng ba nhóm 47, **số văn bản duy nhất 44**. Nhóm C là 25, không phải 14 như báo cáo trước (14 suy ra từ `parse_anomalies.jsonl`, bỏ sót văn bản chỉ có ” thừa).

Mỗi ca có: nguồn HTML và output parser, số dòng (dòng văn bản chuẩn hóa, đánh số từ 1), phần đã đối chiếu, ngữ cảnh quanh dấu ngoặc / ranh giới Điều / ranh giới chữ ký (nhãn `[Đn]` là Điều parser gán), nhận xét và đề xuất tự động, mức bằng chứng, và các cột người duyệt (tên, ngày, kết quả, ghi chú). Trạng thái hiện tại: Minh Thư, 2026-10-24, "Đã xác nhận" (A: 16/16, B: 6/6, C: 25/25), nhập theo xác nhận của người duyệt (`review/confirmation.json`). Với nhóm C, bảng chi tiết local liệt kê từng vị trí ” thừa kèm Điều parser đang gán. Với nhóm B, cả đoạn được giữ lẫn đoạn bị loại đều có bằng chứng.

Mức bằng chứng tự động (không phải kết luận của người): A: 7 "Đủ bằng chứng tự động", 9 "Cần người xem"; B: 6/6 "Đủ bằng chứng tự động"; C: 25/25 "Đủ bằng chứng tự động" (không có vùng trích dẫn chứa tiêu đề Điều). Số Điều liên tục không được dùng riêng để kết luận. Quét vùng trích dẫn toàn cục: 2 tiêu đề Điều nằm trong vùng trích (1 văn bản), 0 tiêu đề có nguy cơ là Điều thật bị nuốt (bảng quét toàn cục sinh lại local bằng `build_review_tables.py`).

## 4. Số Điều lặp, phần đính kèm, ngoặc

- 13 văn bản có số Điều lặp (59 lần). Quyết định: giữ, gắn cờ `has_duplicate_article_numbers`, `article_id` duy nhất; nhãn hiển thị `Điều <số> — <tiêu đề>` (thêm `[article_id]` khi vẫn trùng) ở `duplicate_article_numbers.csv`.
- `after_signature`: 102 Điều ở 4 văn bản được giữ (quy chế / quy chuẩn kèm theo). 24 Điều ở 2 văn bản bị loại như biểu mẫu. Cả 6 văn bản đã được xác nhận trong bảng B.
- Ngoặc bất thường (không cộng trùng): `“` chưa đóng 25 văn bản (16 trong index), `”` thừa 27 (25), `"Điều N` 18 (12).

## 5. Giới hạn chưa kiểm tra hoặc đã biết

1. 25 văn bản trong index có `”` thừa (853 vị trí); đã xác nhận ở mức văn bản (bảng C). Phần lớn là dấu `”` không có dấu mở tương ứng (ngoặc đơn kép `‘‘`, định dạng lẫn lộn), không tạo vùng trích dẫn.
2. Ngoặc thẳng `"` không ghép mở / đóng được; script đã kiểm tra tự động cả 12 văn bản nhưng chưa có người xác nhận.
3. Biểu mẫu sau chữ ký không có lời dẫn quyết định hoặc chỗ trống rõ ràng không bị loại (chỉ có thể gắn `form_uncertain` nếu có ba chấm). Biểu mẫu trước chữ ký chỉ bị cắt khi có dấu hiệu `Mẫu số`, `PHỤ LỤC`, `BIỂU MẪU`.
4. Phần đính kèm không có "Nơi nhận" / `PHỤ LỤC` ở giữa (như `185179`) không gắn cờ `after_signature`; chỉ có cờ số Điều lặp.
5. Ô gộp (`colspan`, `rowspan`) không được xử lý khi chuyển bảng thành dòng.
6. Dấu hiệu cuối văn bản dựa vào mẫu chữ (Nơi nhận, TM., KT., chức danh viết hoa ở 8 dòng cuối); cách ghi khác có thể sót vào thân Điều cuối.
7. Quy tắc nhận diện Điều/chương/chữ ký là heuristic kỹ thuật, chưa đối chiếu với phân tích Điều thủ công trên mẫu ngẫu nhiên.
8. 424 Thông tư (37% của 1.133) không có tiêu đề `Điều N` nên bị loại theo SPEC 3.2 bước 4. Corpus chỉ có 1 Luật, 56 Nghị định, 649 Thông tư.
9. Dedup băm thân Điều (không gồm tiêu đề); 97 trong 103 nhóm trùng ở các văn bản khác nhau; 1 văn bản mất hết Điều nên không vào index.
10. Test: xem kết quả `pytest` của lần chạy cuối trước commit.

Số lỗi `validate_data`: 0. Cờ/cảnh báo: ngoặc: 44 văn bản duy nhất trong ba nhóm A/B/C (B là after_signature), số Điều lặp 13, `after_signature` 6 văn bản (4 giữ phần đính kèm, 2 loại phần mẫu), `form_uncertain` 0, `no_article` 424.

## 6. Họ văn bản (chỉ thống kê, chưa split)

Union-find trên toàn bộ `relationships` với 6 nhãn đã chốt (75.955 cạnh), ID thiếu metadata là nút trung gian (714 nút). Nguồn: `family_stats.json`, `family_sizes.csv`, `family_bridge_report.json`.

| | |
|---|---|
| Họ có ≥ 1 văn bản trong corpus | 569 |
| Văn bản / Điều trong index | 706 / 7.340 |
| Văn bản mỗi họ (min / median / p95 / max) | 1 / 1 / 2 / 94 |
| Điều mỗi họ (min / median / p95 / max) | 1 / 7 / 30,6 / 1.127 |
| Họ lớn nhất | 94 văn bản (13,31%), 1.127 Điều (15,35%), có `135753`; 5.227 nút kể cả ngoài corpus; lĩnh vực chủ đạo "Lao động, tiền lương, tiền công" |
| Họ lớn thứ hai | 150 Điều (2,04%) |
| Họ chỉ có 1 văn bản / có > 1 văn bản | 536 / 33 |
| Họ hòa lĩnh vực chủ đạo | 5 |
| Họ có nút thiếu metadata | 6 |

Số họ theo lĩnh vực chủ đạo: `dominant_domain_family_counts` trong `family_stats.json`. Đường nối qua ID thiếu metadata của họ lớn nhất: 33 nút ID thiếu; bỏ riêng các nút này (chỉ để đo, không cắt cạnh) thì cả 94 văn bản trong corpus vẫn thuộc một thành phần liên thông và không văn bản nào kề trực tiếp nút thiếu (`family_bridge_report.json`).

## 7. Việc còn lại sau Task 1

1. Chấp nhận hoặc xử lý giới hạn mục 5.
2. Split và kiểm tra leakage do Task 2 thực hiện trên corpus này.

## Tái lập

```bash
python -X utf8 scripts/prepare_data.py --config configs/data.yaml
python -X utf8 scripts/validate_data.py --config configs/data.yaml
python -X utf8 scripts/family_stats.py --config configs/data.yaml
python -X utf8 scripts/build_review_tables.py --config configs/data.yaml
python -m pytest -q
```

`logs/filtered_out.tsv` (từng văn bản bị loại ở bước lọc 1–3, ~10 MB) được `.gitignore` bỏ qua, giữ local và được tạo lại bởi `prepare_data.py`. Bảng đếm tổng hợp có thể commit: `filter_steps.csv`, `filtered_out_summary.csv`.
