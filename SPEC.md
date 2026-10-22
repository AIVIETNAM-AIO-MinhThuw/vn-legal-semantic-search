# FINAL FROZEN METHODOLOGY SPEC  
## Tìm kiếm ngữ nghĩa văn bản pháp luật (Đề tài 8)

**Ngày chốt:** 2026-10-22

---

# 0. Cách dùng tài liệu

Tài liệu này là **nguồn sự thật duy nhất (source of truth)** về methodology của MVP. Mọi session Claude Code phải đọc tài liệu này trước khi viết hoặc sửa code.

- Từ **“phải”**, **“không được”**, **“chốt”** trong tài liệu là quy tắc cứng, không phải gợi ý.
- Giá trị số nằm trong `configs/*.yaml` và phải khớp với tài liệu này. Khi hai bên lệch nhau, tài liệu này thắng.
- Mục 17 liệt kê vấn đề duy nhất còn chưa chốt. Claude Code không được bắt đầu phần code phụ thuộc vấn đề mở cho đến khi nhóm ghi quyết định vào mục đó.
- Khi gặp vấn đề buộc phải đổi methodology, Claude Code phải:
  1. mô tả vấn đề;
  2. đề xuất thay đổi;
  3. nêu ảnh hưởng tới methodology và các artifact đã tạo;
  4. dừng lại chờ người quyết định.
- Mỗi thay đổi được chấp thuận phải ghi vào bảng **Changelog** ở cuối tài liệu.
- Không được âm thầm: đổi split, đổi nhãn, đổi metric, đổi prefix E5, đổi độ sâu pool, sửa giá trị kỳ vọng trong test, hoặc dùng test để tune.

---

# 1. Project objective

MVP xây dựng một hệ thống truy hồi **Điều luật tiếng Việt theo ngữ nghĩa**, và đo xem fine-tune `intfloat/multilingual-e5-base` bằng dữ liệu tổng hợp có cải thiện truy hồi so với zero-shot và BM25 hay không.

Sản phẩm gồm:

- pipeline dữ liệu tái lập được;
- năm hệ thống truy hồi chính (mục 7);
- một bộ đánh giá có nhãn do người quyết định;
- phân tích lỗi theo đề bài;
- một ứng dụng Streamlit dùng chung retriever với phần đánh giá.

## Giới hạn claim

Báo cáo **không được claim**:

- mô hình tốt nhất cho legal retrieval nói chung;
- vượt các mô hình chuyên miền pháp luật, vì MVP không đánh giá mô hình chuyên miền;
- tổng quát hóa ra ngoài corpus đã lọc hoặc ra ngoài kiểu query trong tập OOD;
- recall tuyệt đối trên toàn corpus;
- kết quả ổn định giữa các seed, vì MVP chỉ chạy một seed cho mỗi cấu hình.

Mọi kết luận phải dẫn về một con số trong bảng kết quả hoặc một ví dụ cụ thể.

## Hạn chế bắt buộc nêu trong mục Limitations của paper

- Val chỉ có nhãn Điều nguồn và do cùng LLM sinh, nên mọi lựa chọn trên val (learning rate, checkpoint, tham số BM25, thành phần dense của RRF) có thể thiên về mô hình quen phong cách câu hỏi của LLM.
- In-batch negative có thể vô tình là Điều liên quan tới query khác trong batch.
- OOD chỉ khoảng 40 câu, trừ các câu không trả lời được; kiểm định thống kê trên OOD có độ mạnh thấp và phải diễn giải thận trọng.
- Không xử lý trùng lặp gần giống (mục 3.6).
- Recall@k là recall tương đối theo pooled qrels (mục 11.4).
- Mỗi cấu hình chỉ chạy một seed.

---

# 2. Research questions

- **RQ1.** Fine-tune `multilingual-e5-base` bằng cặp `(query, Điều)` do LLM sinh có cải thiện NDCG@10 và MRR@10 so với e5 zero-shot và BM25 trên tập test không?

- **RQ2 (ablation).** Thêm hard negative có cải thiện so với chỉ dùng in-batch negative không, khi **learning rate, batch size, số epoch tối đa, seed và mọi thiết lập khác giữ nguyên**? Learning rate được chọn trên val cho cấu hình A rồi áp dụng nguyên cho cấu hình B (mục 8.4).

- **RQ3 (độ bền và tổng quát hóa).** Mức cải thiện của RQ1 có còn trên:
  - query có độ trùng từ vựng thấp với Điều liên quan;
  - query rất ngắn;
  - query không dấu và có lỗi chính tả;
  - Điều dài;
  - tập OOD do người viết?

Đặc biệt: cải thiện trên test có giữ được trên OOD không, hay mô hình chỉ học phong cách câu hỏi của LLM sinh dữ liệu?

**Câu hỏi phụ bắt buộc theo đề:** trong những trường hợp nào BM25 tốt hơn dense, và vì sao?

---

# 3. Dataset construction

## 3.1 Nguồn

- Dataset: `th1nhng0/vietnamese-legal-documents` trên Hugging Face.
- Phải ghim revision/commit hash của dataset trong `configs/data.yaml`.
- Không tải bản `main` trôi nổi.
- Dùng các phần: metadata, nội dung HTML, bảng `relationships`.

## 3.2 Bộ lọc văn bản

Thứ tự áp dụng cố định. Mỗi bước ghi số văn bản trước và sau vào log.

1. **Loại văn bản:** chỉ giữ Luật, Nghị định, Thông tư; danh sách chính xác theo giá trị trong metadata, ghi trong config.
2. **Tình trạng hiệu lực:** chỉ giữ văn bản còn hiệu lực.
3. **Lĩnh vực:** chỉ giữ 5–8 lĩnh vực trong danh sách ở config; danh sách chốt sau EDA, xem mục 17.
4. **Loại văn bản rỗng:** HTML rỗng hoặc parse ra không có Điều nào.
5. **Văn bản sửa đổi, bổ sung, thay thế** được giữ lại nếu qua các bước 1–4, và được gom họ theo mục 4.

## 3.3 Đơn vị truy hồi

- Đơn vị truy hồi, đơn vị gán nhãn và đơn vị tính metric đều là **Điều**.
- Chunk chỉ là đơn vị để encode và index.
- Điểm của một Điều = điểm lớn nhất trong các chunk của nó (**MaxP**).
- Run file và qrels đều ở cấp Điều (`article_id`).
- Mỗi chunk mang `article_id` để ánh xạ về Điều.

## 3.4 Quy tắc parse và chunk

Độ dài token đo bằng tokenizer của `multilingual-e5-base`, tính trên văn bản đã gắn tiền tố nhưng chưa tính `passage: `.

| Trường hợp | Quy tắc |
|---|---|
| Điều ngắn (`≤ 450 token`) | Một chunk = cả Điều. Không gộp nhiều Điều ngắn với nhau. |
| Điều dài (`> 450 token`) | Tách theo Khoản, gộp các Khoản liên tiếp vào một chunk sao cho mỗi chunk `≤ 450 token`. |
| Một Khoản `> 450 token` | Tách tại ranh giới câu, gộp câu thành cửa sổ `≤ 450 token`, chồng lấn 1 câu giữa hai cửa sổ liền nhau. |
| Một câu `> 450 token` | Cắt theo token thành cửa sổ `≤ 450 token`, chồng lấn 50 token. Ghi log `article_id` của mọi trường hợp này. |
| Phụ lục, biểu mẫu | Loại khỏi corpus. Ghi số lượng đã loại. |
| Bảng nằm trong Điều | Chuyển thành văn bản theo hàng, các ô nối bằng `|`, mỗi hàng một dòng. |
| Điều chỉ còn tiêu đề, hoặc nội dung chỉ là ghi chú bãi bỏ (`"được bãi bỏ"`, `"hết hiệu lực"`) | Loại. Ghi log theo `article_id`. |
| Parse lỗi, không xác định được số Điều hoặc cấu trúc vỡ | Loại, ghi `article_id` hoặc `doc_id` và lý do vào `logs/rejected.jsonl`. |

Tiền tố bắt buộc cho mọi chunk, dùng chung cho BM25 và dense:

```text
{Tên văn bản} › Điều {số}. {Tiêu đề Điều} › {nội dung chunk}
```

Tiền tố được tính vào giới hạn 450 token.

## 3.5 Chuẩn hóa văn bản

- HTML sang text thuần.
- Unicode NFC.
- Gộp khoảng trắng thừa.
- Giữ nguyên dấu tiếng Việt và chữ hoa trong văn bản lưu trữ.
- Mọi bước hạ chữ thường hoặc tách token chỉ diễn ra bên trong từng retriever.

## 3.6 Kiểm tra và loại trùng bắt buộc trước split

Script `validate_data` chạy **sau khi parse và chunk, trước khi split** (và do đó trước mọi bước sinh query và train). Script phải dừng với lỗi nếu một kiểm tra thất bại:

- không có chunk rỗng, không có `article_id` hoặc `doc_id` thiếu;
- mọi `article_id` trong chunk tồn tại trong bảng Điều, mọi `doc_id` tồn tại trong metadata;
- mọi chunk `≤ 450 token`, kể cả tiền tố;
- trùng lặp chính xác: hash SHA-1 của nội dung Điều đã chuẩn hóa, không tính tiền tố;
- mỗi nhóm Điều trùng hash chỉ giữ một **bản đại diện chuẩn** là Điều có `article_id` nhỏ nhất theo thứ tự chuỗi;
- các Điều còn lại bị loại khỏi index, mapping lưu trong metadata của bản đại diện ở trường `duplicate_article_ids`;
- quy tắc chọn bản đại diện là quy tắc kỹ thuật deterministic, **không mang ý nghĩa pháp lý**; không được diễn giải bản đại diện là văn bản “ưu tiên”, “mới hơn” hoặc “hiệu lực cao hơn”;
- run file và qrels chỉ dùng `article_id` của bản đại diện;
- ID `doc_id` ở đầu `relationships` phải ánh xạ được về `doc_id` trong metadata. **Ngoại lệ (OI-10):** cạnh có `other_doc_id` không tồn tại trong metadata không làm `validate_data` thất bại; ID đó được giữ làm **nút trung gian** trong đồ thị gom họ (mục 4.1). Không tạo văn bản hoặc nội dung giả cho ID đó, không tính nó vào corpus, vào thống kê văn bản hay vào lĩnh vực chủ đạo của họ; không bỏ cạnh. Ngoại lệ này chỉ áp dụng cho `other_doc_id` có giá trị khác null/rỗng; `doc_id` nguồn không có trong metadata, hoặc bất kỳ ID null/rỗng ở cả hai đầu, vẫn là **lỗi** làm `validate_data` dừng, và không được gom các ID null/rỗng thành một nút chung;
- script xuất tỷ lệ cạnh không ánh xạ được (báo cả trên toàn bộ cạnh và riêng các nhãn thuộc ánh xạ quan hệ trong config) và danh sách các loại quan hệ gốc trong dữ liệu;
- **Claude Code phải dừng, báo cáo các con số này và chờ người xác nhận trước khi chạy split**; không tự chuyển sang phương án khác dù tỷ lệ lỗi cao;
- phân phối độ dài chunk `(min, median, p95, max)` được log.

Không xử lý trùng lặp gần giống (**near-duplicate**) trong MVP. Ghi điều này vào Limitations.

## 3.7 Thống kê bắt buộc

Xuất ra `reports/data_stats/` cho cả trước và sau lọc:

- số văn bản theo loại;
- lĩnh vực;
- năm;
- hiệu lực;
- số Điều;
- số chunk;
- phân phối độ dài;
- số bản ghi bị loại theo từng lý do.

Không được loại bản ghi mà không có dòng log tương ứng.

---

# 4. Split protocol

Split được thực hiện ở cấp **họ văn bản** (`group_id`), không ở cấp chunk, Điều hay query.

## 4.1 Định nghĩa họ văn bản và quy tắc chia

- Họ văn bản được gom bằng **union-find** trên đồ thị quan hệ của `relationships`.
- Chỉ các cạnh thuộc loại **sửa đổi, bổ sung, thay thế** được dùng.
- Ánh xạ từ tên loại quan hệ gốc sang ba loại này được nhóm xác nhận sau EDA (mục 17) và ghi trong config.
- Union-find chạy trên **toàn bộ dataset trước khi lọc**, sau đó mới giới hạn về các văn bản có trong corpus.
- Vì vậy hai văn bản trong corpus nối với nhau qua một văn bản đã bị lọc vẫn thuộc cùng họ.
- Văn bản không có cạnh nào là một họ riêng.
- Cạnh có `other_doc_id` là ID khác null/rỗng nhưng không có trong metadata vẫn được dùng (ngoại lệ ở mục 3.6 chỉ áp dụng cho đầu `other_doc_id`; `doc_id` nguồn phải tồn tại trong metadata): ID đó là nút trung gian, mỗi giá trị ID là một nút riêng, và có thể nối hai văn bản trong corpus vào cùng họ. Nút này không phải văn bản, không thuộc corpus, không tính khi đếm lĩnh vực hay số văn bản của họ (OI-10).
- Chỉ các họ có ít nhất một văn bản trong corpus cuối cùng (sau bộ lọc mục 3.2 và sau parse/`validate_data`, tức văn bản còn ít nhất một Điều trong index) mới được đưa vào chia split; họ không có văn bản nào trong corpus bị bỏ khỏi `splits.json`.
- Mọi Điều của cùng một `group_id` nằm trong cùng một split.
- Kết hợp loại trùng bằng hash ở mục 3.6.
- Tỷ lệ: **80% train, 10% val, 10% test**, tính theo số họ có ít nhất một văn bản trong corpus cuối cùng.
- Phân tầng theo lĩnh vực xuất hiện nhiều nhất trong họ, đếm **chỉ trên các văn bản thuộc corpus cuối cùng của họ**; nếu hòa, chọn lĩnh vực đứng trước theo thứ tự chữ cái.
- Seed cố định, ghi trong `configs/data.yaml`.
- Kết quả ghi ra `data/splits.json` (`group_id → split`) và được commit vào repo.
- **Không được tạo lại hoặc sửa `splits.json` sau khi tập query test đã được tạo.**
- Nếu union-find gặp vấn đề như tỷ lệ cạnh không ánh xạ cao, dữ liệu quan hệ hỏng hoặc họ quá lớn, Claude Code **không được tự đổi sang cách chia khác**. Phải báo lại theo quy trình thay đổi ở mục 0.
- Claude Code chỉ báo phân phối kích thước họ (số văn bản trong corpus của mỗi họ, họ lớn nhất) trước khi split; **không** tự đặt ngưỡng cắt họ, không bỏ cạnh, không đổi cách split.

## 4.2 Phạm vi của split

- Query train chỉ sinh từ Điều thuộc split train.
- Query val chỉ sinh từ Điều thuộc split val.
- Query test chỉ sinh từ Điều thuộc split test.
- Index truy hồi chứa toàn bộ corpus của cả ba split.
- Một query test có thể có Điều liên quan nằm ở split khác; điều đó hợp lệ và phải ghi rõ trong paper.
- Hard negative cho training chỉ được lấy từ Điều thuộc split train.
- Văn bản của val và test không được xuất hiện trong bất kỳ dữ liệu huấn luyện nào, kể cả với vai trò negative.

## 4.3 Kiểm tra leakage bắt buộc

Script `check_leakage` phải chạy sau split và dừng với lỗi nếu:

- một `group_id` xuất hiện ở hơn một split;
- hash nội dung của một Điều train trùng với hash của một Điều val hoặc test; yêu cầu = 0;
- sau khi sinh query, một Điều nguồn của query train thuộc val hoặc test.

Số liệu chồng lấn phải xuất ra file. Con người xác nhận các con số này, không chỉ dựa vào thông báo “không có leakage” của script.

---

# 5. Query generation

## 5.1 Bộ sinh

- LLM: Gemini qua API free tier.
- Tên model chính xác, temperature, prompt và ngày sinh được ghi vào config và metadata file đầu ra.
- Prompt là một file có version trong `prompts/`. Sửa prompt nghĩa là tăng version.
- Mỗi request gửi 10–20 Điều, nhận JSON theo schema cố định có `article_id`.
- Script phải resume được sau khi bị ngắt:
  - ghi JSONL tăng dần;
  - bỏ qua `article_id` đã xử lý;
  - tự retry khi gặp rate limit.
- Sinh bằng LLM không tái lập được từng bit. File query đã sinh là artifact gốc, được lưu và version hóa.
- Mọi bước sau bắt đầu từ file này, không gọi lại LLM.

## 5.2 Kiểu query

Với mỗi Điều được chọn, bộ sinh tạo đúng ba query:

- `natural`: câu hỏi của người dân, ngôn ngữ đời thường, không lặp thuật ngữ pháp lý của Điều khi có cách nói thông thường;
- `scenario`: mô tả một tình huống cụ thể mà Điều trả lời được;
- `keyword`: 1–4 từ, như gõ vào ô tìm kiếm.

Prompt cấm:

- chép nguyên câu từ Điều;
- nhắc số hiệu Điều;
- nhắc số hiệu văn bản.

Bộ sinh trả cờ `skip` cho Điều không đặt câu hỏi được.

Loại trước khi sinh các Điều có tiêu đề thuộc nhóm thi hành:

- “Hiệu lực thi hành”;
- “Trách nhiệm thi hành”;
- “Điều khoản thi hành”;
- “Tổ chức thực hiện”.

## 5.3 Đo độ trùng từ vựng

- Token hóa: NFC, chữ thường, tách theo khoảng trắng và dấu câu thành âm tiết, giữ dấu tiếng Việt, không bỏ stopword.
- Định nghĩa:

```text
overlap(q, d) =
số âm tiết khác nhau của query có mặt trong Điều
/
số âm tiết khác nhau của query
```

Điều ở đây gồm tiêu đề và nội dung, không gồm tên văn bản.

- **Chép nguyên văn:** query chứa một chuỗi liên tiếp từ **N = 8 âm tiết** trở lên lấy nguyên từ Điều.
- Query chép nguyên văn bị loại khỏi mọi tập.
- Ngưỡng lọc overlap cao cho train = **0,8**.
- Ngưỡng overlap cao chỉ áp dụng cho **train**.
- Val và test không bị lọc theo overlap, chỉ bị phân nhóm trong phân tích.
- Không lọc test theo overlap để tránh chủ động tạo bất lợi cho BM25.

## 5.4 Bốn tập query

| Tập | Quy mô | Nguồn Điều | Người duyệt | Nhãn |
|---|---:|---|---|---|
| Train | khoảng 5.000 cặp | Split train, chọn ngẫu nhiên phân tầng theo lĩnh vực | Không, chỉ lọc tự động | Điều nguồn |
| Val | 150 query: 50 natural, 50 scenario, 50 keyword | Split val, mỗi Điều một query | Có: chấp nhận hoặc loại | Điều nguồn, mức 2 |
| Test | 150 query: 50 natural, 50 scenario, 50 keyword | Split test, mỗi Điều một query | Có: chấp nhận, loại hoặc sửa câu chữ giữ nguyên ý | Qrels từ pooling |
| OOD | khoảng 40 query | Người viết | Là người viết | Qrels từ pooling |

Train dùng mọi query qua bộ lọc của các Điều được chọn.

Với val và test, kiểu query của mỗi Điều được gán ngẫu nhiên theo seed để đạt đúng tỷ lệ 50/50/50.

Lý do loại khi duyệt val và test:

- khó hiểu;
- Điều nguồn không trả lời được;
- chứa số hiệu Điều hoặc văn bản;
- trùng ý với query khác trong tập.

Query bị loại được thay bằng query từ một Điều khác cùng split.

Sau khi người sửa câu chữ một query, phải chạy lại kiểm tra chép nguyên văn (N = 8, mục 5.3) trên bản đã sửa. Bản sửa vi phạm thì phải sửa lại hoặc loại.

Mọi sửa câu chữ phải ghi vào `logs/test_query_edits.jsonl` gồm:

- bản gốc;
- bản sửa;
- người sửa.

### Đóng băng

Sau khi duyệt xong:

- `queries_test.jsonl`;
- `queries_ood.jsonl`;

được ghi hash SHA-256 vào `data/FROZEN.md`.

Sau thời điểm này không được sửa nội dung query.

Người chấm phát hiện query có vấn đề chỉ đánh dấu `query_issue`, không sửa.

## 5.5 Biến thể của tập test

Chỉ sinh từ tập test, bằng quy tắc xác định, seed cố định. Không sinh từ OOD.

### `no_diacritic`

- bỏ toàn bộ dấu thanh và dấu mũ;
- `đ → d`.

### `typo`

- query `≤ 5` âm tiết: 1 lỗi;
- query dài hơn: 2 lỗi;
- mỗi lỗi chọn đều một trong bốn loại:
  - thay bằng phím kề;
  - xóa ký tự;
  - đảo hai ký tự kề nhau;
  - lỗi gõ Telex, ví dụ `hojc` thay cho `học`.

Mỗi biến thể có:

- `query_id` riêng;
- `variant_of` trỏ về query gốc;
- `variant_type`.

Biến thể dùng chung qrels với query gốc.

Một người đọc mẫu 30 biến thể typo. Biến thể có nghĩa bị đổi thì bị loại, không gán nhãn lại; số lượng loại được báo cáo.

Biến thể:

- không bao giờ được đưa vào dữ liệu huấn luyện;
- không tham gia pooling.

---

# 6. OOD protocol

Tập OOD tồn tại để trả lời câu hỏi: cải thiện của mô hình fine-tune đến từ việc hiểu miền, hay chỉ từ việc học phong cách câu hỏi của LLM sinh dữ liệu?

1. **Viết**
   - Mỗi thành viên viết khoảng 8 câu hỏi, tổng khoảng 40.
   - Người viết chỉ được biết danh sách lĩnh vực trong corpus.
   - Người viết không được đọc Điều, văn bản hoặc kết quả tìm kiếm nào trước khi viết.
   - Không được dùng Claude hoặc bất kỳ LLM nào để gợi ý, sửa hoặc diễn đạt lại câu hỏi.

2. **Đóng băng câu chữ**
   - Câu hỏi được nộp và ghi hash trước khi tìm đáp án.
   - Không sửa câu hỏi sau bước này.

3. **Tìm đáp án**
   - OOD đi qua pooling và gán nhãn giống test.
   - Nếu pool không có Điều nào được chấm 1 hoặc 2, người viết tìm thủ công trong corpus bằng công cụ tìm kiếm của dự án.
   - Giới hạn 10 phút mỗi câu.
   - Điều tìm được thêm vào qrels với nhãn do người quyết định và cờ `found_manually = true`.

4. **Câu không trả lời được**
   - Nếu vẫn không có Điều liên quan, query được đánh dấu `unanswerable`.
   - Loại khỏi mọi metric.
   - Báo cáo số lượng và tỷ lệ bị loại.

Quy tắc này cũng áp dụng cho query test: query test không có Điều nào được chấm từ 1 trở lên, kể cả Điều nguồn, bị loại khỏi metric và được báo cáo.

OOD:

- không có biến thể;
- không dùng để tune;
- chỉ chạy cùng test trong lần đánh giá cuối.

---

# 7. Systems

## 7.1 Các hệ thống trong bảng kết quả chính

| ID | Hệ thống | Ghi chú |
|---|---|---|
| S1 | BM25 | Thư viện `bm25s`. Token hóa giống mục 5.3: âm tiết, chữ thường, giữ dấu. Không tách từ. `k1` và `b` chọn trên val theo mục 7.5. |
| S2 | `multilingual-e5-base` zero-shot | `intfloat/multilingual-e5-base`, không huấn luyện thêm. |
| S3 | E5 fine-tune, in-batch negative, cấu hình A | Mục 8. |
| S4 | E5 fine-tune, in-batch + hard negative, cấu hình B | Mục 8. |
| S5 | Hybrid RRF | Reciprocal Rank Fusion của S1 và checkpoint dense có NDCG@10 trên val cao hơn giữa S3 và S4. `k = 60`, cố định, không tune. Trộn top-100 Điều của mỗi thành phần. |

Không có hệ thống nào khác trong bảng chính.

Muốn thêm hệ thống phải theo quy trình thay đổi ở mục 0 và phải thêm hệ thống đó vào pool trước khi đóng băng qrels.

## 7.2 Quy tắc truy hồi chung

Mọi hệ thống cài đặt cùng interface:

```python
search(query, k, filters) -> list[(article_id, score)]
```

Dense:

- embedding chuẩn hóa L2;
- lưu `float32`;
- tìm kiếm chính xác bằng tích vô hướng, brute-force;
- không dùng tìm kiếm xấp xỉ.

Mỗi hệ thống:

- lấy top-200 chunk;
- gộp về Điều theo MaxP;
- trả về top-k Điều.

Đánh giá chạy **không có filter**.

Filter chỉ dùng trong app, áp dụng dạng mặt nạ trước khi xếp hạng.

## 7.3 Quy tắc encode E5 — quy tắc cứng

Query:

```text
query: {query_text}
```

Passage:

```text
passage: {chunk_text_có_tiền_tố}
```

Quy tắc:

- áp dụng prefix đúng một lần;
- dùng một hàm duy nhất trong code;
- dùng chung cho zero-shot, fine-tune, đánh giá và app;
- tokenizer lấy từ chính checkpoint đang dùng;
- `max_length = 512` cho cả query và passage;
- passage sau khi thêm `passage: ` phải `≤ 512 token`;
- nếu vượt thì báo lỗi, không được cắt âm thầm;
- pooling: mean pooling theo attention mask;
- embedding chuẩn hóa L2.

Unit test bắt buộc:

- prefix không bị gắn hai lần;
- chuẩn embedding xấp xỉ 1;
- cùng một văn bản encode hai lần cho cùng kết quả.

## 7.4 Manifest

Mỗi index BM25 và dense có `manifest.json` bên cạnh, gồm ít nhất:

- tên và revision model/checkpoint;
- tên tokenizer;
- `max_length`;
- prefix query và passage;
- kiểu pooling;
- có chuẩn hóa hay không;
- số chiều embedding;
- kiểu dữ liệu lưu;
- version tiền xử lý;
- hash file chunk;
- số chunk;
- với BM25: `k1`, `b`, cách token hóa.

Khi nạp index, code so manifest với config đang chạy.

Bất kỳ trường nào không khớp thì **dừng với lỗi**.

Đánh giá và app dùng chung hàm nạp index và kiểm tra manifest.

## 7.5 Chọn tham số BM25

Lưới:

```text
k1 ∈ {0.9, 1.2, 1.5}
b  ∈ {0.4, 0.75}
```

- Tổng 6 tổ hợp.
- Chọn tổ hợp có NDCG@10 trên val cao nhất.
- Tổ hợp được chọn ghi vào config và đóng băng.
- Không thay đổi dựa trên test.
- Kết quả cả 6 tổ hợp ghi vào `reports/bm25_tuning.csv`.

---

# 8. Training

## 8.1 Thiết lập chung cho cả hai cấu hình

- Thư viện `sentence-transformers`.
- Loss: `MultipleNegativesRankingLoss`.
- Khởi tạo từ `intfloat/multilingual-e5-base`.
- Quy tắc encode giống mục 7.3.
- Batch sampler: `NO_DUPLICATES`.
- Không để hai cặp có cùng Điều nguồn nằm chung một batch.
- Batch size giống nhau cho A và B.
- Batch size = giá trị lớn nhất cấu hình B chạy được trên T4 với fp16.
- Lý do: số negative trong batch ảnh hưởng trực tiếp tới MNRL, batch size khác nhau sẽ làm ablation bị nhiễu.
- `fp16`.
- Warmup = 10% số bước.
- Một seed cố định cho mọi lần chạy.
- Chỉ dùng dữ liệu split train.

## 8.2 Hai cấu hình

### Cấu hình A

- bộ đôi `(query, Điều nguồn)`;
- negative chỉ là các passage khác trong batch.

### Cấu hình B

- bộ ba `(query, Điều nguồn, 1 hard negative)`;
- mọi thiết lập khác giống A.

## 8.3 Đào hard negative — chỉ cho cấu hình B

Ứng viên lấy từ:

- S1 BM25;
- S2 e5 zero-shot.

Retrieval chạy trên index chỉ chứa chunk của split train, sau đó gộp về Điều.

Candidate window cố định:

```text
rank 3–30
```

Loại:

- Điều nguồn;
- Điều cùng văn bản;
- Điều cùng `group_id`;
- Điều có hash nội dung trùng Điều nguồn.

Từ ứng viên còn lại, chọn ngẫu nhiên 1 theo seed.

Kiểm tra false negative:

- một người đọc 30 bộ ba ngẫu nhiên;
- đánh dấu hard negative nào thật ra liên quan;
- báo cáo tỷ lệ.

Tuyệt đối không dùng:

- nhãn val;
- nhãn test;
- qrels;
- query test;
- Điều thuộc split val/test.

## 8.4 Chọn learning rate và checkpoint

1. **Tune trên cấu hình A:** huấn luyện A với từng learning rate trong `{1e-5, 3e-5}`, tối đa **2 epoch**.
2. Cuối mỗi epoch: encode toàn bộ corpus, đánh giá trên val.
3. Learning rate của A = giá trị cho NDCG@10 trên val cao nhất; hòa thì xét MRR@10.
4. Learning rate này được **đóng băng**.
5. **Cấu hình B dùng đúng learning rate đó**, cùng batch size, cùng số epoch tối đa, cùng seed và mọi thiết lập khác.
6. B không được tune learning rate riêng.
7. Khác biệt duy nhất giữa A và B là việc thêm hard negative.
8. Checkpoint A và B mỗi bên được chọn riêng theo epoch có NDCG@10 trên val cao nhất; hòa thì xét MRR@10.
9. Mọi lần chạy ghi vào `reports/training_runs.csv`, kể cả lần không được chọn.
10. Checkpoint được chọn của A và B được đẩy lên Hugging Face Hub, ghi revision vào config.
11. Sau khi qrels đóng băng, không huấn luyện lại, trừ khi thực hiện change procedure ở mục 0 và mở lại pool theo mục 9.4.

---

# 9. Pooling

Pooling là **incremental**, độ sâu **10 Điều**, áp dụng cho:

- query gốc của test;
- OOD.

Biến thể không tham gia pooling.

## 9.1 Các phiên bản pool

| Phiên bản | Thêm vào pool | Điều kiện |
|---|---|---|
| v1 | top-10 của S1 và S2 | Query test và OOD đã đóng băng; S1 và S2 đã chạy xong |
| v2 | top-10 của S3 | Checkpoint A đã chọn trên val |
| v3 | top-10 của S4 | Checkpoint B đã chọn trên val |
| v4 | top-10 của S5 | S1 đã chốt tham số; checkpoint dense của RRF đã chọn trên val; chạy sau v3 |

Quy tắc:

- pool là union theo từng query của các cặp `(query, article_id)`;
- mỗi version chỉ xuất phần chênh lệch, tức các cặp chưa từng được chấm;
- không chấm lại cặp có nhãn, trừ cặp neo ở mục 10.4;
- mỗi version pool lưu thành file riêng, kèm danh sách hệ thống đã đóng góp;
- chỉ checkpoint đã chọn trên val mới đóng góp vào pool;
- các lần chạy thử không đóng góp.

## 9.2 Đóng băng qrels

Qrels chỉ được đóng băng khi:

- mọi hệ thống trong bảng kết quả chính đã đóng góp vào pool;
- mọi cặp trong pool có nhãn cuối cùng.

Khi đóng băng:

- ghi hash SHA-256 của qrels vào `data/FROZEN.md`;
- ghi danh sách hệ thống trong pool.

**Mọi cặp trong pool cuối phải có nhãn do người gán. Không có cặp nào được đóng băng với nhãn chỉ đến từ LLM.**

## 9.3 Cặp chưa được chấm

Khi tính metric, Điều không có trong qrels được coi là không liên quan.

Điều này áp dụng cho:

- Điều ngoài pool;
- Điều mà biến thể truy hồi được nhưng query gốc không truy hồi vào pool.

Phạm vi ảnh hưởng được đo bằng judged coverage.

## 9.4 Sau khi đóng băng

Không:

- huấn luyện lại;
- thay checkpoint;
- thêm hệ thống vào bảng chính.

Nếu bắt buộc phải thay đổi:

1. theo quy trình mục 0;
2. tạo pool version mới;
3. chấm phần delta;
4. đóng băng lại qrels;
5. ghi vào Changelog.

---

# 10. Human annotation

## 10.1 Thang nhãn

| Nhãn | Ý nghĩa |
|---:|---|
| 2 | Điều trả lời trực tiếp và đầy đủ câu hỏi. |
| 1 | Điều liên quan và hữu ích nhưng không đủ để trả lời; thiếu điều kiện, chỉ một phần, hoặc cần thêm Điều khác. |
| 0 | Không liên quan hoặc chỉ trùng từ ngữ mà không giúp trả lời. |

Guideline đầy đủ nằm ở `annotation/GUIDELINE.md`.

Guideline có ít nhất 2 ví dụ cho mỗi nhãn. Ví dụ lấy từ val, không lấy từ test.

## 10.2 Che thông tin — blind

Người chấm chỉ thấy:

- query;
- toàn văn Điều;
- tên văn bản;
- số Điều;
- tiêu đề.

Người chấm không thấy:

- hệ thống nào đề xuất ứng viên;
- thứ hạng;
- điểm số;
- tên model;
- số hệ thống cùng đề xuất ứng viên;
- ứng viên nào là Điều nguồn;
- nhãn nháp LLM;
- bất kỳ metric tạm thời nào.

Ứng viên trong mỗi query được xáo trộn theo seed.

Công cụ chấm phải bảo đảm việc blind ngay trong dữ liệu xuất cho annotator.

## 10.3 Phân công và hiệu chỉnh

- Mỗi query thuộc về đúng một người chấm qua mọi version pool.
- Query chia đều cho 5 người.
- Trước khi chấm thật, cả 5 người cùng chấm 20 cặp lấy từ val.
- So sánh, thảo luận bất đồng và cập nhật guideline.
- Sau đó guideline được đóng băng với version.
- Mỗi thay đổi guideline sau đóng băng phải tăng version và ghi lý do.
- Các nhãn cũ bị ảnh hưởng phải chấm lại.
- Trong vòng hiệu chỉnh, ghi thời gian chấm trung bình mỗi cặp và ước tính tổng giờ công cho toàn bộ pool. Nếu nhóm thấy không kịp, mọi điều chỉnh quy mô (ví dụ số query test) phải đi qua change procedure ở mục 0 **trước khi tạo pool v1**, không được thay đổi giữa chừng.

## 10.4 Kiểm soát nhất quán

### Chấm chéo

- 15% số query của test và OOD, chọn ngẫu nhiên theo seed, được một người thứ hai chấm toàn bộ và độc lập.
- Báo cáo:
  - tỷ lệ đồng ý thô;
  - Cohen's kappa có trọng số tuyến tính.
- Bất đồng do người thứ ba phân xử.
- Nhãn sau phân xử là nhãn cuối.

### Cặp neo

Từ pool v2 trở đi:

- 5% số cặp trong mỗi lô của một người là cặp chính người đó đã chấm ở lô trước;
- trộn lẫn;
- không đánh dấu.

Báo cáo mức tự nhất quán theo thời gian.

Người chấm phát hiện query có vấn đề:

- gắn `query_issue`;
- ghi chú;
- không sửa query.

## 10.5 Vai trò của LLM

- **Qrels cuối hoàn toàn do người gán nhãn; LLM không quyết định relevance.**
- Mọi cặp `(query, article_id)` trong pool cuối phải được người chấm.
- Không có ngoại lệ, kể cả cặp LLM chấm 0.
- LLM được phép tạo nhãn nháp **chỉ** để tính mức đồng thuận giữa người và LLM và báo cáo con số này.
- Nhãn nháp không được hiển thị cho người chấm.
- Nhãn nháp không được dùng để sắp thứ tự.
- Nhãn nháp không được dùng để chọn cặp cần chấm.
- Nhãn nháp không được dùng làm nhãn cuối.

## 10.6 Phân loại negative trong tập đánh giá

Với mỗi query, Điều được chấm 0 chia thành:

- **Hard negative:** xuất hiện trong top-3 của ít nhất một hệ thống, hoặc cùng văn bản/cùng `group_id` với một Điều được chấm từ 1 trở lên;
- **Không liên quan:** các Điều chấm 0 còn lại.

Cả hai nhóm lưu trong file đánh giá cùng với các Điều liên quan.

---

# 11. Evaluation

## 11.1 Kỷ luật với tập test

Metric hiệu năng trên test và OOD không được dùng cho:

- chọn hyperparameter;
- chọn checkpoint;
- thay đổi preprocessing;
- thay đổi retrieval architecture;
- đào hard negative;
- quyết định feature.

Trước lần đánh giá cuối, trên test chỉ được chạy kiểm tra toàn vẹn:

- đủ query;
- đúng định dạng run;
- không có kết quả rỗng;
- không trùng ID;
- judged coverage;
- phân phối nhãn.

Script kiểm tra toàn vẹn không được in metric hiệu năng.

Mọi debugging hiệu năng làm trên val.

Nếu ai đó lỡ xem metric test trước final evaluation:

- phải ghi vào Changelog;
- sau đó chỉ chấp nhận sửa lỗi có thể biện minh độc lập với con số đã xem.

Final evaluation chạy đúng một lần khi:

1. mọi cấu hình đã chốt trên val;
2. final pool chấm xong;
3. qrels đóng băng.

## 11.2 Metric

Báo cáo:

- P@1, P@5, P@10;
- R@1, R@5, R@10;
- NDCG@1, NDCG@5, NDCG@10;
- MRR@10;
- MAP@10.

### Cách tính relevance

- Dùng `ranx`.
- NDCG dùng nhãn 0/1/2 làm graded gain tuyến tính.
- **Bảng chính:** với P, R, MRR, MAP, Điều có nhãn `≥ 1` được coi là relevant.
- **Phân tích độ nhạy ở phụ lục:** cùng các metric khi chỉ nhãn `= 2` được coi là relevant.
- Hai ngưỡng không xuất hiện lẫn nhau trong cùng một bảng.
- Mỗi bảng ghi rõ threshold.

### Unit test metric

- Dùng một qrels và run nhỏ.
- Expected values do người tính tay.
- Ghi cố định trong unit test.
- Claude Code không được sửa expected values để làm test pass.

### Validation

- Val chỉ có Điều nguồn với mức 2.
- Metric val chỉ dùng để so sánh tương đối giữa cấu hình.

### Latency

- Đo trên CPU máy demo.
- Mỗi lần một query.
- Warm-up 10 query.
- Tính toàn bộ `search()`:
  - encode query;
  - search;
  - MaxP aggregation.
- Không tính thời gian load model.
- Báo cáo p50 và p95 trên query gốc của test.
- Ghi cấu hình máy.

### Index size

Dung lượng trên đĩa, MB, của mọi file index cần cho retrieval; tách BM25 và dense.

### Kiểm định thống kê

Thực hiện paired significance testing trên **NDCG@10 theo query** cho:

- S1–S2;
- S2–S3;
- S3–S4;
- dense tốt hơn trên val (S3 hoặc S4, chính là thành phần dense của S5) – S5.

Quy tắc:

- dùng **Fisher randomization / permutation test** để lấy raw p-value;
- dùng `ranx` cho Fisher randomization test nếu API/version đang dùng hỗ trợ đúng phép kiểm định này;
- `10.000` permutations;
- seed cố định;
- `α = 0,05`;
- sau khi có 4 raw p-values, áp dụng **Holm multiple-comparison correction** bằng implementation/thư viện phù hợp, ví dụ `statsmodels.stats.multitest.multipletests`;
- Holm correction áp dụng riêng cho từng tập: 4 p-value của test gốc, và 4 p-value của OOD;
- **không claim Holm correction là tính năng của `ranx`**;
- phương pháp và tham số phải ghi trong config trước final evaluation;
- không đổi phương pháp sau khi xem kết quả;
- chạy trên test gốc và OOD.

## 11.3 Đầu ra bắt buộc

Với mỗi hệ thống và mỗi tập gồm val, test gốc, từng loại biến thể, OOD:

- run file định dạng TREC, top-100 Điều, trong `runs/`;
- metric tổng hợp;
- metric theo từng query trong `reports/`;
- bảng và hình xuất CSV và PNG từ một lệnh duy nhất.

## 11.4 Judged coverage và Recall

Báo cáo:

```text
judged@10 =
tỷ lệ Điều trong top-10 đã có nhãn
```

cho từng hệ thống, từng tập, kể cả biến thể.

Recall@k là **recall tương đối**, tính trên các Điều liên quan đã tìm thấy qua pooling.

Không phải exhaustive recall trên toàn corpus.

Paper phải nói rõ điều này.

Không claim qrels đầy đủ trên toàn corpus.

## 11.5 Chiều phân tích

Mọi chiều tính trên metric theo từng query. Ranh giới nhóm cố định trước final evaluation.

| Chiều | Định nghĩa |
|---|---|
| Kiểu query | `natural`, `scenario`, `keyword` |
| Độ trùng từ vựng | overlap với Điều nguồn; chia ba nhóm theo tam phân vị trên query gốc test |
| Độ dài query | 1–3, 4–8, `≥ 9` âm tiết |
| Độ dài Điều | số token của Điều nguồn, chia ba nhóm theo tam phân vị |
| Biến thể | gốc, `no_diacritic`, `typo` |
| Phân phối | test in-distribution và OOD |

Nhóm overlap thấp chỉ được gọi là:

> proxy cho lexical mismatch / diễn đạt lại

Không được gọi là “query đồng nghĩa”.

Một người đọc 20 query trong nhóm overlap thấp và ghi nhận bao nhiêu query thật sự dùng từ đồng nghĩa; báo cáo con số này.

Nhóm Điều dài chỉ là đại diện cho yêu cầu “tài liệu có nhiều nội dung không liên quan”, phải gọi đúng là đại diện.

---

# 12. Error analysis

Phân tích lỗi dựa trên metric theo từng query của final evaluation.

Claude Code chỉ được trích xuất candidate ví dụ và số liệu.

Nguyên nhân lỗi và kết luận do người trong nhóm xác nhận.

Ví dụ bắt buộc, mỗi nhóm ít nhất 2 ví dụ nếu có:

- BM25 thắng dense;
- dense thắng BM25;
- fine-tune S3/S4 thắng zero-shot S2;
- fine-tune thua zero-shot;
- hard negative giúp: S4 thắng S3;
- hard negative gây hại: S4 thua S3;
- OOD thất bại: mọi dense system bỏ lỡ;
- false negative: Điều liên quan được phát hiện trong pool nhưng nằm ngoài Điều nguồn;
- lỗi parse/chunk nếu phát hiện.

Tiêu chí “thắng”:

```text
ΔNDCG@10 ≥ 0,3
```

Ngưỡng cố định trước khi xem final results.

Mỗi ví dụ gán một nguyên nhân từ danh sách:

- lệch từ vựng;
- query quá ngắn/mơ hồ;
- mất dấu/lỗi chính tả;
- thuật ngữ hiếm/tên riêng;
- Điều dài, nội dung loãng;
- nhiều Điều gần trùng;
- nhãn thiếu/false negative của qrels;
- lỗi parse/chunk;
- `other` kèm ghi chú.

Báo cáo số lượng theo từng nguyên nhân và liên hệ đặc trưng tiếng Việt khi phù hợp:

- âm tiết;
- dấu thanh;
- từ Hán-Việt so với từ thuần Việt.

---

# 13. Reproducibility

Mọi con số trong paper phải sinh lại được từ repo bằng lệnh ghi trong README.

Không chép số từ notebook.

## 13.1 Repo phải có

- `configs/*.yaml`: mọi tham số, đường dẫn, seed, revision dataset/model; không hard-code trong code.
- Script cho từng bước:
  - chuẩn bị dữ liệu;
  - validate dữ liệu;
  - split;
  - check leakage;
  - sinh query;
  - sinh biến thể;
  - build index;
  - train;
  - evaluate;
  - tạo pool;
  - nhập nhãn;
  - xuất report;
  - tải artifact.
- `requirements.txt` ghim version.
- Torch CPU cho máy demo.
- Environment/version training trên Kaggle ghi riêng.
- `README.md`:
  - cách cài;
  - tải artifact;
  - chạy lại final evaluation từ artifact;
  - chạy app.
- Unit test:
  - metric với expected value tính tay;
  - E5 prefix;
  - tokenization consistency;
  - manifest.
- `data/FROZEN.md`: hash của split, query test, query OOD, qrels và thời điểm freeze.
- Changelog methodology.

## 13.2 Artifact

| Artifact | Nơi lưu |
|---|---|
| `splits.json`, query files, qrels, raw annotations, run files, reports | GitHub, dạng text |
| Checkpoint A, B | Hugging Face Hub, ghi revision trong config |
| Dense index, processed chunks | Hugging Face dataset repo hoặc Google Drive, có script tải; hoặc build lại bằng script |

Không commit model hoặc binary lớn vào GitHub.

## 13.3 Hai mức tái lập

### 1. Tái lập đánh giá

Bắt buộc chạy được trên CPU:

- từ artifact đã lưu;
- một lệnh chạy lại toàn bộ bảng kết quả.

### 2. Tái lập toàn bộ

Từ dataset gốc đến checkpoint.

- Training cần GPU.
- Query generation bằng LLM không tái lập bit-by-bit.
- File query đã lưu là điểm xuất phát chính thức cho nhánh reproducibility.

---

# 14. App architecture

## 14.1 Ranh giới

- Streamlit chỉ là UI.
- Toàn bộ retrieval logic ở `src/retrieval/`.
- App dùng đúng retriever, index và manifest loader mà evaluation dùng.
- App không có implementation riêng cho:
  - retrieval;
  - tokenization;
  - prefix.
- Semantic model trong app = checkpoint có NDCG@10 trên val cao hơn giữa S3 và S4.
- Không chọn model app dựa trên test.

## 14.2 Chức năng tối thiểu

| Chức năng | Quy tắc |
|---|---|
| Nhập query | Ô văn bản tiếng Việt |
| Top-k | Chọn 1–20, mặc định 10 |
| Chế độ | BM25; Semantic; Hybrid S5; So sánh hai cột BM25 và Semantic, đánh dấu Điều xuất hiện ở cả hai |
| Filter | Loại văn bản, lĩnh vực, cơ quan ban hành, năm ban hành; áp dụng mask trước ranking |
| Điểm | Hiển thị raw score kèm tên thang: `BM25` hoặc `cosine`; không đặt hai thang lên cùng một trục |
| Highlight | BM25: tô âm tiết query xuất hiện trong Điều. Semantic: tô câu trong Điều có cosine cao nhất với query, chỉ tính cho kết quả đang hiển thị, có cache |
| Thông tin kết quả | Tên văn bản, số và tiêu đề Điều, tình trạng hiệu lực, nội dung Điều |
| Feedback | Nút `Hữu ích` / `Không hữu ích` trên từng kết quả |
| Xuất feedback | Tải CSV |
| Lưu ý pháp lý | “Kết quả không thay thế tư vấn pháp lý.” |

## 14.3 Xử lý đầu vào

- Query rỗng/chỉ khoảng trắng/ký tự đặc biệt: không search, hiển thị thông báo.
- Query vượt giới hạn token: cắt theo tokenizer và hiển thị cảnh báo.
- Filter không còn Điều: thông báo, không crash.
- Model load lỗi hoặc manifest mismatch: dừng app, thông báo rõ ràng; không chạy index sai.

## 14.4 Lưu feedback

SQLite, mỗi lượt một dòng:

- thời điểm;
- query;
- mode;
- model/revision;
- `article_id`;
- rank;
- label.

Feedback không được dùng trong metric của MVP.

---

# 15. Frozen decisions — các mốc đóng băng

Các artifact dưới đây được freeze theo thứ tự. Mỗi mốc ghi hash và thời điểm vào `data/FROZEN.md`.

Sau freeze, artifact chỉ được đổi qua change procedure ở mục 0.

1. **Danh sách lĩnh vực và ánh xạ loại quan hệ:** sau EDA, trước lọc và split.
2. **`splits.json`:** trước khi sinh bất kỳ query nào.
3. **Prompt sinh query và tập val:** trước khi đánh giá zero-shot trên val.
4. **Tham số BM25:** sau khi tune trên val.
5. **Query test và query OOD:** trước pool v1.
6. **Annotation guideline:** sau calibration, trước chấm pool v1.
7. **Learning rate:** chọn trên A, freeze trước khi train B.
8. **Checkpoint A và B:** sau khi chọn trên val, trước pool v2/v3.
9. **Cấu hình S5, gồm dense component:** trước pool v4.
10. **Ranh giới nhóm phân tích, ngưỡng thắng và phương pháp kiểm định thống kê:** trước final evaluation.
11. **Qrels:** khi mọi cặp trong final pool có human label.

---

# 16. Things explicitly prohibited

Không được:

- dùng test/OOD metric cho bất kỳ quyết định nào;
- sửa artifact đã freeze mà không qua change procedure;
- đưa query, variant, label hoặc văn bản val/test vào training, kể cả negative;
- đổi E5 prefix, pooling, normalization, `max_length`, hoặc truncate passage âm thầm;
- dùng approximate search trong evaluation;
- đổi pool depth, label scale hoặc metric definition;
- sửa expected values trong metric unit test để test pass;
- loại record mà không log;
- cho annotator thấy system source, rank, score, LLM label hoặc provisional metric;
- dùng LLM/Claude viết, gợi ý hoặc sửa OOD query;
- để LLM quyết định final relevance label;
- thêm system vào main table mà không đưa system đó vào pool;
- tạo retrieval logic riêng trong app;
- bắt đầu phần code phụ thuộc OI-10 trước khi nhóm quyết định;
- trong paper:
  - claim vượt giới hạn mục 1;
  - gọi low-overlap group là “query đồng nghĩa”;
  - trình bày Recall@k như exhaustive recall;
- dùng learning rate, batch size, số epoch tối đa hoặc seed khác nhau cho A và B;
- tự chuyển từ union-find sang cách split khác nếu relationships có vấn đề;
- tự chọn danh sách lĩnh vực;
- tự chọn ánh xạ relation labels;
- dùng LLM draft label để sắp thứ tự, chọn cặp cần chấm hoặc làm final label;
- diễn giải canonical duplicate representative như một kết luận pháp lý.

---

# 17. REMAINING OPEN ISSUE

| ID | Vấn đề | Chặn phần nào | Quyết định của nhóm |
|---|---|---|---|
| OI-10 | Danh sách 5–8 lĩnh vực đưa vào corpus. Claude Code xuất EDA theo lĩnh vực; **nhóm chọn**, ghi vào config và Changelog, sau đó freeze. Claude Code không được tự chọn. | Lọc dữ liệu, split, mọi bước sau | **Đã chốt 2026-10-22.** Loại văn bản: `Luật`, `Nghị định`, `Thông tư`; hiệu lực: `Còn hiệu lực`. 8 lĩnh vực, khớp **nguyên chuỗi** `linh_vuc` (không tách dấu phẩy/chấm phẩy, không khớp chuỗi con, không gộp tên gần nghĩa; `Chưa phân loại` và null bị loại; không dùng `nganh`): `Quản lý ngân sách`; `Quản lý thuế, phí và lệ phí`; `Lao động, tiền lương, tiền công`; `Chính sách thuế`; `Ngân sách nhà nước`; `Tài chính hành chính sự nghiệp`; `TCNH và thị trường TC, trái phiếu, khác`; `Quản lý dịch vụ tài chính và các quỹ tài chính`. Lĩnh vực thứ 8 đồng hạng 69 văn bản với `Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước`; nhóm chọn theo thứ tự sắp xếp của `scripts/eda.py` (số văn bản giảm dần, hòa thì tên tăng dần theo mã Unicode). |

Cùng thời điểm đó, nhóm xác nhận ánh xạ từ tên loại quan hệ gốc trong `relationships` sang ba loại:

- sửa đổi;
- bổ sung;
- thay thế.

Đây không phải lựa chọn methodology mới, mà là bước ánh xạ dữ liệu cần người xác nhận.

**Ánh xạ đã chốt (2026-10-22):**

| Nhãn gốc | Loại |
|---|---|
| `Văn bản sửa đổi` | sửa đổi |
| `Văn bản được sửa đổi` | sửa đổi |
| `Sửa đổi, bổ sung` | sửa đổi (quy ước kỹ thuật; vẫn giữ nhãn gốc; vì cả hai loại đều nối họ nên chọn `sửa đổi` hay `bổ sung` không đổi kết nối) |
| `Văn bản bổ sung` | bổ sung |
| `Văn bản được bổ sung` | bổ sung |
| `Thay thế` | thay thế |

25 nhãn gốc còn lại không dùng để gom họ; không xóa khỏi dữ liệu gốc. Việc đưa thêm nhãn khác vào ba loại trên, hoặc thêm loại thứ tư, phải qua quy trình mục 0.

Quyết định liên quan đã chốt cùng đợt: cạnh có ID không có trong metadata (mục 3.6, 4.1) và phạm vi họ dùng để chia và phân tầng (mục 4.1).

OI-1 đến OI-9 đã chốt; xem Changelog.

---

# FINAL FROZEN DECISIONS

- Corpus: `th1nhng0/vietnamese-legal-documents`, ghim revision; Luật, Nghị định, Thông tư còn hiệu lực; 5–8 lĩnh vực sau OI-10; loại phụ lục.
- Đơn vị truy hồi, gán nhãn và metric = **Điều**.
- Chunk `≤ 450 token` theo tokenizer E5.
- Điều dài tách theo Khoản → câu → cửa sổ token (chồng lấn 50 token) nếu một câu vượt 450 token.
- Score Điều = MaxP.
- Prefix chunk: `Tên văn bản › Điều X. Tiêu đề › ...`.
- Split 80/10/10 theo **họ văn bản** gom bằng union-find trên quan hệ sửa đổi, bổ sung, thay thế; phân tầng theo lĩnh vực; seed cố định.
- Union-find chạy trên **toàn bộ dataset trước khi lọc**, sau đó giới hạn về corpus.
- Không đổi split sau khi có query test.
- Exact-hash overlap giữa split = 0.
- Index chứa toàn corpus; query train và hard negative chỉ lấy từ train.
- Train khoảng 5.000 cặp do LLM sinh.
- Val 150 query.
- Test 150 query = 50 natural + 50 scenario + 50 keyword.
- OOD khoảng 40 câu do người viết, không dùng LLM.
- Query copy nguyên văn từ 8 âm tiết liên tiếp trở lên bị loại khỏi mọi tập.
- High-overlap filter cho train = 0,8.
- Variant `no_diacritic` và `typo` chỉ từ test, dùng chung qrels, không vào train và không vào pool.
- S1 BM25: `k1`, `b` tune trên val.
- S2 e5 zero-shot.
- S3 e5 fine-tune A: in-batch negative.
- S4 e5 fine-tune B: in-batch + 1 hard negative.
- S5 RRF: S1 + dense tốt hơn trên val; `k = 60`, cố định, không tune.
- E5:
  - `query: `;
  - `passage: `;
  - áp dụng đúng một lần;
  - `max_length = 512`;
  - mean pooling;
  - L2 normalization;
  - float32;
  - exact search;
  - không truncate passage âm thầm.
- Manifest bắt buộc cạnh index; mismatch thì fail.
- Training:
  - MNRL;
  - `NO_DUPLICATES`;
  - một seed;
  - LR tune trên A với `{1e-5, 3e-5}`;
  - tối đa 2 epoch;
  - B dùng nguyên LR của A;
  - A/B chỉ khác hard negative;
  - checkpoint chọn bằng NDCG@10 val.
- Hard-negative candidate window = rank 3–30.
- Incremental pooling depth = 10.
- Mọi main-table system phải vào pool trước freeze qrels.
- Human annotation:
  - label 0/1/2;
  - blind;
  - mỗi query một annotator chính;
  - calibration 20 cặp;
  - double annotation 15%;
  - anchor pairs 5%;
  - human chấm **toàn bộ final pool**;
  - LLM chỉ dùng để đo agreement.
- Main binary relevance threshold = `label ≥ 1`.
- Sensitivity appendix = `label = 2`.
- Statistical testing:
  - Fisher randomization/permutation test cho NDCG@10;
  - 10.000 permutations;
  - 4 pairwise comparisons: S1–S2, S2–S3, S3–S4, dense tốt hơn trên val – S5;
  - Holm áp dụng riêng cho test gốc và OOD;
  - raw p-values từ test implementation;
  - Holm correction thực hiện riêng bằng implementation phù hợp, ví dụ `statsmodels`;
  - không claim Holm có sẵn trong `ranx`.
- Test/OOD performance chỉ đánh giá chính thức sau freeze qrels; trước đó chỉ integrity check.
- Lưu run file và per-query metrics.
- Báo cáo `judged@10`.
- Recall = relative recall theo pooled qrels, không exhaustive recall.
- Error-analysis win threshold = `ΔNDCG@10 ≥ 0,3`.
- Duplicate representative = `article_id` nhỏ nhất theo thứ tự chuỗi; lưu `duplicate_article_ids`; không mang ý nghĩa pháp lý.
- App dùng chung retriever, index và manifest loader với evaluation.

---

# Changelog

| Ngày | Thay đổi | Lý do | Ảnh hưởng | Người duyệt |
|---|---|---|---|---|
| 2026-10-22 | OI-1: chia theo họ văn bản bằng union-find + loại trùng hash | Chống leakage giữa văn bản gốc và văn bản sửa đổi | Mục 3–4 | Nhóm |
| 2026-10-22 | OI-2: tune learning rate trên A, B dùng nguyên giá trị đó | Ablation A–B chỉ khác hard negative | Mục 2, 8 | Nhóm |
| 2026-10-22 | OI-3: S5 RRF vào bảng chính | Hybrid là hệ thống so sánh chính thức | Mục 7, 9, 14 | Nhóm |
| 2026-10-22 | OI-4: người chấm toàn bộ pool | Qrels cuối hoàn toàn do người quyết định | Mục 9, 10 | Nhóm |
| 2026-10-22 | OI-5: ngưỡng ≥ 1 cho bảng chính, = 2 ở phụ lục | Không trộn ngưỡng trong bảng chính | Mục 11 | Nhóm |
| 2026-10-22 | OI-6: kiểm định Fisher randomization cho 4 cặp, Holm correction tách riêng | Kết luận có kiểm định và kiểm soát multiple comparisons | Mục 11 | Nhóm |
| 2026-10-22 | OI-7: tune BM25 trên val | Baseline công bằng với dense | Mục 7 | Nhóm |
| 2026-10-22 | OI-8: đóng băng các ngưỡng số | Cố định trước khi chạy | Mục 5, 8, 12 | Nhóm |
| 2026-10-22 | OI-9: canonical duplicate = `article_id` nhỏ nhất | Dedup thuần kỹ thuật, không mang ý nghĩa pháp lý | Mục 3 | Nhóm |
| 2026-10-22 | Test 150 = 50 natural + 50 scenario + 50 keyword | Cấu trúc test cuối | Mục 5 | Nhóm |
| 2026-10-22 | RRF `k = 60`, cố định | Giảm thêm một bước tune, giữ cấu hình fusion cố định | Mục 7, 9 | Nhóm |
| 2026-10-22 | Union-find chạy trên dataset gốc trước khi lọc | Cách gom họ bảo thủ hơn về leakage | Mục 4 | Nhóm |
| 2026-10-22 | Holm correction thực hiện tách khỏi `ranx` nếu thư viện không hỗ trợ trực tiếp | Tránh claim sai về implementation | Mục 11 | Nhóm |
| 2026-10-22 | Cặp kiểm định thứ tư đổi từ S4–S5 thành (dense tốt hơn trên val)–S5 | So sánh RRF với đúng thành phần dense của nó | Mục 11 | Nhóm |
| 2026-10-22 | Holm áp dụng riêng cho test gốc và OOD | Làm rõ phạm vi hiệu chỉnh | Mục 11 | Nhóm |
| 2026-10-22 | Thêm quy tắc cắt câu > 450 token (cửa sổ token, chồng lấn 50) | Lấp lỗ hổng chunking với câu liệt kê dài | Mục 3 | Nhóm |
| 2026-10-22 | `validate_data` chạy trước split; kiểm tra chép nguyên văn chạy lại sau khi sửa query | Làm rõ thứ tự pipeline | Mục 3, 5 | Nhóm |
| 2026-10-22 | Đo tốc độ chấm ở vòng hiệu chỉnh; điều chỉnh quy mô chỉ trước pool v1 | Kiểm soát khối lượng chấm toàn bộ pool | Mục 10 | Nhóm |
| 2026-10-22 | Thêm danh sách hạn chế bắt buộc nêu trong paper; bỏ hai mục cuối trùng lặp | Gọn source of truth | Mục 1 | Nhóm |
| 2026-10-22 | OI-10: chốt loại văn bản, hiệu lực, 8 lĩnh vực (khớp nguyên chuỗi), ánh xạ 6 nhãn quan hệ | Hoàn tất bước dữ liệu sau EDA | Mục 3.2, 4.1, 17; `configs/data.yaml` | Nhóm |
| 2026-10-22 | Mục 3.6: cạnh có ID không có trong metadata không làm `validate_data` thất bại; ID giữ làm nút trung gian, không tính vào corpus; báo tỷ lệ cạnh không ánh xạ trên toàn bộ cạnh và riêng nhãn thuộc ánh xạ | SPEC trước đó chưa quy định cách xử lý; chọn cách bảo thủ về leakage | Mục 3.6, 4.1 | Nhóm |
| 2026-10-22 | Mục 4.1: chỉ chia các họ có văn bản trong corpus cuối cùng; lĩnh vực chủ đạo đếm trên văn bản trong corpus của họ; chỉ báo kích thước họ, không tự đặt ngưỡng | SPEC trước đó chưa rõ tập họ và phạm vi đếm lĩnh vực | Mục 4.1 | Nhóm |
| 2026-10-22 | Làm rõ ngoại lệ ID thiếu metadata: chỉ áp dụng cho `other_doc_id` khác null/rỗng; `doc_id` nguồn thiếu và ID null/rỗng vẫn là lỗi; mỗi ID là một nút riêng | Tránh code vô tình cho phép cả hai đầu hoặc gộp ID null thành một nút | Mục 3.6, 4.1 | Nhóm |
