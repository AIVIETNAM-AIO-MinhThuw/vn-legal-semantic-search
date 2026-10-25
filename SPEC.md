# FINAL FROZEN METHODOLOGY SPEC  
## Tìm kiếm ngữ nghĩa văn bản pháp luật (Đề tài 8)

**Ngày chốt:** 2026-10-22  
**Cập nhật quy trình dữ liệu, nhãn và split:** 2026-10-25 (xem Changelog)

---

# 0. Cách dùng tài liệu

Tài liệu này là **nguồn sự thật duy nhất (source of truth)** về methodology của MVP. Mọi session Claude Code phải đọc tài liệu này trước khi viết hoặc sửa code.

- Từ **“phải”**, **“không được”**, **“chốt”** trong tài liệu là quy tắc cứng, không phải gợi ý.
- Giá trị số nằm trong `configs/*.yaml` và phải khớp với tài liệu này. Khi hai bên lệch nhau, tài liệu này thắng.
- Mục 17 liệt kê các vấn đề còn mở. Claude Code không được bắt đầu phần code phụ thuộc một vấn đề mở cho đến khi nhóm ghi quyết định vào mục đó.
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
- một dataset có nhãn gồm query do LLM sinh và nhãn relevance cấp Điều do LLM gán theo protocol cố định, có kiểm chứng bằng người trên mẫu pilot (mục 5, 9, 10);
- một tập OOD gồm câu hỏi do người viết, tách biệt với dataset tổng hợp (mục 6);
- năm hệ thống truy hồi chính (mục 7);
- phân tích lỗi theo đề bài;
- một ứng dụng Streamlit dùng chung retriever với phần đánh giá.

## Giới hạn claim

Báo cáo **không được claim**:

- mô hình tốt nhất cho legal retrieval nói chung;
- vượt các mô hình chuyên miền pháp luật, vì MVP không đánh giá mô hình chuyên miền;
- tổng quát hóa ra ngoài corpus đã lọc hoặc ra ngoài kiểu query trong tập OOD;
- recall tuyệt đối trên toàn corpus;
- kết quả ổn định giữa các seed, vì MVP chỉ chạy một seed cho mỗi cấu hình;
- nhãn của dataset là human gold, hoặc toàn bộ nhãn do người quyết định;
- điểm trên dataset tổng hợp tự chứng minh chất lượng với người dùng thật.

Dataset phải được mô tả đúng là **query tổng hợp do LLM sinh và nhãn do LLM gán, có kiểm chứng bằng người trên mẫu**.

Mọi kết luận phải dẫn về một con số trong bảng kết quả hoặc một ví dụ cụ thể.

## Hạn chế bắt buộc nêu trong mục Limitations của paper

- Nhãn của dataset do LLM gán, có thể có lỗi và thiên lệch của LLM. Mức đồng thuận với người chỉ được đo trên mẫu pilot (mục 10.4), không phải trên toàn dataset.
- Query được sinh và nhãn được gán bằng LLM (cùng LLM hoặc cùng phong cách LLM, theo cấu hình đã ghi). Mọi lựa chọn trên val (learning rate, checkpoint, tham số BM25, thành phần dense của RRF) và kết quả trên test có thể thiên về mô hình quen phong cách câu hỏi và cách đánh giá của LLM.
- Pool ứng viên chưa đầy đủ: Điều ngoài pool chưa được chấm và được coi là không liên quan khi tính metric (mục 9.4).
- Mức chồng lấn query, Điều, văn bản và họ văn bản giữa các split phụ thuộc protocol split chốt ở OI-12 (mục 4.2) và phải được báo cáo bằng số (mục 4.3).
- Điểm trên dataset này không tự chứng minh chất lượng với người dùng thật.
- In-batch negative có thể vô tình là Điều liên quan tới query khác trong batch.
- OOD chỉ khoảng 40 câu, trừ các câu không trả lời được; kiểm định thống kê trên OOD có độ mạnh thấp và phải diễn giải thận trọng.
- Không xử lý trùng lặp gần giống (mục 3.6).
- Recall@k là recall tương đối theo pooled qrels (mục 11.4).
- Mỗi cấu hình chỉ chạy một seed.

---

# 2. Research questions

- **RQ1.** Fine-tune `multilingual-e5-base` bằng cặp `(query, Điều positive)` lấy từ phần train của dataset tổng hợp (query do LLM sinh, nhãn do LLM gán) có cải thiện NDCG@10 và MRR@10 so với e5 zero-shot và BM25 trên phần test của dataset không?

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

## 3.6 Kiểm tra và loại trùng bắt buộc trước sinh query

Script `validate_data` chạy **sau khi parse và chunk, trước mọi bước sinh query** (và do đó trước gán nhãn, split và train). Script phải dừng với lỗi nếu một kiểm tra thất bại:

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
- **Claude Code phải dừng, báo cáo các con số này và chờ người xác nhận trước khi dùng đồ thị quan hệ để gom họ văn bản (mục 4.1)**; không tự chuyển sang phương án khác dù tỷ lệ lỗi cao;
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

# 4. Họ văn bản và split dataset

Split được thực hiện **sau khi** dataset có nhãn đã được tạo và kiểm tra (mục 10.5), trên các query của dataset. Không chia corpus trước rồi sinh query riêng theo từng split. Index truy hồi luôn chứa toàn bộ corpus.

## 4.1 Họ văn bản

Họ văn bản (`group_id`) dùng để truy vết, kiểm tra chồng lấn giữa các split, loại ứng viên hard negative (mục 8.3) và, nếu OI-12 chọn phương án (b), làm đơn vị chia (mục 4.2).

- Họ văn bản được gom bằng **union-find** trên đồ thị quan hệ của `relationships`.
- Chỉ các cạnh thuộc loại **sửa đổi, bổ sung, thay thế** được dùng.
- Ánh xạ từ tên loại quan hệ gốc sang ba loại này được nhóm xác nhận sau EDA (mục 17) và ghi trong config.
- Union-find chạy trên **toàn bộ dataset trước khi lọc**, sau đó mới giới hạn về các văn bản có trong corpus.
- Vì vậy hai văn bản trong corpus nối với nhau qua một văn bản đã bị lọc vẫn thuộc cùng họ.
- Văn bản không có cạnh nào là một họ riêng.
- Cạnh có `other_doc_id` là ID khác null/rỗng nhưng không có trong metadata vẫn được dùng (ngoại lệ ở mục 3.6 chỉ áp dụng cho đầu `other_doc_id`; `doc_id` nguồn phải tồn tại trong metadata): ID đó là nút trung gian, mỗi giá trị ID là một nút riêng, và có thể nối hai văn bản trong corpus vào cùng họ. Nút này không phải văn bản, không thuộc corpus, không tính khi đếm lĩnh vực hay số văn bản của họ (OI-10).
- Chỉ các họ có ít nhất một văn bản trong corpus cuối cùng (sau bộ lọc mục 3.2 và sau parse/`validate_data`) được dùng; lĩnh vực chủ đạo của họ đếm **chỉ trên các văn bản thuộc corpus cuối cùng của họ**, hòa thì chọn lĩnh vực đứng trước theo thứ tự chữ cái.
- Nếu union-find gặp vấn đề như tỷ lệ cạnh không ánh xạ cao, dữ liệu quan hệ hỏng hoặc họ quá lớn, Claude Code **không được tự đổi cách gom họ**, không bỏ cạnh, không tự đặt ngưỡng cắt họ. Phải báo lại theo quy trình thay đổi ở mục 0.

**Artifact lịch sử.** `data/splits.json` (mốc 2 trong `data/FROZEN.md`, freeze ngày 2026-10-24) được tạo theo quy trình cũ: chia họ văn bản 80/10/10 trước khi sinh query. Quy trình đó đã bị thay thế ngày 2026-10-25 (Changelog). File được giữ nguyên làm bằng chứng lịch sử. File **không** phải split của dataset, không quyết định Điều nào được dùng để sinh query và không giới hạn index. `group_id` dùng cho truy vết được tính bằng cùng quy tắc và code gom họ, không đọc nhãn split trong file này.

## 4.2 Split dataset có nhãn

Điều kiện bắt đầu:

- dataset có nhãn đã qua kiểm tra ở mục 10.5 và đã đóng băng (mốc 5, mục 15);
- OI-12 đã được nhóm chốt (mục 17).

Trước khi OI-12 được chốt, không được chạy split, tạo dữ liệu training hoặc tune trên val.

Quy tắc:

- Không chia ngẫu nhiên từng dòng `(query, article, label)`.
- Mọi ứng viên và nhãn của cùng một `query_id` nằm cùng một split.
- Query trùng hoặc diễn đạt lại nhau được gom vào cùng `dup_group_id` (mục 5.4) trước khi chia; cả nhóm nằm cùng một split.
- Mỗi query giữ truy vết tới Điều nguồn, văn bản nguồn và họ văn bản nguồn (`source_article_id`, `source_doc_id`, `source_group_id`) để kiểm tra chồng lấn.
- Không nối các query với nhau chỉ vì chung một Điều được chấm 0 hoặc chung một Điều chưa chấm. Negative không tạo liên kết khi gom nhóm để chia.
- Tỷ lệ mục tiêu giữ như hiện hành: **80% train, 10% val, 10% test**. Đơn vị đếm tỷ lệ là đơn vị chia do OI-12 quyết định.
- Phân tầng theo lĩnh vực của văn bản nguồn. Seed toàn dự án `42`, ghi trong `configs/data.yaml`.
- Split được chốt **một lần**: ghi seed, mapping (đơn vị chia → split và `query_id` → split) và SHA-256 vào `data/FROZEN.md`. Không chia lại hoặc đổi split để cải thiện metric.
- Train chỉ dùng query và nhãn của train. Val chỉ dùng để chọn cấu hình. Test chỉ dùng cho đánh giá cuối (mục 11.1).

### Phụ thuộc OI-12

OI-12 quyết định dataset đo khả năng nào:

| Phương án | Đơn vị chia | Hệ quả cho split và kết luận | Hệ quả cho dữ liệu training |
|---|---|---|---|
| (a) Query mới trên corpus cố định | `dup_group_id` (nhóm query sau khi gom trùng/diễn đạt lại) | Một Điều, văn bản hoặc họ có thể là positive của query ở cả train và test. Kết luận chỉ nói về query mới trên corpus đã thấy khi huấn luyện. | Điều positive của query val/test có thể xuất hiện trong training qua query khác, kể cả làm hard negative. Tỷ lệ chồng lấn Điều, văn bản và họ giữa các split phải được báo cáo. |
| (b) Tổng quát hóa sang họ văn bản chưa gặp | `source_group_id`: mọi query có Điều nguồn thuộc cùng họ nằm cùng split | Kết luận nói về họ văn bản chưa gặp khi huấn luyện. Tỷ lệ 80/10/10 tính theo số họ hay số query phải ghi khi chốt OI-12. | Training không dùng Điều thuộc họ của val/test làm positive hoặc hard negative. Cặp train có positive thuộc họ val/test bị loại khỏi training và ghi log. |

Với phương án (b):

- Query có Điều nhãn `≥ 1` thuộc nhiều họ được gán theo họ của Điều nguồn. Không nối các họ lại với nhau qua positive. Positive thuộc họ của split khác vẫn giữ trong nhãn của query; số trường hợp được báo cáo theo từng cặp split.
- Nếu một họ chiếm tỷ lệ query lớn tới mức không đạt tỷ lệ mục tiêu trong phạm vi sai lệch ghi khi chốt OI-12, Claude Code dừng, báo phân phối kích thước họ theo số query và chờ người quyết định. Không tự cắt họ, bỏ cạnh hay đổi đơn vị chia.

## 4.3 Kiểm tra chồng lấn bắt buộc

Script `check_leakage` chạy sau split và dừng với lỗi nếu:

- một `query_id` xuất hiện ở hơn một split;
- một `dup_group_id` xuất hiện ở hơn một split;
- với phương án (b) của OI-12: một `source_group_id` xuất hiện ở hơn một split, hoặc dữ liệu training chứa Điều thuộc họ của val/test.

Script xuất ra file, theo từng cặp split:

- số và tỷ lệ Điều nguồn, văn bản nguồn, họ nguồn dùng chung;
- số và tỷ lệ Điều có nhãn `≥ 1` dùng chung;
- số Điều dùng trong training trùng hash nội dung với Điều nguồn hoặc Điều positive của val/test.

Con người xác nhận các con số này, không chỉ dựa vào thông báo “không có leakage” của script.

---

# 5. Query generation

## 5.1 Đầu vào và bộ sinh

### Đầu vào

- Nguồn dữ liệu là ba file processed hiện có: `data/processed/docs_index.jsonl`, `data/processed/articles_index.jsonl`, `data/processed/chunks_index.jsonl`.
- Đầu vào sinh query dựng từ **nội dung Điều** (`articles_index.jsonl`) và **metadata văn bản** (`docs_index.jsonl`): tên văn bản, loại, lĩnh vực, số và tiêu đề Điều. Chunk chỉ phục vụ truy hồi và encode; không gửi lặp lại nội dung chunk đã có trong Điều.
- Điều nguồn được chọn từ **toàn bộ corpus**, không giới hạn theo split. Cách chọn Điều nguồn và quy mô sinh hàng loạt ghi trong config theo quyết định ở OI-13.
- Loại trước khi sinh các Điều có tiêu đề thuộc nhóm thi hành:
  - “Hiệu lực thi hành”;
  - “Trách nhiệm thi hành”;
  - “Điều khoản thi hành”;
  - “Tổ chức thực hiện”.
- Chia lô theo giới hạn của API; không yêu cầu đưa toàn bộ ba file vào một request. Kích thước lô ghi trong config.
- Không cắt nội dung Điều âm thầm. Điều vượt giới hạn đầu vào của model được ghi log và đánh dấu `context_incomplete`; cách xử lý (bỏ qua, hoặc gửi kèm cờ không đầy đủ) ghi trong config.

### Bộ sinh

- LLM: Gemini qua API free tier.
- Tên model chính xác, version, temperature, version prompt và thời điểm sinh ghi vào config và provenance của đầu ra (mục 10.6).
- Prompt là một file có version trong `prompts/`. Sửa prompt nghĩa là tăng version.
- LLM trả JSON theo schema cố định (mục 5.4). Mỗi query có `query_id` ổn định và `source_article_id` của Điều nguồn để truy vết.
- **Điều nguồn không mặc định là positive và không mặc định có nhãn 2.** Điều nguồn chỉ có nhãn khi nằm trong pool và được gán nhãn như mọi ứng viên khác (mục 9.1, 10).
- Script phải resume được sau khi bị ngắt:
  - ghi JSONL tăng dần;
  - bỏ qua Điều nguồn đã xử lý theo khóa ổn định;
  - tự retry khi gặp rate limit;
  - không tạo bản ghi trùng.
- Sinh bằng LLM không tái lập được từng bit. File query đã sinh, cùng đầu vào và đầu ra thô, là artifact gốc, được lưu và version hóa.
- Mọi bước sau bắt đầu từ file này, không gọi lại LLM để sinh lại query.

## 5.2 Kiểu query

Với mỗi Điều nguồn, bộ sinh tạo đúng ba query:

- `natural`: câu hỏi của người dân bằng ngôn ngữ tự nhiên;
- `scenario`: mô tả một tình huống cụ thể mà Điều trả lời được;
- `keyword`: 1–4 từ, như gõ vào ô tìm kiếm.

Query được dùng thuật ngữ pháp lý khi đó là cách diễn đạt tự nhiên. Không yêu cầu bộ sinh tránh từ ngữ của Điều để đạt độ trùng từ vựng thấp.

Prompt cấm:

- chép nguyên câu từ Điều;
- nhắc số hiệu Điều;
- nhắc số hiệu văn bản.

Bộ sinh trả cờ `skip` cho Điều không đặt câu hỏi được. Số Điều bị skip được ghi log.

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

- **Chép nguyên văn:** query chứa một chuỗi liên tiếp từ **N = 8 âm tiết** trở lên lấy nguyên từ Điều nguồn. Query chép nguyên văn bị loại khỏi mọi tập (mục 5.4).
- Overlap **chỉ dùng để phân tích** (mục 11.5). Overlap không được dùng để quyết định sinh, giữ, loại hay chia query ở bất kỳ tập nào. Không có ngưỡng lọc overlap.

## 5.4 Kiểm soát chất lượng, schema và đóng băng query

Kiểm tra tự động trước khi query vào pool (mục 9.1). Mọi query bị loại hoặc đánh dấu đều có dòng log kèm lý do:

- query chép nguyên văn (mục 5.3): loại;
- query rỗng, sai schema, nhắc số hiệu Điều hoặc số hiệu văn bản: loại;
- query trùng chính xác sau chuẩn hóa (NFC, chữ thường, tách âm tiết như mục 5.3): gộp, giữ một bản;
- query trùng ý hoặc diễn đạt lại nhau: gom vào cùng `dup_group_id`. Cách phát hiện trùng ý ghi trong config trước khi split (OI-13);
- query vô nghĩa hoặc không phải câu hỏi về nội dung pháp luật: gắn `query_issue` (bởi kiểm tra tự động, LLM gán nhãn hoặc người kiểm chứng) và không vào dataset cho tới khi được giải quyết (mục 10.5).

Không sửa câu chữ query tổng hợp. Query có vấn đề bị loại hoặc đánh dấu, có log.

Schema tối thiểu của một query:

| Trường | Ý nghĩa |
|---|---|
| `query_id` | ID ổn định, không đổi khi chạy lại hoặc resume |
| `text` | Câu chữ query |
| `query_type` | `natural`, `scenario`, `keyword` |
| `origin` | `synthetic` (dataset) hoặc `ood_human` (mục 6) |
| `source_article_id`, `source_doc_id`, `source_group_id` | Truy vết Điều, văn bản, họ nguồn; rỗng với OOD |
| `dup_group_id` | Nhóm trùng/diễn đạt lại |
| `status` | `accepted`, `rejected`, `query_issue` |
| `reject_reason` | Lý do khi bị loại hoặc đánh dấu |
| `gen_run_id` | Trỏ tới provenance của lần sinh (mục 10.6) |

### Đóng băng

- File query tổng hợp đã qua kiểm tra tự động được ghi SHA-256 vào `data/FROZEN.md` trước khi tạo pool (mốc 4, mục 15).
- `queries_ood.jsonl` được ghi hash theo mục 6.
- Sau thời điểm này không sửa nội dung query.
- Người kiểm chứng hoặc LLM gán nhãn phát hiện query có vấn đề chỉ đánh dấu `query_issue`, không sửa.

## 5.5 Biến thể của tập test

Chỉ sinh từ query gốc thuộc split test của dataset, sau khi split đã đóng băng, bằng quy tắc xác định, seed cố định. Không sinh từ OOD.

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
   - OOD đi qua pooling như test (mục 9.2).
   - Nguồn nhãn của OOD chưa chốt (OI-16). Trước khi chốt, không gán nhãn OOD.
   - Nếu sau khi gán nhãn, pool không có Điều nào có nhãn 1 hoặc 2, người viết tìm thủ công trong corpus bằng công cụ tìm kiếm của dự án.
   - Giới hạn 10 phút mỗi câu.
   - Điều tìm được thêm vào qrels với nhãn do người quyết định, `label_source = human_manual` và cờ `found_manually = true`.

4. **Câu không trả lời được**
   - Nếu vẫn không có Điều liên quan, query được đánh dấu `unanswerable`.
   - Loại khỏi mọi metric.
   - Báo cáo số lượng và tỷ lệ bị loại.

Query test không có Điều nào được chấm từ 1 trở lên sau pool cuối được xử lý theo mục 10.5 (`no_positive_in_pool`): không mặc nhiên coi là không trả lời được, loại khỏi metric và được báo cáo.

OOD:

- là câu hỏi do người viết, **không** thuộc dataset tổng hợp; không qua split, không được báo cáo gộp với test;
- không có biến thể;
- không dùng để tune;
- chỉ chạy cùng test trong lần đánh giá cuối.

---

# 7. Systems

## 7.1 Các hệ thống trong bảng kết quả chính

| ID | Hệ thống | Ghi chú |
|---|---|---|
| S1 | BM25 | Thư viện `bm25s`. VNCoreNLP tách từ, chỉ dùng word unigram (`ngram_range = (1, 1)`), chữ thường, giữ dấu; protocol ở mục 7.1.1. Không dùng bộ tách âm tiết ở mục 5.3 cho BM25. `k1` và `b` chọn trên val theo mục 7.5. Cấu hình BM25 dùng để tạo dataset (S1₀) là cấu hình riêng, cố định trước khi tạo nhãn (mục 7.5). |
| S2 | `multilingual-e5-base` zero-shot | `intfloat/multilingual-e5-base`, không huấn luyện thêm. |
| S3 | E5 fine-tune, in-batch negative, cấu hình A | Mục 8. |
| S4 | E5 fine-tune, in-batch + hard negative, cấu hình B | Mục 8. |
| S5 | Hybrid RRF | Reciprocal Rank Fusion của S1 và checkpoint dense có NDCG@10 trên val cao hơn giữa S3 và S4. `k = 60`, cố định, không tune. Trộn top-100 Điều của mỗi thành phần. |

Không có hệ thống nào khác trong bảng chính.

Muốn thêm hệ thống phải theo quy trình thay đổi ở mục 0 và phải thêm hệ thống đó vào pool trước khi đóng băng qrels.

### 7.1.1 Tiền xử lý BM25 — S1₀ và S1

- Dùng `bm25s`; VNCoreNLP chỉ bật word segmentation. Không dùng POS, NER hoặc dependency parsing.
- Corpus và query đi qua cùng một pipeline: Unicode NFC, gộp khoảng trắng/bỏ khoảng trắng đầu cuối → VNCoreNLP trên văn bản còn chữ hoa → hạ chữ thường các token → bỏ token chỉ chứa dấu câu.
- Giữ dấu tiếng Việt, chữ số, từ phủ định và stopword; không stemming, không mở rộng từ đồng nghĩa. Giữ nguyên token từ ghép do VNCoreNLP trả về, không tách lại ở dấu `_`.
- Chỉ dùng unigram sau tách từ; không thêm bigram hay n-gram bậc cao. Đổi cách tạo token phải qua mục 0, xây lại index và ghi provenance; không tự tune n-gram trong bản baseline này.
- Dùng `normalize_query` chung (mục 7.3) đúng một lần trước bước tách từ; việc hạ chữ thường và segmentation chỉ nằm trong nhánh BM25. Corpus/query gốc không bị ghi đè.
- Index trên chunk với tiền tố văn bản ở mục 3.4; không thêm `query: ` hoặc `passage: ` cho BM25. Truy hồi và MaxP theo mục 7.2.
- Khởi tạo VNCoreNLP một lần mỗi tiến trình; chỉ tách corpus khi xây index. Thiếu Java/model hoặc tách từ lỗi phải báo lỗi, không âm thầm chuyển sang tách âm tiết.
- Phiên bản `bm25s`, wrapper VNCoreNLP, Java, checksum JAR/model và biến thể công thức BM25 phải được ghi rõ khi triển khai, trước khi chạy pool; không phụ thuộc mặc định trôi nổi của thư viện.
- Kiểm thử cần bảo vệ: query/corpus cùng pipeline; từ ghép, dấu, chữ số và phủ định được giữ; không sinh bigram; MaxP, thứ tự hòa điểm và kết quả sau lưu/nạp index ổn định.

Bộ tách âm tiết ở mục 5.3 chỉ phục vụ kiểm tra query và phân tích; tokenizer E5 ở mục 7.3 là pipeline riêng. Các giới hạn chunk vẫn đo bằng tokenizer E5, không đếm bằng token VNCoreNLP.

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
- **Thứ tự khi hòa điểm** là cố định ở cả hai cấp. Cấp chunk (top-200): điểm giảm dần, rồi `article_id` tăng dần, rồi chỉ số chunk trong Điều tăng dần. Cấp Điều (sau MaxP): điểm giảm dần, rồi `article_id` tăng dần. `article_id` so sánh dưới dạng chuỗi theo thứ tự từ điển. Mọi retriever dùng chung một hàm sắp xếp này.
- **Kiểu số khi suy luận:** mọi lần encode phục vụ đánh giá, pooling, API và highlight dùng **fp32**, kể cả khi checkpoint được huấn luyện bằng fp16 (mục 8.1).

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
- E5 nhận văn bản tự nhiên trước segmentation, không nhận token/chuỗi nối `_` do VNCoreNLP sinh, không dùng word n-gram hoặc bước hạ chữ thường của BM25. Quy tắc này áp dụng cho query và passage của S2/S3/S4; giữ prefix và tokenizer riêng của E5;
- `max_length = 512` cho cả query và passage;
- passage sau khi thêm `passage: ` phải `≤ 512 token`;
- nếu vượt thì báo lỗi, không được cắt âm thầm;
- pooling: mean pooling theo attention mask;
- embedding chuẩn hóa L2.
- **Chuẩn hóa query** nằm trong một hàm duy nhất `normalize_query`: Unicode NFC, gộp khoảng trắng liên tiếp, bỏ khoảng trắng đầu cuối. Không hạ chữ thường, không bỏ dấu. Hàm này chạy **trước** khi gắn prefix `query: ` và được dùng chung cho đánh giá, API và highlight. Không được gọi `normalize_query` hai lần trên cùng một query.

Unit test bắt buộc:

- prefix không bị gắn hai lần;
- chuẩn embedding xấp xỉ 1;
- cùng một văn bản encode hai lần cho cùng kết quả.

## 7.4 Manifest

Mỗi index BM25 và dense có `manifest.json` bên cạnh, gồm ít nhất:

- tên và revision model/checkpoint;
- tên tokenizer;
- phiên bản các thư viện `transformers`, `tokenizers`, `sentence-transformers`, `torch`;
- `max_length`;
- prefix query và passage;
- kiểu pooling;
- có chuẩn hóa hay không;
- số chiều embedding;
- kiểu dữ liệu lưu;
- version tiền xử lý;
- hash file chunk;
- số chunk;
- với BM25: `k1`, `b`, biến thể công thức BM25, phiên bản `bm25s`, pipeline chuẩn hóa/tách từ, `ngram_range = (1, 1)`, chính sách dấu câu/stopword, phiên bản wrapper VNCoreNLP và Java, checksum JAR/model segmentation. Các trường model/embedding chỉ áp dụng cho dense; dependency tokenizer E5 dùng để chuẩn bị chunk được ghi riêng với vai trò preprocessing, không coi là tokenizer truy hồi BM25.

Khi nạp index, code so manifest với config đang chạy.

Bất kỳ trường nào không khớp thì **dừng với lỗi**.

Đánh giá và app dùng chung hàm nạp index và kiểm tra manifest.

Khi nạp index dense, phiên bản `transformers`, `tokenizers`, `sentence-transformers` đang chạy phải **trùng chính xác** với manifest. Với `torch`, so phần phiên bản chính và bỏ hậu tố biến thể (`+cpu`, `+cu121`). Lệch thì dừng với lỗi. File requirements của huấn luyện và của `api` phải ghim **cùng** phiên bản cho bốn thư viện này.

## 7.5 Tham số BM25

### BM25 tạo dataset (S1₀)

- Dùng trong pool tạo dataset (mục 9.1) và pool v1 của test/OOD (mục 9.2).
- Cùng thư viện và cách token hóa với S1.
- Biến thể triển khai: `lucene` của `bm25s`, backend NumPy, điểm float32. Với mỗi token query, `IDF = ln(1 + (N - df + 0.5)/(df + 0.5))`; đóng góp `IDF * tf / (tf + k1 * (1 - b + b * len/avgdl))`. `N`, `df`, `len`, `avgdl` tính trên chunk/token word unigram. Token lặp trong query được cộng lặp; token ngoài vocabulary đóng góp 0. Đây là công thức thư viện đã chọn, không nhân thêm `(k1+1)`.
- `k1`, `b` cố định **trước** khi chạy pool tạo dataset (kể cả pilot), ghi vào config và provenance. Không phụ thuộc val, vì val chưa tồn tại ở bước này.
- **Đã chốt OI-14 ngày 2026-10-25: `k1 = 1.2`, `b = 0.75`.** Đây là cấu hình khởi điểm tạo dataset, không phải kết quả tuning hoặc bằng chứng tối ưu. Khi triển khai, ghi vào config và manifest; không hard-code.
- Sau khi đã dùng để tạo pool, không đổi tham số S1₀.

### BM25 trong so sánh cuối (S1)

Giữ nguyên thư viện, biến thể công thức và VNCoreNLP + unigram như S1₀; chỉ tune `k1`, `b` trên val.

Lưới:

```text
k1 ∈ {0.9, 1.2, 1.5}
b  ∈ {0.4, 0.75}
```

- Tổng 6 tổ hợp.
- Chọn tổ hợp có NDCG@10 trên val cao nhất, sau khi split đã đóng băng.
- Tổ hợp được chọn ghi vào config và đóng băng.
- Không thay đổi dựa trên test.
- Kết quả cả 6 tổ hợp ghi vào `reports/bm25_tuning.csv`.
- Nếu tham số S1 khác S1₀, S1 phải đóng góp vào pool đánh giá trước khi đóng băng qrels (mục 9.2).

---

# 8. Training

## 8.1 Thiết lập chung cho cả hai cấu hình

- Thư viện `sentence-transformers`.
- Loss: `MultipleNegativesRankingLoss`.
- Khởi tạo từ `intfloat/multilingual-e5-base`.
- Quy tắc encode giống mục 7.3.
- Batch sampler: `NO_DUPLICATES`.
- Không để hai cặp có cùng Điều positive nằm chung một batch.
- Batch size giống nhau cho A và B.
- Batch size = giá trị lớn nhất cấu hình B chạy được trên T4 với fp16.
- Lý do: số negative trong batch ảnh hưởng trực tiếp tới MNRL, batch size khác nhau sẽ làm ablation bị nhiễu.
- `fp16`.
- Warmup = 10% số bước.
- Một seed cố định cho mọi lần chạy.
- Chỉ dùng query và nhãn thuộc split train của dataset (mục 4.2), cùng các ràng buộc của OI-12.

## 8.2 Hai cấu hình

### Cặp huấn luyện

- Điều positive là Điều có `final_label` đã chấp nhận (mục 10.5) đạt ngưỡng positive cho training. Ngưỡng này (`= 2` hay `≥ 1`) và cách dùng query có nhiều positive chưa chốt (OI-15).
- Không phải positive: Điều chưa chấm, Điều có bản ghi `needs_review` hoặc lỗi chưa giải quyết, và Điều nguồn khi chưa có nhãn đạt ngưỡng.
- Query không có positive (`no_positive_in_pool`, mục 10.5) không tạo cặp huấn luyện.

### Cấu hình A

- bộ đôi `(query, Điều positive)`;
- negative chỉ là các passage khác trong batch.

### Cấu hình B

- bộ ba `(query, Điều positive, 1 hard negative)`;
- mọi thiết lập khác giống A.

## 8.3 Đào hard negative — chỉ cho cấu hình B

Ứng viên lấy từ:

- S1 BM25 (tham số đã chốt trên val);
- S2 e5 zero-shot.

Retrieval chạy cho query train trên index, sau đó gộp về Điều. Phạm vi Điều được phép phụ thuộc OI-12: phương án (a) dùng toàn corpus; phương án (b) chỉ dùng Điều thuộc họ của split train.

Candidate window cố định:

```text
rank 3–30
```

Loại:

- Điều có nhãn `≥ 1`, hoặc có bản ghi `needs_review`/lỗi chưa giải quyết, với chính query đó;
- Điều nguồn;
- Điều cùng văn bản hoặc cùng `group_id` với Điều nguồn hoặc với một Điều positive của query;
- Điều có hash nội dung trùng Điều nguồn hoặc Điều positive.

Từ ứng viên còn lại, chọn ngẫu nhiên 1 theo seed. Điều đã chấm 0 và Điều chưa chấm trong window đều là ứng viên hợp lệ.

Kiểm tra false negative:

- một người đọc 30 bộ ba ngẫu nhiên;
- đánh dấu hard negative nào thật ra liên quan;
- báo cáo tỷ lệ.

Tuyệt đối không dùng:

- query, nhãn hoặc qrels của val, test, OOD;
- nhãn bổ sung của test/OOD từ pool đánh giá (mục 9.2);
- với phương án (b) của OI-12: Điều thuộc họ của val/test.

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
11. Sau khi qrels đóng băng, không huấn luyện lại, trừ khi thực hiện change procedure ở mục 0 và mở lại pool theo mục 9.5.

---

# 9. Pooling

Pool là union theo từng query của các cặp `(query_id, article_id)`, ở cấp Điều, độ sâu **10 Điều** cho mỗi hệ thống. Biến thể không tham gia pooling.

## 9.1 Pool tạo dataset

- Áp dụng cho mọi query tổng hợp đã qua kiểm tra và đóng băng (mục 5.4), **trước** split.
- Hai hệ thống: S1₀ (mục 7.5) và S2 e5 zero-shot, chưa fine-tune. Mỗi hệ thống lấy top-10 Điều sau MaxP (mục 7.2).
- Hợp nhất theo `(query_id, article_id)` và loại trùng.
- File pool lưu hệ thống, rank và score của từng ứng viên để truy vết. Các thông tin này không được gửi cho LLM gán nhãn hoặc người kiểm chứng (mục 10.2).
- Điều nguồn chỉ nằm trong pool khi được một trong hai hệ thống truy hồi. Không tự thêm Điều nguồn vào pool hay gán nhãn cho nó.
- Pool này cùng nhãn của nó tạo thành dataset ban đầu (mục 10.5). Với query test, đây là pool v1 của đánh giá (mục 9.2).

## 9.2 Pool bổ sung cho đánh giá cuối

Chỉ áp dụng cho query gốc của **test** và cho OOD. Val không mở rộng pool; Điều chưa chấm của val được coi là không liên quan và ảnh hưởng được đo bằng judged coverage.

| Phiên bản | Thêm vào pool | Điều kiện |
|---|---|---|
| v1 | top-10 của S1₀ và S2 | Test: pool tạo dataset (mục 9.1). OOD: câu hỏi đã đóng băng (mục 6). |
| v2 | top-10 của S1 | Tham số S1 đã chốt trên val; chỉ khi khác S1₀ |
| v3 | top-10 của S3 | Checkpoint A đã chọn trên val |
| v4 | top-10 của S4 | Checkpoint B đã chọn trên val |
| v5 | top-10 của S5 | S1 đã chốt tham số; checkpoint dense của RRF đã chọn trên val; chạy sau v4 |

Quy tắc:

- mỗi version chỉ xuất phần chênh lệch, tức các cặp chưa từng được chấm;
- mỗi version lưu thành file riêng, kèm danh sách hệ thống đã đóng góp;
- phần bổ sung được chấm theo cùng protocol, cùng version prompt và guideline đã đóng băng (mục 10);
- chỉ cấu hình đã chọn trên val mới đóng góp; các lần chạy thử không đóng góp;
- nhãn bổ sung của test và OOD **không** được đưa vào train, không dùng cho hard negative và không dùng để chọn cấu hình;
- không dùng việc mở rộng pool để tune trên test: không xem metric test trong quá trình này, không retrain và không đổi cấu hình sau khi thấy nhãn bổ sung;
- mỗi hệ thống đóng góp đúng một lần theo thứ tự trong bảng; không lặp vòng bổ sung nhãn → retrain → đánh giá.

## 9.3 Đóng băng qrels

Qrels của test và OOD chỉ được đóng băng khi:

- mọi hệ thống trong bảng kết quả chính đã đóng góp vào pool;
- mọi cặp trong pool có nhãn đã chấp nhận (mục 10.5). Cặp `needs_review` hoặc lỗi phải được giải quyết, hoặc cả query bị loại khỏi metric kèm log. Không tự gán 0.

Khi đóng băng:

- ghi hash SHA-256 của qrels vào `data/FROZEN.md`;
- ghi danh sách hệ thống trong pool, version prompt và guideline, phân phối `label_source`.

Metric hiệu năng chính thức trên test và OOD chỉ được tính sau bước này.

## 9.4 Cặp chưa được chấm

- Điều ngoài pool là **chưa chấm**. Không tạo nhãn 0 cho các Điều này trong dataset.
- Khi tính metric, Điều không có trong qrels được coi là không liên quan. Điều này áp dụng cho Điều ngoài pool và Điều mà biến thể truy hồi được nhưng query gốc không đưa vào pool.
- Phạm vi ảnh hưởng được đo bằng judged coverage (mục 11.4).

## 9.5 Sau khi đóng băng

Không:

- huấn luyện lại;
- thay checkpoint;
- thêm hệ thống vào bảng chính.

Nếu bắt buộc phải thay đổi:

1. theo quy trình mục 0;
2. tạo pool version mới;
3. chấm phần delta theo cùng protocol;
4. đóng băng lại qrels;
5. ghi vào Changelog.

---

# 10. Gán nhãn

## 10.1 Thang nhãn

| Nhãn | Ý nghĩa |
|---:|---|
| 2 | Điều trả lời trực tiếp và đầy đủ câu hỏi. |
| 1 | Điều liên quan và hữu ích nhưng không đủ để trả lời; thiếu điều kiện, chỉ một phần, hoặc cần thêm Điều khác. |
| 0 | Không liên quan hoặc chỉ trùng từ ngữ mà không giúp trả lời. |

Guideline đầy đủ nằm ở `annotation/GUIDELINE.md`, dùng chung cho prompt gán nhãn và người kiểm chứng.

Guideline có ít nhất 2 ví dụ cho mỗi nhãn. Ví dụ lấy từ query pilot (mục 10.4), không lấy từ val hoặc test.

Nhãn chỉ nhận giá trị 0, 1, 2. Trạng thái xử lý là trường riêng (mục 10.3). Không dùng một nhãn hợp lệ để biểu diễn lỗi hoặc thiếu căn cứ.

## 10.2 Che thông tin — blind

LLM gán nhãn và người kiểm chứng chỉ thấy:

- query;
- toàn văn Điều;
- tên văn bản;
- số Điều;
- tiêu đề.

LLM gán nhãn và người kiểm chứng không thấy:

- hệ thống nào đề xuất ứng viên;
- thứ hạng;
- điểm số;
- tên model truy hồi;
- số hệ thống cùng đề xuất ứng viên;
- ứng viên nào là Điều nguồn, hoặc bất kỳ dấu hiệu nào cho biết Điều nào đã sinh query;
- bất kỳ metric tạm thời nào.

Người kiểm chứng ngoài ra không thấy nhãn của LLM.

Ứng viên trong mỗi query được xáo trộn theo seed. Công cụ xuất dữ liệu phải bảo đảm việc blind ngay trong dữ liệu gửi cho LLM và cho người kiểm chứng.

## 10.3 Gán nhãn bằng LLM

- Gán nhãn qua API trực tiếp bằng **`gemini-3.5-flash-lite`** (đã chốt 2026-10-25); model và generation settings đọc từ config, key chỉ qua biến môi trường. Ghi requested model và model/version thực tế API trả về, temperature, version prompt trong provenance. Không tự fallback model. Prompt là file có version trong `prompts/`.
- Mỗi request gửi một query cùng nội dung các Điều ứng viên của nó, đã blind theo mục 10.2.
- Không cắt nội dung Điều âm thầm. Nếu không gửi được đầy đủ nội dung, judgment của cặp đó gắn `context_incomplete = true` và có `status = needs_review`.
- LLM trả kết quả theo schema cố định, một judgment cho mỗi ứng viên:

| Trường | Ý nghĩa |
|---|---|
| `query_id`, `article_id` | Khóa của cặp |
| `label` | 0, 1 hoặc 2 khi `status = labeled`; rỗng trong mọi trường hợp khác |
| `status` | `labeled`, `needs_review` (thiếu căn cứ để quyết định), `error` (lỗi kỹ thuật, sai schema) |
| `reason` | Lý do ngắn |
| `evidence` | Đoạn trích nguyên văn từ nội dung Điều làm căn cứ, khi có; rỗng nếu không có |
| `context_incomplete` | `true` khi nội dung gửi đi không đầy đủ |
| `query_issue` | `true` khi query vô nghĩa hoặc không đánh giá được |
| `label_run_id` | Trỏ tới provenance của lần gán nhãn (mục 10.6) |

- Thiếu căn cứ thì dùng `needs_review`, không ép thành nhãn 0.
- `evidence` phải là chuỗi có thật trong nội dung Điều. Script kiểm tra trích đoạn tồn tại nguyên văn; không khớp thì bản ghi chuyển `needs_review`. Không bịa trích dẫn.
- Nhãn LLM là nhãn sử dụng trong dataset, không phải nhãn nháp chờ người chấm toàn bộ.

## 10.4 Pilot và kiểm chứng bằng người

Trước khi sinh query và gán nhãn hàng loạt:

1. Chạy pilot trên một tập query pilot qua toàn bộ luồng: sinh query → pool (mục 9.1) → gán nhãn LLM.
2. **Đã chốt 2026-10-25:** pilot gồm **10 query**; sau khi LLM gán nhãn toàn pool, lấy mẫu người kiểm chứng **tối đa 30 cặp**, mục tiêu 10 cặp mỗi nhãn LLM 0/1/2. Trong từng nhóm nhãn, dùng seed cố định và ưu tiên độ phủ query, kiểu câu hỏi có thật trong đầu vào và lĩnh vực. Nếu một nhãn có ít hơn 10 cặp hợp lệ thì lấy toàn bộ số có và báo thiếu; không tự chuyển quota, tạo nhãn hoặc gọi LLM lại để đủ số. `needs_review`/`error` xử lý riêng, không coi là nhãn 0 và không dùng để lấp mẫu. Không tự sửa nội dung hay phân loại lại query để tạo độ phủ.
3. Người kiểm chứng chấm độc lập theo guideline, blind theo mục 10.2, không thấy nhãn LLM.
4. Báo cáo: tỷ lệ đồng ý thô và Cohen's kappa có trọng số tuyến tính giữa người và LLM, ma trận nhầm lẫn, các kiểu sai và số `needs_review`. Ghi rõ phân phối nhãn của pool và mẫu kiểm chứng: đây là mẫu cân bằng theo nhãn LLM để phát hiện lỗi; agreement/kappa trên mẫu không phải ước lượng tỷ lệ đúng toàn pool/dataset. Không tự ngoại suy. Khi không đủ điều kiện tính kappa, ghi undefined kèm lý do.
5. Bất đồng giữa người và LLM được một người thứ hai phân xử. Ghi cách xử lý từng loại bất đồng.
6. Nếu sửa prompt hoặc guideline sau pilot: tăng version, ghi lý do và kiểm tra lại trên mẫu pilot mới, không trên val hoặc test.

Quy tắc:

- Quy mô pilot (10 query), mẫu kiểm chứng (tối đa 30 cặp, mục tiêu 10/nhãn) đã chốt như trên. **Ngưỡng chấp nhận để chạy hàng loạt còn mở** (OI-13); không tự coi API thành công, schema hợp lệ hoặc hoàn tất 10 query là pilot đạt. Chưa được duyệt thì không sinh và gán nhãn hàng loạt.
- Không khẳng định tỷ lệ đúng của nhãn LLM khi chưa có kết quả kiểm chứng.
- Không yêu cầu người chấm lại toàn bộ dataset.
- Query pilot và query dùng làm ví dụ trong guideline không thuộc val hoặc test. Cách xử lý chúng khi split (đưa vào train hay loại khỏi dataset) ghi cùng quyết định OI-12.
- Không dùng lỗi hoặc metric trên test để sửa prompt hay guideline. Nếu điều này đã xảy ra, test không còn được coi là độc lập; phải ghi vào Changelog.
- Sau khi chốt, prompt gán nhãn và guideline được đóng băng (mốc 3, mục 15). Mọi thay đổi sau đó phải qua mục 0 và các nhãn bị ảnh hưởng phải được gán lại.

### Lịch sử nhãn

Mỗi cặp giữ riêng:

- `llm_label`: nhãn LLM gốc;
- `human_label`: nhãn của người kiểm chứng, nếu có;
- `final_label`: nhãn dùng trong dataset;
- `label_source`: `llm`, `human_verified` (người xác nhận nhãn LLM), `human_corrected` (người sửa nhãn LLM), `human_manual` (người gán khi không có nhãn LLM hợp lệ hoặc tìm thủ công).

Mỗi lần sửa ghi người sửa, thời điểm và lý do. Không ghi đè nhãn gốc.

`final_label` là nhãn LLM, trừ khi người đã sửa nhãn đó hoặc đã giải quyết bản ghi `needs_review`.

## 10.5 Kiểm tra và tạo dataset có nhãn

Script nhập judgment kiểm tra trước khi nhập và dừng với lỗi hoặc ghi log:

- đúng schema;
- `query_id` và `article_id` tồn tại;
- `label` thuộc `{0, 1, 2}` khi `status = labeled`, rỗng khi khác;
- không có cặp trùng;
- không thiếu cặp so với pool;
- không có cặp nằm ngoài pool được yêu cầu chấm;
- `evidence` khớp nguyên văn với nội dung Điều.

Bản ghi không đạt chuyển `error` hoặc `needs_review`, không bị bỏ âm thầm. Bản ghi `error` do lỗi kỹ thuật được chạy lại với cùng version prompt; bản ghi `needs_review` chỉ được giải quyết bởi người (`label_source = human_manual`).

**Dataset có nhãn** gồm mọi cặp `(query_id, article_id)` có `final_label` hợp lệ. Bản ghi `needs_review` hoặc `error` chưa giải quyết **không** trở thành dữ liệu train hay qrels chính thức; số lượng được báo cáo.

**Query không có positive.** Query không có cặp nào với `final_label ≥ 1` được gắn cờ `no_positive_in_pool`. Cờ này không có nghĩa query không trả lời được. Query này:

- vẫn giữ trong dataset cùng các nhãn đã có;
- không tạo cặp huấn luyện;
- bị loại khỏi metric val/test, với số lượng và tỷ lệ được báo cáo;
- với test, được kiểm tra lại sau pool cuối (mục 9.2).

Query có `query_issue` đã được xác nhận bị loại khỏi dataset, có log.

Schema tối thiểu của dataset được chấp nhận, một dòng cho mỗi cặp:

| Trường | Ý nghĩa |
|---|---|
| `query_id`, `article_id` | Khóa |
| `final_label`, `label_source` | Nhãn dùng trong dataset và nguồn nhãn (mục 10.4) |
| `query_type`, `dup_group_id` | Từ file query |
| `source_article_id`, `source_doc_id`, `source_group_id` | Truy vết nguồn |
| `no_positive_in_pool` | Cờ cấp query |

Split được gán sau, trong file split riêng (mục 4.2). Dataset có nhãn được đóng băng trước split (mốc 5, mục 15).

## 10.6 Provenance và resume

Mỗi lần gọi LLM, cả sinh query và gán nhãn, lưu:

- đầu vào và đầu ra thô;
- tên model và version;
- version prompt;
- thời điểm (UTC);
- cấu hình: temperature, kích thước lô, seed nếu có;
- ID lần chạy (`gen_run_id`, `label_run_id`).

Mỗi bản ghi kết quả trỏ về ID lần chạy tạo ra nó.

Resume dùng khóa ổn định: Điều nguồn với bước sinh, `(query_id, article_id)` với bước gán nhãn. Chạy lại thì bỏ qua khóa đã có kết quả hợp lệ và không tạo bản ghi trùng.

## 10.7 Phân loại negative trong tập đánh giá

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
2. mọi cặp trong final pool có nhãn đã chấp nhận;
3. qrels đóng băng (mục 9.3).

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

- Qrels val là nhãn của dataset cho query val, lấy từ pool tạo dataset (mục 9.1). Val không mở rộng pool.
- Điều chưa chấm được coi là không liên quan; báo judged coverage trên val.
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
- **Latency đầu-cuối qua API:** khi có app, đo thêm thời gian của `POST /v1/search` (từ lúc gửi đến lúc nhận đủ response, cùng máy, `highlight=false`), báo cáo p50 và p95 trong một bảng riêng, ghi rõ đây là số đo khác loại. Không dùng số này thay cho số đo của `search()`.

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
- nhãn LLM sai;
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
- Script cho từng bước, theo thứ tự pipeline:
  - chuẩn bị dữ liệu;
  - validate dữ liệu;
  - sinh query;
  - kiểm tra query;
  - build index;
  - tạo pool;
  - gán nhãn bằng LLM;
  - nhập và kiểm tra nhãn, tạo dataset có nhãn;
  - split dataset;
  - check leakage;
  - sinh biến thể;
  - train;
  - evaluate;
  - mở rộng pool đánh giá;
  - xuất report;
  - tải artifact.
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
- `data/FROZEN.md`: hash của query tổng hợp, query OOD, prompt và guideline đã chốt, dataset có nhãn, split dataset, qrels và thời điểm freeze.
- Changelog methodology.
- `Dockerfile.api`, `Dockerfile.ui`, `docker-compose.yml`, `.dockerignore`.
- Ba file requirements riêng: `requirements-api.txt` (torch bản CPU), `requirements-ui.txt` (không có torch), `requirements-train.txt`. Phiên bản ghim cứng.
- `openapi.json`: hợp đồng API đã đóng băng (mục 14.5, 15).
- `Makefile` với các lệnh: `fetch-artifacts` (tải artifact về `./artifacts` trước buổi bảo vệ), `up` (`docker compose up`), `smoke` (khởi động, gọi `/health`, chạy một query rồi dừng), `demo-local` (chạy `api` và `ui` bằng Python, không Docker).

## 13.2 Artifact

| Artifact | Nơi lưu |
|---|---|
| File split dataset, query files, dataset có nhãn, judgment và nhãn người kiểm chứng, qrels, đầu vào/đầu ra LLM thô, run files, reports | GitHub, dạng text |
| Checkpoint A, B | Hugging Face Hub, ghi revision trong config |
| Dense index, processed chunks | Hugging Face dataset repo hoặc Google Drive, có script tải; hoặc build lại bằng script |

Không commit model hoặc binary lớn vào GitHub.

**Quy tắc đóng gói:**
- Image `api` và `ui` **không chứa** artifact, `qrels`, file query test, query OOD hay `runs/` (loại bằng `.dockerignore`).
- Thư mục `./artifacts` (index BM25, index dense, file chunk, bảng Điều, manifest, model và checkpoint) được mount vào container `api` ở chế độ **chỉ đọc**.
- File SQLite của feedback nằm trên một volume riêng, ghi được.

## 13.3 Các mức tái lập và cách chạy app

### 1. Tái lập đánh giá

Bắt buộc chạy được trên CPU:

- từ artifact đã lưu;
- một lệnh chạy lại toàn bộ bảng kết quả.

### 2. Tái lập toàn bộ

Từ dataset gốc đến checkpoint.

- Training cần GPU.
- Sinh query và gán nhãn bằng LLM không tái lập bit-by-bit.
- File query, judgment thô và dataset có nhãn đã lưu là điểm xuất phát chính thức cho nhánh reproducibility.

3. **Chạy app:** `docker compose up` là cách chạy chính. `make demo-local` là cách dự phòng khi Docker không dùng được. Cả hai cách phải dùng cùng artifact và cùng config, và README mô tả cả hai.

---

# 14. App architecture

## 14.1 Ranh giới

- Luồng gọi: **UI → API → `SearchService` → `retrieval/`**.
  - `src/retrieval/`: retriever, index, manifest, MaxP. Không import lớp nào phía trên.
  - `src/service/`: `SearchService`, chứa logic ứng dụng (chế độ BM25 / Semantic / Hybrid / So sánh, cờ `in_both`, highlight, ghi và xuất feedback).
  - `src/api/`: FastAPI, chỉ làm việc kiểm tra request, gọi `SearchService`, ánh xạ lỗi.
  - `src/contracts/`: schema Pydantic dùng chung cho API và UI.
  - `src/ui/`: Streamlit, chỉ hiển thị và gọi API bằng HTTP.
- `ui/` chỉ được import `contracts/` và thư viện bên thứ ba. Không được import `service/` hay `retrieval/`.
- Các script đánh giá gọi thẳng `retrieval/`, không đi qua HTTP.
- App không được có bản cài đặt truy hồi, token hóa, prefix hay chuẩn hóa query riêng. `SearchService` gọi đúng retriever, index và hàm nạp có kiểm tra manifest mà phần đánh giá dùng.
- Mô hình semantic trong app được chọn bằng một khóa trong config (`app.semantic_system`). Khi phát triển, khóa này trỏ tới S2. Khi demo cuối, khóa phải trỏ tới checkpoint có NDCG@10 trên val cao hơn giữa S3 và S4. Lựa chọn dựa trên val, không dựa trên test. Chỉ con người được đổi giá trị này.

## 14.2 Chức năng tối thiểu

| Chức năng | Quy tắc |
|---|---|
| Nhập query | Ô văn bản tiếng Việt |
| Top-k | Chọn 1–20, mặc định 10 |
| Chế độ | BM25; Semantic; Hybrid; So sánh hai cột BM25 và Semantic, đánh dấu Điều xuất hiện ở cả hai |
| Filter | Loại văn bản, lĩnh vực, cơ quan ban hành; áp dụng mask trước ranking. Danh sách giá trị lọc lấy từ `GET /v1/info`, UI không hard-code. UI không có lọc theo năm ban hành. |
| Điểm | Hiển thị điểm kèm tên thang: `BM25`, `cosine` hoặc `RRF`; không đặt hai thang lên cùng một trục |
| Highlight | BM25: các từ của query khớp theo pipeline mục 7.1.1, ánh xạ lại vị trí trên nội dung NFC gốc; không hiển thị chuỗi nối `_` hoặc sửa nội dung để highlight. Semantic: câu trong Điều có cosine cao nhất với query. API trả về **danh sách vị trí ký tự**, không trả HTML (mục 14.5). Chỉ tính cho kết quả đang hiển thị, có cache. Quy tắc tách câu là xác định và ghi trong config. Hybrid: dùng highlight kiểu Semantic. |
| Thông tin kết quả | Tên văn bản, số và tiêu đề Điều, tình trạng hiệu lực, nội dung Điều |
| Feedback | Nút `Hữu ích` / `Không hữu ích` trên từng kết quả |
| Xuất feedback | Tải CSV |
| Lưu ý pháp lý | “Kết quả không thay thế tư vấn pháp lý.” |

## 14.3 Xử lý đầu vào

- Query rỗng/chỉ khoảng trắng/ký tự đặc biệt: không search, hiển thị thông báo.
- Query vượt giới hạn token: cắt theo tokenizer và hiển thị cảnh báo.
- Filter không còn Điều: thông báo, không crash.
- Model load lỗi hoặc manifest mismatch: dừng app, thông báo rõ ràng; không chạy index sai.
- Mỗi tình huống ở trên tương ứng một mã lỗi của API (mục 14.5). UI hiển thị thông báo dựa trên **mã lỗi**, không dựa trên nội dung chuỗi thông báo.
- Query vượt giới hạn token được cắt ở API theo tokenizer E5, kèm cảnh báo `QUERY_TRUNCATED` trong response. Cắt cùng một query cho mọi chế độ.
- Nếu API không phản hồi (không kết nối được), UI hiển thị thông báo "Dịch vụ tìm kiếm chưa sẵn sàng" và không báo lỗi kỹ thuật thô.

## 14.4 Lưu feedback

- **Chỉ API được ghi SQLite.** UI không truy cập database.
- Bảng `searches`: một dòng cho mỗi lượt tìm kiếm, gồm `search_id`, thời điểm (UTC), query đã chuẩn hóa, chế độ, model hoặc revision, và danh sách (`system`, `article_id`, thứ hạng) đã trả về.
- Bảng `feedback`: `search_id`, `system`, `article_id`, nhãn (`useful` hoặc `not_useful`), thời điểm (UTC). Khóa duy nhất (`search_id`, `system`, `article_id`). Gửi lại thì **cập nhật** (upsert), không thêm dòng.
- Query, chế độ và thứ hạng lấy từ bảng `searches` phía server. API không tin các giá trị này từ client.
- File xuất CSV mã hóa UTF-8 có BOM.
- Feedback **không** được dùng trong bất kỳ metric nào của MVP.

## 14.5 Hợp đồng API

**Quy ước chung.** Tiền tố `/v1`. Dữ liệu JSON. `article_id` luôn là **chuỗi**. Điểm luôn đi kèm `score_type` (`bm25`, `cosine` hoặc `rrf`), và điểm của hai thang không bao giờ được gộp hay so sánh trực tiếp.

**Endpoint**

| Endpoint | Chức năng |
|---|---|
| `GET /health` | Trả 200 chỉ khi model và index đã nạp và manifest đã khớp. Ngược lại trả 503 `MODEL_NOT_READY`. |
| `GET /v1/info` | Revision model, hash manifest, git commit, giới hạn (top-k từ 1 đến 20, độ dài query), danh sách giá trị filter, danh sách chế độ khả dụng. |
| `POST /v1/search` | Tìm kiếm (mô tả bên dưới). |
| `POST /v1/feedback` | Body: `search_id`, `system`, `article_id`, `label`. |
| `GET /v1/feedback/export` | Tải CSV feedback. |

**`POST /v1/search`**
- Request: `query`, `mode` (`bm25`, `semantic`, `hybrid`, `compare`), `top_k` (1 đến 20, mặc định 10), `filters` (`doc_types`, `domains`, `issuers`, `year_min`, `year_max`), `highlight` (mặc định `true`). `year_min` và `year_max` vẫn thuộc hợp đồng nhưng UI không gửi (mục 14.2).
- Response: `search_id` (UUID do server sinh), `query_normalized`, `warnings`, `timing_ms`, và `lists`.
- `lists` là mảng các danh sách kết quả. Chế độ `bm25`, `semantic` và `hybrid` trả một danh sách, `compare` trả hai danh sách (BM25 và Semantic). Mỗi danh sách có `system`, `score_type` và `items`.
- Mỗi item gồm: `rank`, `article_id`, tên văn bản, số và tiêu đề Điều, tình trạng hiệu lực, `content`, `score`, `in_both`, `highlights`.
- `in_both` do server tính. Giá trị này chỉ có ý nghĩa ở chế độ `compare`.

**Highlight.** `highlights` là danh sách `{start, end}` trên chuỗi `content`. Vị trí tính theo **code point Unicode** (chỉ số chuỗi Python) trên `content` đã ở dạng NFC, khoảng nửa mở: `content[start:end]`. Các đoạn liền kề được gộp. API không trả HTML.

**Lỗi.** Mọi lỗi dùng dạng `{"error": {"code": "...", "message": "..."}}`.

| Mã | HTTP | Khi nào |
|---|---|---|
| `EMPTY_QUERY` | 422 | Query rỗng, chỉ khoảng trắng hoặc ký tự đặc biệt |
| `INVALID_FILTER` | 422 | Giá trị filter không có trong `/v1/info` |
| `INVALID_REQUEST` | 422 | Request sai schema |
| `MODEL_NOT_READY` | 503 | Model hoặc index chưa nạp xong |
| `INDEX_MANIFEST_MISMATCH` | 503 | Manifest không khớp |

Cảnh báo (không phải lỗi, nằm trong `warnings`): `QUERY_TRUNCATED`. Filter hợp lệ nhưng không còn Điều nào thì trả danh sách rỗng, không báo lỗi.

**Đóng băng hợp đồng.** File `openapi.json` được sinh từ code và commit vào repo. Có test so `openapi.json` với schema sinh ra từ code. Đổi hợp đồng phải qua quy trình ở mục 0 và cập nhật cả `openapi.json` lẫn Changelog.

## 14.6 Chạy và đóng gói

- API chạy **một worker**. Model và index nạp **một lần** lúc khởi động. Nếu manifest không khớp, tiến trình thoát với mã khác 0, không phục vụ index sai.
- Số lượt tìm kiếm chạy song song bị giới hạn bởi `api.max_concurrent_search` (mặc định 1).
- App chạy **offline**: đặt `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`. App không được tải dữ liệu hay model từ mạng khi đang chạy.
- Địa chỉ API mà UI gọi lấy từ biến môi trường `API_BASE_URL`, mặc định `http://api:8000`. Không dùng `localhost` trong container.
- `docker-compose.yml`: `api` có healthcheck gọi `/health`; `ui` chỉ khởi động khi `api` đã khỏe mạnh. Cổng bind vào `127.0.0.1`. Container chạy bằng user không phải root.
- Huấn luyện và pipeline dữ liệu **không** nằm trong Docker.

## 14.7 Test bắt buộc cho phần app

1. Snapshot `openapi.json` khớp với schema sinh từ code.
2. **Tương đương:** trên một tập query cố định, `retrieval.search` và `POST /v1/search` trả cùng thứ tự `article_id` và cùng điểm (trong sai số số học ghi trong config).
3. Luật import: test đọc import xác nhận `ui/` không import `service/` hay `retrieval/`; image `ui` không chứa `torch`.
4. Filter: khi có ít nhất k Điều hợp lệ thì trả đủ k.
5. `normalize_query`: NFC đúng, không gọi hai lần; query nhập ở dạng NFD cho cùng kết quả với dạng NFC.
6. Highlight: `content[start:end]` đúng đoạn mong đợi trên các câu tiếng Việt có dấu.
7. Feedback: gửi lại cùng một (`search_id`, `system`, `article_id`) không sinh dòng mới; đổi nhãn thì cập nhật.
8. Thứ tự khi hòa điểm: kết quả không đổi giữa các lần chạy.
9. Smoke test cho compose (`make smoke`).

---

# 15. Frozen decisions — các mốc đóng băng

Các artifact dưới đây được freeze theo thứ tự. Mỗi mốc ghi hash và thời điểm vào `data/FROZEN.md`.

Sau freeze, artifact chỉ được đổi qua change procedure ở mục 0.

1. **Danh sách lĩnh vực và ánh xạ loại quan hệ:** sau EDA, trước lọc. Đã freeze.
2. ~~**`splits.json` theo họ văn bản:** trước khi sinh bất kỳ query nào.~~ **Đã thay thế ngày 2026-10-25.** Bản freeze ngày 2026-10-24 giữ trong `data/FROZEN.md` làm lịch sử, không phải split đang áp dụng (mục 4.1). Split đang áp dụng là mốc 6.
3. **Cấu hình S1₀:** VNCoreNLP + unigram, `k1 = 1.2`, `b = 0.75` đã chốt; ghim phiên bản, biến thể công thức, config và manifest trước pilot (mục 7.1.1, 7.5). **Prompt sinh query, prompt gán nhãn và annotation guideline:** sau pilot (mục 10.4), trước sinh query hàng loạt.
4. **File query tổng hợp đã kiểm tra:** trước pool tạo dataset. **Query OOD:** khi nộp, trước khi tìm đáp án (mục 6).
5. **Dataset có nhãn:** sau kiểm tra ở mục 10.5, trước split.
6. **Split dataset:** trước mọi training, tune hoặc đánh giá trên val.
7. **Tham số BM25 S1:** sau khi tune trên val.
8. **Learning rate:** chọn trên A, freeze trước khi train B.
9. **Checkpoint A và B:** sau khi chọn trên val, trước pool v3/v4.
10. **Cấu hình S5, gồm dense component:** trước pool v5.
11. **Ranh giới nhóm phân tích, ngưỡng thắng và phương pháp kiểm định thống kê:** trước final evaluation.
12. **`openapi.json` phiên bản đầu:** trước khi viết UI. Mốc này độc lập với các mốc còn lại, có thể thực hiện bất cứ lúc nào trước khi bắt đầu phần UI.
13. **Qrels test và OOD:** khi mọi cặp trong final pool có nhãn đã chấp nhận (mục 9.3).

---

# 16. Things explicitly prohibited

Không được:

- dùng test/OOD metric cho bất kỳ quyết định nào;
- sửa artifact đã freeze mà không qua change procedure;
- đưa query, variant hoặc nhãn của val/test/OOD vào training, kể cả negative; với phương án (b) của OI-12, đưa Điều thuộc họ của val/test vào training;
- split trước khi dataset có nhãn được tạo và kiểm tra; chia corpus trước rồi sinh query theo split;
- chia ngẫu nhiên từng dòng `(query, article, label)`, hoặc tách các cặp của cùng một query hay cùng `dup_group_id` sang nhiều split;
- tự chọn đơn vị split khi OI-12 chưa chốt; chia lại split để cải thiện metric;
- coi Điều nguồn là positive hoặc nhãn 2 mặc định;
- tạo nhãn 0 cho Điều ngoài pool; ép `needs_review` hoặc lỗi thành nhãn; dùng một nhãn hợp lệ để biểu diễn lỗi;
- để bản ghi `needs_review` hoặc lỗi chưa giải quyết trở thành dữ liệu train hoặc qrels chính thức;
- dùng lexical overlap để quyết định sinh, giữ, loại hoặc chia query;
- cắt nội dung Điều âm thầm khi gửi LLM; bịa trích dẫn căn cứ;
- đổi E5 prefix, pooling, normalization, `max_length`, hoặc truncate passage âm thầm;
- dùng approximate search trong evaluation;
- đổi pool depth, label scale hoặc metric definition;
- sửa expected values trong metric unit test để test pass;
- loại record mà không log;
- cho LLM gán nhãn hoặc người kiểm chứng thấy system source, rank, score, Điều nguồn hoặc provisional metric; cho người kiểm chứng thấy nhãn LLM;
- sửa prompt hoặc guideline dựa trên lỗi hay metric của test rồi vẫn coi test là độc lập;
- đưa nhãn bổ sung của test/OOD vào train; dùng việc mở rộng pool để tune trên test;
- khẳng định tỷ lệ đúng của nhãn LLM khi chưa có kết quả kiểm chứng;
- dùng LLM/Claude viết, gợi ý hoặc sửa OOD query;
- thêm system vào main table mà không đưa system đó vào pool;
- tạo retrieval logic riêng trong app;
- bắt đầu phần code phụ thuộc một vấn đề mở ở mục 17 trước khi nhóm quyết định;
- trong paper:
  - claim vượt giới hạn mục 1;
  - gọi dataset hoặc qrels là human gold;
  - gọi low-overlap group là “query đồng nghĩa”;
  - trình bày Recall@k như exhaustive recall;
- dùng learning rate, batch size, số epoch tối đa hoặc seed khác nhau cho A và B;
- tự đổi cách gom họ văn bản bằng union-find nếu relationships có vấn đề;
- tự chọn danh sách lĩnh vực;
- tự chọn ánh xạ relation labels;
- diễn giải canonical duplicate representative như một kết luận pháp lý.
- `ui/` import `retrieval/` hoặc `service/`.
- Đổi API mà không cập nhật `openapi.json` và Changelog.
- Encode query hoặc passage bằng đường khác ngoài hàm chung ở mục 7.3, kể cả trong highlight.
- Đưa `qrels`, query test, query OOD hay `runs/` vào image Docker.
- Chạy API với nhiều worker.
- App tải dữ liệu hoặc model từ mạng khi đang chạy.
- Để UI ghi trực tiếp vào SQLite.

---

# 17. Các vấn đề còn mở

| ID | Vấn đề | Chặn phần nào | Quyết định của nhóm |
|---|---|---|---|
| OI-10 | Danh sách 5–8 lĩnh vực đưa vào corpus. Claude Code xuất EDA theo lĩnh vực; **nhóm chọn**, ghi vào config và Changelog, sau đó freeze. Claude Code không được tự chọn. | Lọc dữ liệu, split, mọi bước sau | **Đã chốt 2026-10-22.** Loại văn bản: `Luật`, `Nghị định`, `Thông tư`; hiệu lực: `Còn hiệu lực`. 8 lĩnh vực, khớp **nguyên chuỗi** `linh_vuc` (không tách dấu phẩy/chấm phẩy, không khớp chuỗi con, không gộp tên gần nghĩa; `Chưa phân loại` và null bị loại; không dùng `nganh`): `Quản lý ngân sách`; `Quản lý thuế, phí và lệ phí`; `Lao động, tiền lương, tiền công`; `Chính sách thuế`; `Ngân sách nhà nước`; `Tài chính hành chính sự nghiệp`; `TCNH và thị trường TC, trái phiếu, khác`; `Quản lý dịch vụ tài chính và các quỹ tài chính`. Lĩnh vực thứ 8 đồng hạng 69 văn bản với `Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước`; nhóm chọn theo thứ tự sắp xếp của `scripts/eda.py` (số văn bản giảm dần, hòa thì tên tăng dần theo mã Unicode). |
| OI-11 | Máy demo (hệ điều hành, RAM, Docker chạy được chưa) và đường chạy chính. Phương án: (a) Docker là đường chính, `demo-local` dự phòng; (b) `demo-local` là đường chính, Docker là phần phụ. | Không chặn code. Ảnh hưởng thứ tự kiểm thử trước buổi bảo vệ và nội dung README. | |
| OI-12 | Dataset đo khả năng nào: (a) query mới trên corpus cố định, hay (b) tổng quát hóa sang họ văn bản chưa gặp. Quyết định đơn vị chia, cách tính tỷ lệ 80/10/10, phạm vi sai lệch cho phép, ràng buộc với dữ liệu training và cách xử lý query pilot (mục 4.2, 4.3, 8.3, 10.4). | Split dataset, tạo dữ liệu training, tune trên val, đào hard negative || **Đã chốt 2026-10-26:** (a), đơn vị chia = cùng Điều nguồn ∪ trùng nguyên văn ∪ `likely_same_intent`; 80/10/10 theo số query, phân tầng lĩnh vực, seed 42; query pilot vào train. Báo cáo chồng lấn: `data/splits_v2/overlap_report.json`. |
| OI-13 | Ngưỡng chấp nhận nhãn LLM để chạy hàng loạt; quy mô sinh hàng loạt (số và cách chọn Điều nguồn); cách phát hiện query trùng ý (mục 5.1, 5.4, 10.4). Phần còn mở không được tự đặt. | Sinh và gán nhãn hàng loạt; split (cần cách gom trùng ý) | **Chốt một phần 2026-10-25:** pilot 10 query; API `gemini-3.5-flash-lite`; người kiểm chứng tối đa 30 cặp, mục tiêu 10/nhãn 0/1/2, thiếu thì lấy số có và báo thiếu; seed cố định, ưu tiên độ phủ query/kiểu/lĩnh vực. Chưa chốt ngưỡng chạy hàng loạt. |
| OI-14 | Tham số và token hóa BM25 tạo dataset S1₀ (mục 7.1.1, 7.5). | Không còn chặn quyết định tham số; baseline local được bàn giao ở `docs/phases/bm25.md` | **Đã chốt 2026-10-25:** `bm25s`, VNCoreNLP + word unigram, `k1 = 1.2`, `b = 0.75`. Không bigram; E5 dùng tokenizer riêng trên văn bản tự nhiên. |
| OI-15 | Ngưỡng nhãn của Điều positive trong training (`= 2` hay `≥ 1`) và cách dùng query có nhiều positive (mục 8.2). | Tạo cặp training cho A và B | |
| OI-16 | Nguồn nhãn của OOD: theo protocol LLM như dataset (mục 10.3), hay do người chấm. Câu hỏi OOD vẫn do người viết (mục 6). | Gán nhãn OOD | |

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

- Corpus: `th1nhng0/vietnamese-legal-documents`, ghim revision; Luật, Nghị định, Thông tư còn hiệu lực; 8 lĩnh vực theo OI-10; loại phụ lục.
- Đơn vị truy hồi, gán nhãn và metric = **Điều**.
- Chunk `≤ 450 token` theo tokenizer E5.
- Điều dài tách theo Khoản → câu → cửa sổ token (chồng lấn 50 token) nếu một câu vượt 450 token.
- Score Điều = MaxP.
- Prefix chunk: `Tên văn bản › Điều X. Tiêu đề › ...`.
- Luồng dữ liệu: dữ liệu processed → LLM sinh query → S1₀ và S2 truy hồi top-10 → hợp nhất ứng viên → LLM gán nhãn → kiểm tra, tạo dataset có nhãn → split train/val/test → huấn luyện và đánh giá.
- Điều nguồn chọn từ toàn corpus; Điều nguồn không mặc định là positive.
- Họ văn bản gom bằng union-find trên quan hệ sửa đổi, bổ sung, thay thế, chạy trên **toàn bộ dataset trước khi lọc**; dùng để truy vết, kiểm tra chồng lấn và loại hard negative.
- Split sau khi có dataset có nhãn; không chia theo dòng; mọi cặp của một query và của một `dup_group_id` nằm cùng split; mục tiêu 80/10/10; seed 42; chốt một lần. Đơn vị chia theo OI-12.
- `data/splits.json` (mốc 2) là artifact lịch sử, không phải split đang áp dụng.
- Index chứa toàn corpus.
- Query tổng hợp do LLM sinh, ba kiểu `natural`, `scenario`, `keyword`, được dùng thuật ngữ pháp lý tự nhiên. Quy mô theo OI-13.
- OOD khoảng 40 câu do người viết, không dùng LLM; tách biệt với dataset tổng hợp.
- Query copy nguyên văn từ 8 âm tiết liên tiếp trở lên bị loại khỏi mọi tập.
- Không có ngưỡng lọc overlap; overlap chỉ dùng để phân tích.
- Variant `no_diacritic` và `typo` chỉ từ query test, dùng chung qrels, không vào train và không vào pool.
- S1₀ BM25 tạo dataset: `bm25s`, VNCoreNLP + word unigram, `k1 = 1.2`, `b = 0.75`; OI-14 đã chốt. Không bigram; không dùng tokenizer âm tiết của mục 5.3 cho truy hồi BM25.
- S1 BM25: cùng pipeline VNCoreNLP + unigram và biến thể công thức với S1₀; chỉ `k1`, `b` tune trên val.
- S2 e5 zero-shot.
- S3 e5 fine-tune A: in-batch negative.
- S4 e5 fine-tune B: in-batch + 1 hard negative.
- S5 RRF: S1 + dense tốt hơn trên val; `k = 60`, cố định, không tune.
- E5 (văn bản tự nhiên, tokenizer riêng của checkpoint; không VNCoreNLP, không word n-gram):
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
  - checkpoint chọn bằng NDCG@10 val;
  - positive theo ngưỡng chốt ở OI-15.
- Hard-negative candidate window = rank 3–30.
- Pooling depth = 10. Pool tạo dataset = S1₀ + S2. Pool đánh giá test/OOD mở rộng tăng dần với S1, S3, S4, S5.
- Mọi main-table system phải vào pool trước freeze qrels.
- Gán nhãn:
  - label 0/1/2, trạng thái `needs_review`/`error` tách khỏi nhãn;
  - blind với LLM và người kiểm chứng;
  - nhãn LLM là nhãn dùng trong dataset, có lý do và căn cứ;
  - pilot với người kiểm chứng độc lập trên mẫu; báo cáo đồng thuận;
  - giữ lịch sử nhãn LLM gốc, nhãn người và nhãn đã sửa;
  - Điều ngoài pool là chưa chấm.
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
- App có kiến trúc UI → API (FastAPI) → `SearchService` → `retrieval/`. UI chỉ gọi API qua HTTP và dùng `contracts/`; phần đánh giá gọi thẳng `retrieval/`.
- Hợp đồng API gồm 5 endpoint (`/health` và bốn endpoint tiền tố `/v1`), mã lỗi cố định, `article_id` là chuỗi, highlight là vị trí code point, `openapi.json` được commit và đóng băng.
- Thứ tự khi hòa điểm cố định; encode luôn fp32; `normalize_query` là hàm duy nhất cho query.
- Docker có hai image (`api`, `ui`), artifact mount chỉ đọc và không nằm trong image, chạy offline, một worker; `make demo-local` là đường dự phòng.
- Feedback chỉ API ghi, khóa duy nhất (`search_id`, `system`, `article_id`), ghi dạng upsert.

---

# Changelog

| Ngày | Thay đổi | Lý do | Ảnh hưởng | Người duyệt |
|---|---|---|---|---|
| 2026-10-22 | OI-1: chia theo họ văn bản bằng union-find + loại trùng hash — *phần chia split đã thay thế ngày 2026-10-25; gom họ giữ để truy vết, xem dòng cuối* | Chống leakage giữa văn bản gốc và văn bản sửa đổi | Mục 3–4 | Nhóm |
| 2026-10-22 | OI-2: tune learning rate trên A, B dùng nguyên giá trị đó | Ablation A–B chỉ khác hard negative | Mục 2, 8 | Nhóm |
| 2026-10-22 | OI-3: S5 RRF vào bảng chính | Hybrid là hệ thống so sánh chính thức | Mục 7, 9, 14 | Nhóm |
| 2026-10-22 | OI-4: người chấm toàn bộ pool — *đã thay thế ngày 2026-10-25, xem dòng cuối* | Qrels cuối hoàn toàn do người quyết định | Mục 9, 10 | Nhóm |
| 2026-10-22 | OI-5: ngưỡng ≥ 1 cho bảng chính, = 2 ở phụ lục | Không trộn ngưỡng trong bảng chính | Mục 11 | Nhóm |
| 2026-10-22 | OI-6: kiểm định Fisher randomization cho 4 cặp, Holm correction tách riêng | Kết luận có kiểm định và kiểm soát multiple comparisons | Mục 11 | Nhóm |
| 2026-10-22 | OI-7: tune BM25 trên val | Baseline công bằng với dense | Mục 7 | Nhóm |
| 2026-10-22 | OI-8: đóng băng các ngưỡng số — *ngưỡng overlap 0,8 cho train đã bỏ ngày 2026-10-25, xem dòng cuối* | Cố định trước khi chạy | Mục 5, 8, 12 | Nhóm |
| 2026-10-22 | OI-9: canonical duplicate = `article_id` nhỏ nhất | Dedup thuần kỹ thuật, không mang ý nghĩa pháp lý | Mục 3 | Nhóm |
| 2026-10-22 | Test 150 = 50 natural + 50 scenario + 50 keyword — *đã thay thế ngày 2026-10-25, xem dòng cuối* | Cấu trúc test cuối | Mục 5 | Nhóm |
| 2026-10-22 | RRF `k = 60`, cố định | Giảm thêm một bước tune, giữ cấu hình fusion cố định | Mục 7, 9 | Nhóm |
| 2026-10-22 | Union-find chạy trên dataset gốc trước khi lọc | Cách gom họ bảo thủ hơn về leakage | Mục 4 | Nhóm |
| 2026-10-22 | Holm correction thực hiện tách khỏi `ranx` nếu thư viện không hỗ trợ trực tiếp | Tránh claim sai về implementation | Mục 11 | Nhóm |
| 2026-10-22 | Cặp kiểm định thứ tư đổi từ S4–S5 thành (dense tốt hơn trên val)–S5 | So sánh RRF với đúng thành phần dense của nó | Mục 11 | Nhóm |
| 2026-10-22 | Holm áp dụng riêng cho test gốc và OOD | Làm rõ phạm vi hiệu chỉnh | Mục 11 | Nhóm |
| 2026-10-22 | Thêm quy tắc cắt câu > 450 token (cửa sổ token, chồng lấn 50) | Lấp lỗ hổng chunking với câu liệt kê dài | Mục 3 | Nhóm |
| 2026-10-22 | `validate_data` chạy trước split; kiểm tra chép nguyên văn chạy lại sau khi sửa query — *thứ tự đã thay thế ngày 2026-10-25: `validate_data` chạy trước sinh query; query tổng hợp không sửa câu chữ* | Làm rõ thứ tự pipeline | Mục 3, 5 | Nhóm |
| 2026-10-22 | Đo tốc độ chấm ở vòng hiệu chỉnh; điều chỉnh quy mô chỉ trước pool v1 — *đã thay thế ngày 2026-10-25, xem dòng cuối* | Kiểm soát khối lượng chấm toàn bộ pool | Mục 10 | Nhóm |
| 2026-10-22 | Thêm danh sách hạn chế bắt buộc nêu trong paper; bỏ hai mục cuối trùng lặp — *danh sách cập nhật ngày 2026-10-25* | Gọn source of truth | Mục 1 | Nhóm |
| 2026-10-22 | OI-10: chốt loại văn bản, hiệu lực, 8 lĩnh vực (khớp nguyên chuỗi), ánh xạ 6 nhãn quan hệ | Hoàn tất bước dữ liệu sau EDA | Mục 3.2, 4.1, 17; `configs/data.yaml` | Nhóm |
| 2026-10-22 | Mục 3.6: cạnh có ID không có trong metadata không làm `validate_data` thất bại; ID giữ làm nút trung gian, không tính vào corpus; báo tỷ lệ cạnh không ánh xạ trên toàn bộ cạnh và riêng nhãn thuộc ánh xạ | SPEC trước đó chưa quy định cách xử lý; chọn cách bảo thủ về leakage | Mục 3.6, 4.1 | Nhóm |
| 2026-10-22 | Mục 4.1 (*phần chia split đã thay thế ngày 2026-10-25; quy tắc phạm vi họ và lĩnh vực chủ đạo giữ*): chỉ chia các họ có văn bản trong corpus cuối cùng; lĩnh vực chủ đạo đếm trên văn bản trong corpus của họ; chỉ báo kích thước họ, không tự đặt ngưỡng | SPEC trước đó chưa rõ tập họ và phạm vi đếm lĩnh vực | Mục 4.1 | Nhóm |
| 2026-10-22 | Làm rõ ngoại lệ ID thiếu metadata: chỉ áp dụng cho `other_doc_id` khác null/rỗng; `doc_id` nguồn thiếu và ID null/rỗng vẫn là lỗi; mỗi ID là một nút riêng | Tránh code vô tình cho phép cả hai đầu hoặc gộp ID null thành một nút | Mục 3.6, 4.1 | Nhóm |
| 2026-10-22 | Thêm API (FastAPI) và Docker cho phần app; sửa mục 7.2, 7.3, 7.4, 11.2, 13.1 đến 13.3, 14.1 đến 14.4, 15, 16, 17; thêm mục 14.5 đến 14.7 (gồm chế độ `hybrid` và `score_type` `rrf`); thêm OI-11 | Tách lớp rõ ràng, chống lệch âm thầm giữa app và đánh giá, ổn định khi demo | Chỉ phần app và đóng gói. Không ảnh hưởng split, query, pooling, qrels, huấn luyện hay số liệu đánh giá | Thành Vũ |
| 2026-10-24 | Mục 14.2: UI bỏ lọc theo năm ban hành; mục 14.5 ghi rõ UI không gửi `year_min`, `year_max` | Người tra cứu thường không biết năm ban hành của văn bản; corpus chỉ gồm văn bản còn hiệu lực nên lọc năm ít giá trị | Chỉ phần UI. Hợp đồng API và `openapi.json` giữ nguyên (`year_min`, `year_max` vẫn là trường tùy chọn); không ảnh hưởng split, query, pooling, qrels, huấn luyện hay số liệu đánh giá | Thành Vũ |
| 2026-10-25 | Thay quy trình dữ liệu, nhãn và split. Luồng mới: dữ liệu processed → LLM sinh query (Điều nguồn từ toàn corpus) → S1₀ BM25 và S2 e5 zero-shot top-10 → hợp nhất ứng viên → LLM gán nhãn 0/1/2 blind, có `needs_review` → kiểm tra, tạo dataset có nhãn → split train/val/test trên dataset → huấn luyện và đánh giá. Nhãn LLM là nhãn dùng trong dataset, kiểm chứng bằng người trên mẫu pilot. Thay thế: split họ văn bản trước sinh query; query sinh theo split; quota 5.000/150/150 và 50/50/50; ngưỡng overlap 0,8 (overlap chỉ còn dùng phân tích); val chỉ có nhãn Điều nguồn; Điều nguồn là positive mặc định; người chấm toàn bộ pool; LLM chỉ dùng đo agreement; calibration 20 cặp, chấm chéo 15%, cặp neo 5%. Pool test/OOD mở rộng với S1 đã tune, S3, S4, S5 và chấm cùng protocol trước freeze qrels. Thêm OI-12 đến OI-16. `data/splits.json` (mốc 2) giữ làm lịch sử. | Quyết định của người duyệt về luồng tạo dataset: mỗi query có nhãn trên nhiều Điều ứng viên cho cả train, val và test, thay vì chỉ nhãn Điều nguồn | Mục 0–13, 15, 16, 17, Final frozen decisions; `CLAUDE.md` và tài liệu hướng dẫn trong `README.md`, `docs/`, `notebooks/README.md`. `data/splits.json` không còn là split đang áp dụng. Code đang làm dở của Task 3 (nhánh `task/3-query-generation`) và `configs/data.yaml` (khóa `split`) theo luồng cũ cần đối chiếu lại; chưa sửa trong thay đổi này | Thành Vũ |
| 2026-10-25 | Chốt OI-14: S1₀ dùng `bm25s`, VNCoreNLP + unigram, `k1 = 1.2`, `b = 0.75`; S1 giữ pipeline và chỉ tune tham số trên val. Thay quy định BM25 tách âm tiết/không tách từ ở mục 7.1. E5 giữ tokenizer riêng, không nhận đầu ra segmentation. | Người dùng duyệt phác thảo baseline trước triển khai | Mục 7, 14.2, 15, 17, Final frozen decisions; CLAUDE.md, README.md, docs/artifacts.md. Chỉ cập nhật tài liệu; chưa tạo config/index hoặc chạy baseline, không đổi artifact frozen. Token hóa âm tiết cho kiểm tra query/phân tích vẫn giữ nguyên. | Người dùng |
| 2026-10-25 | Chốt một phần OI-13: pilot 10 query; gán nhãn qua API gemini-3.5-flash-lite; mẫu kiểm chứng người tối đa 30 cặp, mục tiêu 10 cặp mỗi nhãn 0/1/2; thiếu thì báo thiếu, không tự bù. Báo agreement/kappa đúng phạm vi mẫu cân bằng nhãn. | Người dùng chọn API, model, quy mô pilot và mẫu kiểm chứng trong trao đổi thiết kế | Mục 10.3–10.4, 17; CLAUDE.md. Ngưỡng chạy hàng loạt còn mở; chưa gọi API hoặc thay dữ liệu/frozen artifact. | Người dùng |
| 2026-10-26 | Hoàn thiện bài ở mức cơ bản theo ủy quyền của Thành Vũ. (1) **Nhãn:** thay gán nhãn LLM toàn pool bằng **pseudo-qrels Điều nguồn** (`scripts/build_source_qrels.py`): positive = Điều nguồn (+ Điều trùng `content_sha1`), negative giả định = top-10 BM25/E5 khác văn bản/họ với Điều nguồn và 5 Điều ngẫu nhiên (seed 42). Không dùng heuristic theo độ trùng từ hay điểm hệ thống để gán positive. File nhãn do AI ngoài sinh bằng heuristic (`data/interim/annotation_full_v2/external/judgments.jsonl`) **không dùng**. (2) **OI-12 = (a) mở rộng:** đơn vị chia = thành phần liên thông của cùng Điều nguồn, cùng `exact_group_id`, cặp `likely_same_intent` (12 cặp); phân tầng lĩnh vực; 80/10/10 theo query; pilot vào train (`scripts/split_queries.py`, `data/splits_v2/`). (3) Hard negative training lấy rank 3–10 (run hiện có chỉ tới top-10) thay 3–30. (4) Thêm hệ thống SBERT đa ngôn ngữ (`paraphrase-multilingual-MiniLM-L12-v2`) theo yêu cầu Đề tài 8. (5) Bỏ OOD (mục 6); bỏ tune BM25 S1 trên val (dùng S1₀ cố định). (6) API thật (`src/app/service.py`) thay stub; chữ ký endpoint giữ nguyên `openapi.json`. | Hạn nộp; gán nhãn LLM toàn pool không kịp và bản AI ngoài dùng heuristic theo độ trùng từ (thiên vị BM25) | Mục 4.2, 6, 7.1, 8.3, 9–10, 11; Limitations phải nêu: một positive/query làm Recall/MRR bị đánh giá thấp (false negative), qrels không do người chấm, không có OOD, query sinh bằng nhiều chatbot web. | Thành Vũ |
