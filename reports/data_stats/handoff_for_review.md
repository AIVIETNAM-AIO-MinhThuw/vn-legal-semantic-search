# Bàn giao review EDA — OI-10 (cập nhật sau khi EDA hoàn tất)

## 1. Kết luận kiểm tra

Đối chiếu mã/config và thống kê; không đọc HTML thô, không chạy lại EDA. Bản này thay các kết luận thiếu file ở bản trước, được tạo khi EDA chưa hoàn tất.

| Hạng mục | Kết luận — giải thích |
|---|---|
| Script chỉ thống kê | **Đạt** — Tập con mô tả, bỏ tag/entity/NFC và regex chỉ phục vụ đo đếm; không lọc corpus, parse cấu trúc Điều, chunk hay split. |
| Seed / dữ liệu gốc | **Đạt** — Seed `42`; mã chỉ đọc parquet, chỉ ghi báo cáo và mẫu vào `reports/data_stats/`. Không kiểm chứng lịch sử ghi ngoài mã. |
| Config | **Đạt** — Revision `8977887f17be2defae4c5171d55562e1cde7d695` khớp schema; bốn trường OI-10 (`doc_types`, `effective_statuses`, `domains`, `mapping`) vẫn null. |
| `.gitignore` | **Không đạt** đầy đủ — Loại `data/raw/`, parquet/arrow, model/index và đuôi file lớn; chưa loại bản sao HTML thô ở `reports/data_stats/samples/*.html`. |
| Tổng metadata | **Đạt** — Theo loại, hiệu lực, lĩnh vực, năm và bảng chéo đều **171.556**, khớp schema; tổng hàng/cột bảng chéo khớp bảng riêng. |
| Null/thiếu | **Đạt** về ghi nhận — Lĩnh vực `<NULL>` **4.785**; loại/hiệu lực không có nhóm null/trắng. Năm `<unparsed>` **98**; **không kiểm tra được** riêng null và sai định dạng vì báo cáo gộp. |
| HTML rỗng/thiếu | **Đạt** — Toàn tập: 158.774 có chữ + 12.050 `empty_text` + 732 `missing_row` = 171.556; rỗng/thiếu **7,4506%**. Core: 10.147 + 150 + 18 = 10.315; **1,6287%**. Không có nhóm HTML null/chuỗi rỗng được ghi nhận. |
| Content so với schema | **Đạt** — 170.824 dòng = 158.774 + 12.050; summary ghi ID trùng/orphan = 0, nên 732 metadata thiếu content là nhất quán. |
| Relationships | **Đạt** về số — 31 loại cộng **1.033.255** cạnh, khớp schema; **990.127 (95,8260%)** ánh xạ cả hai đầu, **43.128 (4,1740%)** không ánh xạ đủ; tỷ lệ từng loại tính lại đều khớp. **Không đạt** về nhãn “chỉ đầu” trong summary (mục 2). |
| Giá trị gốc | **Đạt** về kiểm kê — 31 loại, 8 hiệu lực không thấy biến thể thuần hoa/thường/khoảng trắng/dấu tiếng Việt; lĩnh vực có 39 nhóm gần nhau dưới đây, chưa xác nhận cùng nghĩa. |
| Độ dài / số Điều | **Đạt** về nhất quán — Core **10.315** dòng, **669** lĩnh vực, tổng **102.386** Điều đầu dòng ước lượng; tổng theo lĩnh vực/loại khớp từng dòng thống kê. Có giá trị 0 và cực trị (mục 2); **không kiểm tra được** số Điều thật hoặc nguyên nhân nếu không parse/đọc HTML. |

## 2. Các bất thường và lỗi

- Lĩnh vực toàn tập: **2.159** giá trị; “Chưa phân loại” **113.772**, null **4.785**. Core: **5.125 + 354 = 5.479 (53,12%)** thuộc hai nhóm này.
- **1.633** chuỗi có dấu phẩy (16.327 văn bản), **90** có chấm phẩy (667 văn bản); có thể giao nhau. Dấu phẩy cũng thuộc tên đơn, nên không kết luận mọi chuỗi đều gộp; từng giá trị giữ nguyên ở `domain_counts_all.csv`.
- Ví dụ đảo thứ tự: “Quản lý ngân sách; Tài chính khác” (134) / “Tài chính khác; Quản lý ngân sách” (36); dấu phân cách cuối: “Viễn thông và Internet;” (152).
- Không thấy khoảng trắng đầu/cuối/liên tiếp hoặc cặp chỉ khác có dấu/không dấu. Các nhóm khác hoa/thường, dấu thanh hoặc dấu câu sau chỉ là đối chiếu hình thức; số trong ngoặc là văn bản toàn tập, không hợp nhất:
- “Tổ chức- Biên chế” (1302) / “tổ chức, biên chế” (2).
- “Thi đua, khen thưởng” (620) / “Thi đua - Khen thưởng” (4) / “Thi đua khen thưởng” (1) / “Thi đua - khen thưởng” (1).
- “Tổ chức cán bộ” (401) / “Tổ chức, cán bộ” (1) / “tổ chức cán bộ” (1).
- “Thể dục, thể thao” (285) / “Thể dục thể thao” (5).
- “Tiêu chuẩn đo lường chất lượng” (204) / “Tiêu chuẩn - Đo lường - Chất lượng” (2).
- “Khiếu nại, tố cáo” (144) / “Khiếu nại, Tố cáo” (1).
- “Cán bộ, công chức” (132) / “cán bộ, công chức” (4).
- “Kinh tế hợp tác và Phát triển nông thôn” (88) / “Kính tế hợp tác và Phát triển nông thôn” (2).
- “Lao động ngoài nước” (85) / “lao động ngoài nước” (3).
- “Kế hoạch - Tài chính” (55) / “Kế hoạch tài chính” (22) / “Kế hoạch, Tài chính” (3).
- “Giáo dục nghề nghiệp” (55) / “giáo dục nghề nghiệp” (2).
- “Tổ chức, bộ máy” (52) / “Tổ chức bộ máy” (4).
- “Khoa học công nghệ” (40) / “Khoa học - Công nghệ” (3).
- “Biển và hải đảo” (36) / “Biển và Hải đảo” (2).
- “Khoa học, công nghệ và môi trường” (31) / “Khoa học Công nghệ và Môi trường” (2).
- “Quy hoạch” (24) / “quy hoạch” (1).
- “Giáo dục chuyên nghiệp, Giáo dục thường xuyên” (14) / “Giáo dục chuyên nghiệp Giáo dục thường xuyên” (1).
- “Khám bệnh, chữa bệnh” (14) / “khám bệnh, chữa bệnh” (1).
- “Cán bộ, công chức, viên chức” (13) / “Cán bộ, công chức, Viên chức” (5) / “cán bộ, công chức Viên chức” (1).
- “Ngân sách nhà nước, Quản lý ngân sách nhà nước” (8) / “Ngân sách nhà nước Quản lý ngân sách nhà nước” (1).
- “Biên giới quốc gia” (8) / “Biên giới Quốc gia” (1).
- “Nông nghiệp, Thủy sản” (7) / “Nông nghiệp Thủy sản” (1).
- “Xây dựng nhà ở” (6) / “Xây dựng, Nhà ở” (2).
- “Công nghiệp nhẹ, Thị trường trong nước” (6) / “Công nghiệp nhẹ Thị trường trong nước” (1).
- “Chăn nuôi, thú y” (5) / “Chăn nuôi, Thú y” (4).
- “Xuất nhập khẩu, Chính sách thuế” (5) / “Xuất nhập khẩu Chính sách thuế” (1).
- “Công nghệ thông tin,điện tử, Viễn thông và Internet;” (5) / “Công nghệ thông tin,điện tử Viễn thông và Internet;” (1).
- “Chính sách thuế Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước” (3) / “Chính sách thuế, Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước” (2).
- “Công nghệ thông tin,điện tử, Tin học hóa” (3) / “Công nghệ thông tin,điện tử Tin học hóa” (1).
- “Quản lý chung Quản lý Khám, chữa bệnh” (2) / “Quản lý chung, Quản lý Khám, chữa bệnh” (1).
- “Hải quan Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước” (2) / “Hải quan, Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước” (1).
- “Đầu tư tại Việt Nam, Tín dụng” (2) / “Đầu tư tại Việt Nam Tín dụng” (1).
- “Công nghệ thông tin,điện tử Viễn thông” (1) / “Công nghệ thông tin,điện tử, Viễn thông” (1).
- “chuyển đổi số Công nghệ thông tin,điện tử” (1) / “Chuyển đổi số, Công nghệ thông tin,điện tử” (1).
- “Quản lý ngân sách nhà nước, Tài chính hành chính sự nghiệp” (1) / “Quản lý ngân sách nhà nước Tài chính hành chính sự nghiệp” (1).
- “Giáo dục đại học, Khảo thí và Kiểm định chất lượng” (1) / “Giáo dục đại học Khảo thí và Kiểm định chất lượng” (1).
- “Quản lý dược, Quản lý Khám, chữa bệnh” (1) / “Quản lý dược Quản lý Khám, chữa bệnh” (1).
- “Nông nghiệp Phát triển nông thôn Thủy sản” (1) / “Nông nghiệp, Phát triển nông thôn, Thủy sản” (1).
- “Khoa học và công nghệ Viễn thông và Internet;” (1) / “Khoa học và công nghệ, Viễn thông và Internet;” (1).
- Các tên gần nghĩa chưa đủ căn cứ coi là một: “Ngân sách nhà nước” (1.289), “Quản lý ngân sách” (1.228), “Quản lý ngân sách nhà nước” (1.085).
- Năm `<unparsed>` **98**; khoảng năm **1925–2026**; không có căn cứ xác nhận năm sai.
- **259 self-loop**, **0 cạnh trùng**, **0 ID null** theo summary; không kiểm tra độc lập các số này vì chỉ dùng thống kê.
- Lỗi diễn đạt summary: “chỉ đầu doc_id: 100% / chỉ đầu other_doc_id: 95,83%” thực tế là tỷ lệ từng đầu, gồm cả cạnh ánh xạ hai đầu; không phải nhóm độc quyền. Từ bảng: chỉ nguồn **43.128**, chỉ đích **0**. Chưa sửa mã/chạy lại vì phiên này chỉ cập nhật bàn giao, các số gốc vẫn đối chiếu được.
- Core có **2.361** ước lượng Điều đầu dòng bằng 0: **150** rỗng sau bỏ tag + **2.211** có chữ; **18** thiếu content là giá trị thiếu, không phải 0. Theo loại: Luật **4**, Nghị định **23**, Thông tư **2.334/7.924 (29,45%)** (bao gồm rỗng sau bỏ tag).
- Core có chữ: độ dài ký tự min/median/p95/max = **18 / 9.656 / 73.560 / 2.627.048**; max HTML **12.756.339** ký tự. ID `155207` dài 2.627.048 ký tự text nhưng chỉ 4 Điều đầu dòng ước lượng; chưa kết luận lỗi.
- Ước lượng Điều đầu dòng max **261** (ID `401e82e0-7cf1-11f1-962a-a92b40ea08f1`); mọi lần nhắc Điều max **1.442** (ID `152897`, đầu dòng 15). Tổng mọi lần nhắc **211.723** gồm viện dẫn, không coi là số Điều thật.
- Workspace không có `.git`: không kiểm tra được tracking/lịch sử Git; thiếu quy tắc ignore HTML mẫu như mục 1. Không thay đổi phạm vi loại văn bản, hiệu lực hoặc cột lĩnh vực.

## 3. Bảng lĩnh vực

Tập mô tả đúng chuỗi **Luật / Nghị định / Thông tư**, hiệu lực **“Còn hiệu lực”**; tương ứng **179 / 2.212 / 7.924** văn bản. Bảng rút gọn 12 dòng đầu theo số văn bản giảm dần, hòa theo tên; đủ **669** dòng tại [domain_counts_core_effective.csv](domain_counts_core_effective.csv). Đây là thứ tự số lượng, không phải danh sách đề xuất. Ước tính = regex “Điều <số>” ở đầu dòng sau bỏ tag; thiếu content không có ước tính, tổng nhóm bỏ qua giá trị thiếu.

| Lĩnh vực gốc | Văn bản | Điều ước tính |
|---|---:|---:|
| Chưa phân loại | 5.125 | 42.214 |
| <NULL> | 354 | 4.627 |
| Quản lý ngân sách | 309 | 1.381 |
| Quản lý thuế, phí và lệ phí | 234 | 868 |
| Lao động, tiền lương, tiền công | 168 | 2.419 |
| Chính sách thuế | 100 | 301 |
| Ngân sách nhà nước | 92 | 1.032 |
| Tài chính hành chính sự nghiệp | 84 | 326 |
| TCNH và thị trường TC, trái phiếu, khác | 77 | 767 |
| Quản lý dịch vụ tài chính và các quỹ tài chính | 69 | 528 |
| Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước | 69 | 380 |
| Hàng hải | 67 | 710 |
| **Tổng đủ 669 dòng** | **10.315** | **102.386** |

## 4. Bảng loại quan hệ

Đủ 31 nhãn gốc; tỷ lệ = cả hai ID có trong metadata. Mô tả chỉ diễn đạt tên, không xác nhận chiều nguồn/đích và không ánh xạ sang nhóm dùng cho split.

| Nhãn gốc | Cạnh | Ánh xạ (%) | Mô tả theo tên |
|---|---:|---:|---|
| Căn cứ | 668.173 | 99,87 | Nêu căn cứ. |
| Dẫn chiếu | 72.554 | 99,75 | Nêu dẫn chiếu. |
| Văn bản quy định hết hiệu lực | 50.939 | 99,90 | Nêu văn bản quy định hết hiệu lực. |
| Quy định chi tiết, hướng dẫn thi hành | 39.419 | 99,72 | Nêu quy định chi tiết, hướng dẫn thi hành. |
| Thay thế | 37.146 | 99,79 | Nêu việc thay thế. |
| Văn bản HD, QĐ chi tiết | 34.392 | 99,85 | Tên viết tắt; chưa xác nhận ý nghĩa. |
| Bãi bỏ | 32.479 | 99,71 | Nêu việc bãi bỏ. |
| Văn bản căn cứ | 26.515 | 4,93 | Nêu văn bản căn cứ. |
| Sửa đổi, bổ sung | 17.674 | 99,84 | Nêu việc sửa đổi, bổ sung. |
| Văn bản bổ sung | 12.853 | 99,91 | Nêu văn bản bổ sung. |
| Văn bản hết hiệu lực | 12.247 | 31,45 | Nêu văn bản hết hiệu lực. |
| Văn bản sửa đổi | 7.466 | 99,95 | Nêu văn bản sửa đổi. |
| Văn bản quy định hết hiệu lực 1 phần | 6.100 | 99,82 | Nêu quy định hết hiệu lực một phần. |
| Văn bản dẫn chiếu | 5.715 | 3,46 | Nêu văn bản dẫn chiếu. |
| Hợp nhất | 3.930 | 99,90 | Nêu việc hợp nhất. |
| Văn bản được HD, QĐ chi tiết | 1.388 | 18,08 | Tên viết tắt; chưa xác nhận ý nghĩa. |
| Hướng dẫn áp dụng | 1.333 | 99,92 | Nêu hướng dẫn áp dụng. |
| Văn bản bị hết hiệu lực 1 phần | 1.127 | 46,58 | Nêu văn bản bị hết hiệu lực một phần. |
| Văn bản được bổ sung | 532 | 7,33 | Nêu văn bản được bổ sung. |
| Văn bản liên quan khác | 387 | 77,78 | Không rõ loại liên quan cụ thể. |
| Văn bản được sửa đổi | 284 | 41,55 | Nêu văn bản được sửa đổi. |
| Đính chính | 209 | 100,00 | Nêu việc đính chính. |
| Tạm ngưng hiệu lực | 128 | 100,00 | Nêu tạm ngưng hiệu lực. |
| Giải thích | 98 | 100,00 | Nêu việc giải thích. |
| Đình chỉ thi hành | 72 | 100,00 | Nêu đình chỉ thi hành. |
| Bản dịch | 55 | 98,18 | Nêu bản dịch. |
| Văn bản đình chỉ 1 phần | 21 | 85,71 | Nêu văn bản đình chỉ một phần. |
| Văn bản đình chỉ | 16 | 81,25 | Nêu văn bản đình chỉ. |
| Công bố | 1 | 100,00 | Nêu việc công bố. |
| Văn bản bị đình chỉ | 1 | 0,00 | Nêu văn bản bị đình chỉ. |
| Văn bản bị đình chỉ 1 phần | 1 | 0,00 | Nêu văn bản bị đình chỉ một phần. |
| **Tổng** | **1.033.255** | **95,83** | **990.127 cạnh ánh xạ đủ** |

## 5. Mọi thay đổi đã thực hiện trong repo

Chỉ cập nhật `reports/data_stats/handoff_for_review.md`, thay kết luận cũ khi EDA đang chạy bằng đối chiếu thống kê hoàn tất. Không sửa script/config/SPEC.md/CLAUDE.md hay các kết quả EDA. Đã chạy kiểm tra đọc bằng Python: tổng metadata/bảng chéo, đối chiếu từng lĩnh vực và loại với 10.315 dòng thống kê, trạng thái content, số Điều ước lượng và tỷ lệ 31 loại quan hệ; đều khớp. Không chạy pipeline/test hay tải dữ liệu. Dừng ở điểm chờ 1; chưa chọn lĩnh vực, chưa xác nhận ánh xạ quan hệ.
