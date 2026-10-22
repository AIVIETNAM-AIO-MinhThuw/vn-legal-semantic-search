# EDA summary (phiên 1)

Dataset `th1nhng0/vietnamese-legal-documents` @ `8977887f17be2defae4c5171d55562e1cde7d695`. Chưa lọc, chưa parse. Mọi giá trị là giá trị gốc trong metadata.

## Metadata

- Số văn bản: 171,556; `id` duy nhất: True; `id` null: 0

### Theo loại văn bản (`loai_van_ban`)

| loai_van_ban | n_docs |
|---|---|
| Quyết định | 91183 |
| Nghị quyết | 28337 |
| Thông tư | 17232 |
| Bản dịch văn bản | 10952 |
| Chỉ thị | 8543 |
| Nghị định | 5328 |
| Thông tư liên tịch | 3519 |
| Văn bản hợp nhất | 2232 |
| Sắc lệnh | 981 |
| Văn bản hệ thống hóa | 762 |
| Công văn | 732 |
| Luật | 610 |
| Lệnh | 379 |
| Văn bản hành chính liên quan | 281 |
| Pháp lệnh | 248 |
| Văn bản liên quan | 43 |
| Chương trình | 42 |
| Nghị quyết liên tịch | 34 |
| Hiệp định | 24 |
| Bộ luật | 17 |
| Văn bản khác | 16 |
| Công ước | 16 |
| Thông báo | 11 |
| Chưa xác định | 9 |
| Thông tư liên bộ | 7 |
| Hiến pháp | 6 |
| Nghị định thư | 4 |
| Sắc luật | 4 |
| Bản ghi nhớ | 2 |
| Quy định | 1 |
| Thỏa thuận | 1 |

### Theo tình trạng hiệu lực (`tinh_trang_hieu_luc`)

| tinh_trang_hieu_luc | n_docs |
|---|---|
| Hết hiệu lực toàn bộ | 90721 |
| Còn hiệu lực | 71619 |
| Hết hiệu lực một phần | 5235 |
| Chưa xác định | 3205 |
| Ngưng hiệu lực | 373 |
| Không còn phù hợp | 255 |
| Chưa có hiệu lực | 146 |
| Ngưng hiệu lực một phần | 2 |

### Theo lĩnh vực (`linh_vuc`), toàn bộ

- Số giá trị gốc khác nhau: 2,159 (file `domain_counts_all.csv`).
- Giá trị chứa dấu `,`: 1,633 giá trị; chứa `;`: 90 giá trị.
- Cột `nganh` (ngành): 1,166 giá trị gốc (file `nganh_counts_all.csv`).

Top 30:

| linh_vuc | n_docs |
|---|---|
| Chưa phân loại | 113772 |
| <NULL> | 4785 |
| Đất đai | 2916 |
| Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước | 2390 |
| Quản lý thuế, phí và lệ phí | 1742 |
| Lĩnh vực giá | 1656 |
| Lao động, tiền lương, tiền công | 1479 |
| Tổ chức- Biên chế | 1302 |
| Ngân sách nhà nước | 1289 |
| Quản lý ngân sách | 1228 |
| Quản lý ngân sách nhà nước | 1085 |
| Chính quyền địa phương | 880 |
| Đường bộ | 874 |
| Công chức, viên chức | 737 |
| Tài chính khác | 668 |
| Lâm nghiệp | 643 |
| Thi đua, khen thưởng | 620 |
| Môi trường | 542 |
| Nông nghiệp | 495 |
| Chính sách thuế | 474 |
| Thủy lợi | 470 |
| Cải cách hành chính | 442 |
| Xây dựng | 413 |
| Tổ chức cán bộ | 401 |
| An ninh và trật tự, an toàn xã hội | 386 |
| Tài nguyên khoáng sản, địa chất | 373 |
| Bảo trợ xã hội | 363 |
| Phát triển nông thôn | 347 |
| Kiểm tra, rà soát, hệ thống hóa, hợp nhất văn bản quy phạm pháp luật, pháp điển hệ thống quy phạm pháp luật | 344 |
| Đầu tư tại Việt Nam | 336 |

### Theo năm ban hành

- `ngay_ban_hanh` không parse được theo `dd/mm/yyyy` (hoặc null): 98
- Khoảng năm: 1925–2026 (file `year_counts.csv`)

## Nội dung HTML

- Số dòng content: 170,824; id trùng trong content: 0; id content không có trong metadata: 0
- `missing_row`: metadata không có dòng content; `null`/`empty_string`: HTML null/rỗng; `empty_text`: HTML có tag nhưng bóc tag ra không còn chữ.

| scope | content_state | n_docs | pct |
|---|---|---|---|
| all | ok | 158774 | 92.549 |
| all | empty_text | 12050 | 7.024 |
| all | missing_row | 732 | 0.427 |
| core_effective | ok | 10147 | 98.371 |
| core_effective | empty_text | 150 | 1.454 |
| core_effective | missing_row | 18 | 0.175 |

## Tập mô tả: Luật / Nghị định / Thông tư, `Còn hiệu lực`

Chỉ để mô tả, **không phải bộ lọc đã chốt**. Loại văn bản đúng chuỗi ['Luật', 'Nghị định', 'Thông tư'], `tinh_trang_hieu_luc == 'Còn hiệu lực'`. Số văn bản: 10,315.

Ước lượng số Điều: `est_articles_line_start` = số dòng bắt đầu bằng `Điều <số>` sau khi bóc tag (gần với số Điều thật hơn); `est_articles_any_mention` = mọi lần xuất hiện `Điều <số>` (gồm cả viện dẫn, chắc chắn đếm dư). Cả hai chỉ là ước lượng.

### Theo loại

| loai_van_ban | n_docs | n_with_text | est_articles_line_start | docs_zero_article_line_start |
|---|---|---|---|---|
| Luật | 179 | 173 | 8037.0 | 4 |
| Nghị định | 2212 | 2191 | 34857.0 | 23 |
| Thông tư | 7924 | 7783 | 59492.0 | 2334 |

### Theo lĩnh vực (giá trị gốc)

- Số giá trị `linh_vuc` gốc trong tập này: 669 (đầy đủ ở `domain_counts_core_effective.csv`).

Top 40 theo số văn bản:

| linh_vuc | n_docs | n_luat | n_nghi_dinh | n_thong_tu | n_with_text | est_articles_line_start | is_multi_value_candidate |
|---|---|---|---|---|---|---|---|
| Chưa phân loại | 5125 | 80 | 1428 | 3617 | 5056 | 42214 | False |
| <NULL> | 354 | 29 | 138 | 187 | 319 | 4627 | False |
| Quản lý ngân sách | 309 | 0 | 0 | 309 | 298 | 1381 | False |
| Quản lý thuế, phí và lệ phí | 234 | 0 | 0 | 234 | 225 | 868 | True |
| Lao động, tiền lương, tiền công | 168 | 1 | 27 | 140 | 168 | 2419 | True |
| Chính sách thuế | 100 | 0 | 13 | 87 | 100 | 301 | False |
| Ngân sách nhà nước | 92 | 0 | 16 | 76 | 90 | 1032 | False |
| Tài chính hành chính sự nghiệp | 84 | 0 | 0 | 84 | 83 | 326 | False |
| TCNH và thị trường TC, trái phiếu, khác | 77 | 0 | 0 | 77 | 75 | 767 | True |
| Quản lý dịch vụ tài chính và các quỹ tài chính | 69 | 0 | 0 | 69 | 66 | 528 | False |
| Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước | 69 | 1 | 13 | 55 | 68 | 380 | True |
| Hàng hải | 67 | 0 | 10 | 57 | 65 | 710 | False |
| Quản lý tài chính doanh nghiệp | 64 | 0 | 0 | 64 | 63 | 418 | False |
| An ninh quốc gia | 63 | 0 | 14 | 49 | 63 | 1578 | False |
| Tài chính khác | 58 | 0 | 2 | 56 | 55 | 178 | False |
| Thanh tra | 55 | 2 | 9 | 44 | 55 | 999 | False |
| Tổ chức cán bộ | 47 | 0 | 2 | 45 | 47 | 456 | False |
| Xuất nhập khẩu | 44 | 0 | 5 | 39 | 44 | 441 | False |
| Đường bộ | 42 | 1 | 6 | 35 | 37 | 738 | False |
| An toàn lao động | 39 | 0 | 1 | 38 | 39 | 278 | False |
| Hoạt động khoa học và công nghệ | 38 | 0 | 8 | 30 | 38 | 833 | False |
| Đo đạc và bản đồ | 38 | 0 | 1 | 37 | 38 | 260 | False |
| Lĩnh vực giá | 35 | 1 | 2 | 32 | 35 | 358 | False |
| Tài chính doanh nghiệp | 35 | 0 | 4 | 31 | 35 | 339 | False |
| Tài chính đối ngoại | 35 | 0 | 0 | 35 | 35 | 263 | False |
| Chính sách tiền tệ | 34 | 0 | 0 | 34 | 34 | 299 | False |
| Môi trường | 33 | 0 | 2 | 31 | 33 | 412 | False |
| Quản lý Khám, chữa bệnh | 33 | 1 | 0 | 32 | 33 | 427 | True |
| Hàng không | 32 | 1 | 7 | 24 | 32 | 470 | False |
| Quản lý ngoại hối | 32 | 0 | 3 | 29 | 32 | 416 | False |
| Công chức, viên chức | 31 | 0 | 6 | 25 | 31 | 258 | True |
| Diêm nghiệp | 31 | 0 | 2 | 29 | 31 | 304 | False |
| Chính quyền địa phương | 30 | 1 | 21 | 8 | 29 | 310 | False |
| Quản lý ngân sách; Tài chính khác | 30 | 0 | 0 | 30 | 28 | 24 | False |
| Đường sắt | 30 | 0 | 7 | 23 | 28 | 489 | False |
| Giáo dục | 29 | 1 | 6 | 22 | 29 | 441 | False |
| Quản lý dược | 29 | 0 | 1 | 28 | 29 | 346 | False |
| An toàn, vệ sinh lao động | 28 | 0 | 0 | 28 | 28 | 151 | True |
| Khác | 28 | 1 | 6 | 21 | 28 | 359 | False |
| Thú y | 28 | 0 | 1 | 27 | 28 | 277 | False |

### Phân phối độ dài (ký tự, văn bản có nội dung)

`text_chars` = độ dài sau khi bóc tag thô và gộp khoảng trắng.

| quantile | html_chars | text_chars |
|---|---|---|
| p0 | 373 | 18 |
| p5 | 5384 | 1474 |
| p25 | 10248 | 3824 |
| p50 | 22289 | 9656 |
| p75 | 51228 | 21118 |
| p95 | 213213 | 73560 |
| p99 | 668420 | 172121 |
| p100 | 12756339 | 2627048 |

| loai_van_ban | text_chars_p50 | text_chars_p95 |
|---|---|---|
| Luật | 49157 | 163324 |
| Nghị định | 9619 | 114162 |
| Thông tư | 9445 | 60618 |

## Relationships

- Số cạnh: 1,033,255; số loại quan hệ gốc: 31
- Cạnh có cả hai đầu ánh xạ về metadata `id`: 990,127 (95.83%); chỉ đầu `doc_id`: 100.00%; chỉ đầu `other_doc_id`: 95.83%
- Self-loop: 259; cạnh trùng (cùng 3 cột): 0; ID null: 0

**Toàn bộ** loại quan hệ gốc (chưa ánh xạ — nhóm xác nhận theo OI-10):

| relationship | n_edges | n_src_mapped | n_dst_mapped | n_both_mapped | pct_both_mapped |
|---|---|---|---|---|---|
| Căn cứ | 668173 | 668173 | 667285 | 667285 | 99.87 |
| Dẫn chiếu | 72554 | 72554 | 72370 | 72370 | 99.75 |
| Văn bản quy định hết hiệu lực | 50939 | 50939 | 50890 | 50890 | 99.9 |
| Quy định chi tiết, hướng dẫn thi hành | 39419 | 39419 | 39308 | 39308 | 99.72 |
| Thay thế | 37146 | 37146 | 37068 | 37068 | 99.79 |
| Văn bản HD, QĐ chi tiết | 34392 | 34392 | 34342 | 34342 | 99.85 |
| Bãi bỏ | 32479 | 32479 | 32386 | 32386 | 99.71 |
| Văn bản căn cứ | 26515 | 26515 | 1306 | 1306 | 4.93 |
| Sửa đổi, bổ sung | 17674 | 17674 | 17645 | 17645 | 99.84 |
| Văn bản bổ sung | 12853 | 12853 | 12841 | 12841 | 99.91 |
| Văn bản hết hiệu lực | 12247 | 12247 | 3852 | 3852 | 31.45 |
| Văn bản sửa đổi | 7466 | 7466 | 7462 | 7462 | 99.95 |
| Văn bản quy định hết hiệu lực 1 phần | 6100 | 6100 | 6089 | 6089 | 99.82 |
| Văn bản dẫn chiếu | 5715 | 5715 | 198 | 198 | 3.46 |
| Hợp nhất | 3930 | 3930 | 3926 | 3926 | 99.9 |
| Văn bản được HD, QĐ chi tiết | 1388 | 1388 | 251 | 251 | 18.08 |
| Hướng dẫn áp dụng | 1333 | 1333 | 1332 | 1332 | 99.92 |
| Văn bản bị hết hiệu lực 1 phần | 1127 | 1127 | 525 | 525 | 46.58 |
| Văn bản được bổ sung | 532 | 532 | 39 | 39 | 7.33 |
| Văn bản liên quan khác | 387 | 387 | 301 | 301 | 77.78 |
| Văn bản được sửa đổi | 284 | 284 | 118 | 118 | 41.55 |
| Đính chính | 209 | 209 | 209 | 209 | 100.0 |
| Tạm ngưng hiệu lực | 128 | 128 | 128 | 128 | 100.0 |
| Giải thích | 98 | 98 | 98 | 98 | 100.0 |
| Đình chỉ thi hành | 72 | 72 | 72 | 72 | 100.0 |
| Bản dịch | 55 | 55 | 54 | 54 | 98.18 |
| Văn bản đình chỉ 1 phần | 21 | 21 | 18 | 18 | 85.71 |
| Văn bản đình chỉ | 16 | 16 | 13 | 13 | 81.25 |
| Công bố | 1 | 1 | 1 | 1 | 100.0 |
| Văn bản bị đình chỉ | 1 | 1 | 0 | 0 | 0.0 |
| Văn bản bị đình chỉ 1 phần | 1 | 1 | 0 | 0 | 0.0 |

## Mẫu HTML

10 văn bản ngẫu nhiên (seed 42) từ tập mô tả, xoay vòng Luật/Nghị định/Thông tư. Lưu nguyên HTML thô tại `samples/`, chỉ mục `samples/samples_index.csv`.

| file | loai_van_ban | so_ky_hieu |
|---|---|---|
| 01_luat_8611.html | Luật | Không số |
| 02_nghi_dinh_144098.html | Nghị định | 110/2020/NĐ-CP |
| 03_thong_tu_107543.html | Thông tư | 46/1998/TT/BTC |
| 04_luat_173332.html | Luật | 61/2024/QH15 |
| 05_nghi_dinh_183905.html | Nghị định | 304/2025/NĐ-CP |
| 06_thong_tu_139959.html | Thông tư | 87/2019/TT-BTC |
| 07_luat_142843.html | Luật | 62/2020/QH14 |
| 08_nghi_dinh_141685.html | Nghị định | 40/2020/NĐ-CP |
| 09_thong_tu_27128.html | Thông tư | 152/2011/TT-BTC |
| 10_luat_25701.html | Luật | 49/2010/QH12 |
