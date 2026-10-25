# CLAUDE.md — Đề tài 8: Tìm kiếm ngữ nghĩa văn bản pháp luật

`SPEC.md` là **nguồn sự thật duy nhất** về methodology. File này chỉ là bản tóm tắt để Claude Code đọc ở đầu mỗi phiên.

Nếu `CLAUDE.md` và `SPEC.md` khác nhau, **`SPEC.md` thắng**. Trước khi làm một phần việc, đọc đúng mục tương ứng trong `SPEC.md` theo bảng cuối file này.

---

## Quy tắc cứng — không được tự thay đổi

- Đơn vị truy hồi, gán nhãn và tính metric = **Điều**. Chunk chỉ dùng để encode/index; điểm Điều = **MaxP**.
- Mọi chunk **bắt buộc** `≤ 450 token` theo tokenizer E5 (kể cả tiền tố); `validate_data` dừng với lỗi nếu vi phạm. Điều dài tách theo **Khoản → câu → cửa sổ token**. Nếu một câu `> 450 token`, cắt theo token với **overlap 50 token** và ghi log `article_id`.
- Luồng dữ liệu bắt buộc (SPEC 4–5, 9–10): dữ liệu processed → LLM sinh query (Điều nguồn từ toàn corpus) → BM25 tạo dataset (S1₀) và E5 zero-shot lấy top-10 Điều → hợp nhất ứng viên → LLM gán nhãn → kiểm tra, tạo dataset có nhãn → split train/val/test → huấn luyện và đánh giá.
- `validate_data` chạy **sau parse/chunk, trước sinh query**.
- Họ văn bản gom bằng union-find trên quan hệ sửa đổi/bổ sung/thay thế, chạy trên dataset gốc trước khi lọc; dùng để truy vết, kiểm tra chồng lấn và loại hard negative. `data/splits.json` (split họ trước sinh query) là artifact lịch sử, **không** phải split đang áp dụng.
- Split **sau** khi dataset có nhãn được tạo và kiểm tra; không chia theo dòng; mọi cặp của một query và một `dup_group_id` nằm cùng split; mục tiêu 80/10/10, seed 42, chốt một lần. Đơn vị chia chờ **OI-12**.
- Điều nguồn **không** mặc định là positive. Không có ngưỡng lọc overlap; overlap chỉ dùng phân tích. Query chép nguyên văn **N = 8 âm tiết** bị loại. Không sửa câu chữ query tổng hợp.
- Training chỉ dùng query và nhãn train. Không đưa query, nhãn hoặc variant của val/test/OOD vào training, kể cả negative.
- E5: `query: ` / `passage: ` gắn **đúng một lần trong một hàm duy nhất**; `max_length = 512`; mean pooling; L2 normalize; float32; exact search; không truncate passage âm thầm.
- Mỗi index có `manifest.json`; config/manifest không khớp thì **dừng với lỗi**. Evaluation và app dùng chung loader/retriever.
- BM25 S1₀/S1 dùng `bm25s` + VNCoreNLP word segmentation + unigram; giữ dấu, không stopword removal/stemming/bigram. Pipeline query/corpus dùng chung (SPEC 7.1.1); không dùng bộ tách âm tiết phân tích query để truy hồi.
- E5 nhận văn bản tự nhiên và dùng tokenizer checkpoint riêng; không nhận đầu ra VNCoreNLP hoặc word n-gram.
- 5 hệ thống chính (S1₀ đã chốt **OI-14**: `k1 = 1.2`, `b = 0.75`, cố định trước tạo nhãn; triển khai tại `src/retrieval/bm25.py`, xem `docs/phases/bm25.md`):
  - S1 BM25 — tune `k1`,`b` trên val;
  - S2 e5 zero-shot — `configs/e5.yaml`, `scripts/run_e5.py`, kiểm chứng local tại `docs/phases/e5.md`;
  - S3 fine-tune A — in-batch negative;
  - S4 fine-tune B — A + 1 hard negative;
  - S5 RRF — S1 + dense tốt hơn trên val, `k = 60`.
- Learning rate chỉ tune trên A với `{1e-5, 3e-5}`, tối đa 2 epoch. B dùng **cùng LR, batch size, epoch budget và seed**; A/B chỉ khác hard negative.
- Mọi lựa chọn model/config/chkpt chỉ dựa trên **val**.
- Test/OOD chỉ chạy metric hiệu năng **một lần** sau khi qrels freeze. Trước đó chỉ kiểm tra integrity, không in metric hiệu năng.
- Pooling depth = 10. Pool tạo dataset = S1₀ + S2. Pool test/OOD mở rộng với S1 đã tune, S3, S4, S5, chấm cùng protocol; mọi system trong main table phải vào pool trước khi freeze qrels. Nhãn bổ sung của test/OOD không vào train.
- **Nhãn LLM là nhãn dùng trong dataset**, nhãn 0/1/2 kèm lý do và căn cứ có thật; trạng thái `needs_review`/`error` tách khỏi nhãn, không ép thành 0; chưa giải quyết thì không vào train hay qrels. Điều ngoài pool là chưa chấm, không tạo nhãn 0.
- LLM gán nhãn và người kiểm chứng làm việc blind (không thấy hệ thống, rank, score, Điều nguồn; người không thấy nhãn LLM). Giữ lịch sử nhãn LLM gốc, nhãn người, nhãn đã sửa.
- Pilot đã chốt 10 query, API `gemini-3.5-flash-lite`; người kiểm chứng blind mẫu tối đa 30 cặp, mục tiêu 10/nhãn 0/1/2. Thiếu nhãn thì lấy số có và báo thiếu; `needs_review`/error không coi là 0. Agreement/kappa chỉ mô tả mẫu cân bằng nhãn, không ngoại suy toàn dataset. Ngưỡng cho chạy hàng loạt còn chờ **OI-13**; không tự coi pilot đạt. Không sửa prompt dựa trên test.
- Metric bằng `ranx`; unit test metric dùng expected values do người tính tay — **không được sửa expected values để test pass**.
- Statistical test trên NDCG@10:
  - S1–S2;
  - S2–S3;
  - S3–S4;
  - **dense tốt hơn trên val – S5**.
  Fisher randomization/permutation test, 10.000 permutations. Holm correction áp dụng **riêng** cho 4 p-value test gốc và 4 p-value OOD.
- Lưu TREC run và metric theo từng query. Không hard-code tham số; dùng `configs/*.yaml`.

---

## Điểm phải dừng chờ người

1. **Sau EDA**
   - xuất thống kê theo lĩnh vực;
   - xuất danh sách relation labels gốc trong `relationships`;
   - **không tự chọn** 5–8 lĩnh vực;
   - **không tự ánh xạ** relation labels sang sửa đổi/bổ sung/thay thế.

2. **Sau `validate_data`, trước khi dùng đồ thị quan hệ** (đã thực hiện ngày 2026-10-24)
   - báo tỷ lệ cạnh `relationships` không ánh xạ được;
   - báo các lỗi dữ liệu quan hệ;
   - chờ người xác nhận.

3. **Sau pilot, trước sinh và gán nhãn hàng loạt**
   - báo kết quả kiểm chứng của người (đồng thuận, kiểu sai, `needs_review`);
   - chờ nhóm chốt OI-13 và version prompt/guideline.

4. **Trước split dataset**
   - chờ nhóm chốt OI-12;
   - với gom theo họ: báo phân phối kích thước họ theo số query; không tự cắt họ hoặc đổi đơn vị chia.

5. **Khi cần đổi methodology**
   - mô tả vấn đề;
   - đề xuất thay đổi;
   - nêu ảnh hưởng tới methodology và artifact đã tạo;
   - **dừng chờ người duyệt**;
   - nếu được duyệt, cập nhật Changelog trong `SPEC.md`.

6. **Khi `SPEC.md` không nói rõ hoặc có thể hiểu theo hai cách**
   - không tự đoán nếu lựa chọn ảnh hưởng tới dữ liệu, split, nhãn, metric hoặc kết quả báo cáo;
   - nêu các cách hiểu và hệ quả của từng cách, rồi dừng chờ người quyết định;
   - chi tiết thuần kỹ thuật không ảnh hưởng kết quả (tên biến, cấu trúc hàm, định dạng log) thì được tự quyết.

---

## Không được làm

Không được:

- đổi split, label scale, metric, E5 prefix, pool depth hoặc frozen artifact mà không qua change procedure;
- dùng test/OOD để tune;
- đưa val/test/OOD vào training hoặc hard-negative mining;
- loại dữ liệu mà không ghi log;
- tự thay đổi cách gom họ khi `relationships` có vấn đề;
- tự chọn lĩnh vực hoặc relation mapping;
- split trước khi dataset có nhãn được tạo và kiểm tra; chia theo từng dòng `(query, article, label)`; tự chọn đơn vị split khi OI-12 chưa chốt;
- coi Điều nguồn là positive mặc định; tạo nhãn 0 cho Điều ngoài pool; ép `needs_review` thành nhãn;
- dùng overlap để sinh, giữ, loại hoặc chia query;
- dùng LLM/Claude để viết, gợi ý hay sửa OOD query;
- cho LLM gán nhãn hoặc người kiểm chứng thấy system source, rank, score, Điều nguồn hoặc provisional metric; cho người kiểm chứng thấy nhãn LLM;
- gọi dataset/qrels là human gold;
- tạo retrieval logic riêng trong Streamlit;
- thêm system vào main table mà không đưa vào pooling;
- sửa expected metric trong unit test để test pass.

Danh sách đầy đủ: **`SPEC.md` mục 16**.

---

## Những hạn chế phải giữ trong paper

Không được viết claim vượt quá `SPEC.md` mục 1.

Paper phải nêu ít nhất:

- query tổng hợp do LLM sinh và nhãn do LLM gán, chỉ kiểm chứng bằng người trên mẫu; có lỗi và thiên lệch của LLM;
- pool chưa đầy đủ; chồng lấn giữa các split tùy protocol OI-12;
- điểm trên dataset không tự chứng minh chất lượng với người dùng thật;
- in-batch negative có thể vô tình chứa Điều liên quan;
- OOD chỉ khoảng 40 câu nên statistical power thấp;
- MVP không xử lý near-duplicate;
- Recall@k là **relative recall theo pooled qrels**, không phải exhaustive recall;
- mỗi cấu hình chỉ chạy một seed.

---

## Đọc mục nào trong `SPEC.md` khi làm việc gì

| Việc | Mục cần đọc |
|---|---|
| Luật chung, change procedure | 0 |
| Objective, claim, limitations | 1 |
| Research questions | 2 |
| Tải dữ liệu, lọc, parse, chunk, dedup, `validate_data` | 3 |
| Họ văn bản, split dataset, leakage | 4 |
| Sinh query, kiểm tra query, lexical overlap, variants | 5 |
| OOD | 6 |
| Retriever, E5 encode, manifest, BM25 tạo dataset và BM25 tuning, RRF | 7 |
| Training, positive, hard negative, LR/checkpoint | 8 |
| Pool tạo dataset, pool đánh giá, qrels freeze | 9 |
| Gán nhãn LLM, pilot, kiểm tra và tạo dataset, provenance | 10 |
| Metric, significance test, judged coverage, analysis dimensions | 11 |
| Error analysis | 12 |
| Repo structure, artifacts, reproducibility, README | 13 |
| Streamlit app | 14 |
| Freeze order | 15 |
| Danh sách cấm | 16 |
| Vấn đề còn mở (OI-11, OI-12, OI-13, OI-15, OI-16); OI-10 và OI-14 đã chốt | 17 |

---

## Trước khi kết thúc mỗi phiên

- Không tự sửa methodology.
- Không để code/config lệch `SPEC.md`.
- Ghi rõ file nào đã tạo/sửa.
- Ghi rõ test nào đã chạy và kết quả.
- Nếu đang bị chặn bởi quyết định của người, **dừng ở trạng thái an toàn và nêu chính xác cần người quyết định gì**.

---

## Quy tắc quản lý file và commit

### 1. Hai vùng làm việc

**Vùng chia sẻ qua Git**

Các vị trí hợp lệ gồm `src/`, `scripts/`, `tests/`, `configs/`,
`notebooks/`, `reports/`, `docs/` và `data/` đối với artifact được SPEC yêu cầu.

Việc nằm trong một thư mục trên không tự động có nghĩa file được commit.
Mỗi file vẫn phải đáp ứng điều kiện ở mục 2.

**Vùng local**

Dùng `.scratch/`, được loại bằng `.gitignore`.

Vùng này chứa ghi chú phiên, câu hỏi tạm, kế hoạch làm việc, bảng debug,
bản nháp bàn giao, script dùng một lần và output trung gian.

Pipeline, test và notebook chính thức không được dùng file trong `.scratch/`
làm đầu vào bắt buộc. Khi một file trở nên cần thiết cho dự án, phải chuyển nó
sang vị trí chính thức, đặt tên rõ và ghi chức năng trước khi commit.

Không cần thêm `.scratch/` vào `.git/info/exclude` nếu nó đã có trong
`.gitignore`. `.git/info/exclude` chỉ dùng cho ngoại lệ cá nhân trên từng máy.

### 2. Khi nào một file được vào vùng chia sẻ

File chỉ được commit khi có ít nhất một chức năng rõ ràng:

- chạy hệ thống hoặc pipeline;
- được code khác import hoặc gọi;
- có entry point được ghi trong README hoặc Makefile;
- là test bảo vệ hành vi quan trọng;
- chứa cấu hình cần để tái lập;
- là artifact bắt buộc theo SPEC;
- là báo cáo, bảng hoặc hình cuối dùng cho paper, slide hay kiểm chứng kết quả.

Định dạng và nơi lưu do SPEC chỉ định phải tuân theo SPEC, ví dụ run file TREC,
CSV/PNG ở mục 11.3 và artifact trong `reports/data_stats/`.

Ngoài trường hợp SPEC yêu cầu:

- không xuất cùng một nội dung thành nhiều định dạng nếu không có nơi sử dụng
  riêng cho từng định dạng;
- mỗi phase ưu tiên một báo cáo chính;
- file dữ liệu hỗ trợ chỉ commit khi được báo cáo, notebook hoặc bước pipeline
  khác trực tiếp tham chiếu;
- file sinh lại được nhưng không được sử dụng trực tiếp thì để local.

Bằng chứng người duyệt mà SPEC yêu cầu, gồm số liệu leakage mục 4.3, nhãn thô,
`FROZEN.md` và thông tin người duyệt split, được commit. Bảng debug hoặc nhận
xét trung gian của agent không commit.

Số dùng trong paper phải được sinh từ script. Notebook dùng để khám phá và
trình bày, không chứa một phiên bản pipeline riêng và không trở thành nguồn số
liệu độc lập.

Mỗi số liệu chỉ có một nguồn chính. `CHANGELOG` chỉ ghi quyết định, lý do và
đường dẫn tham chiếu; không sao chép lại bảng số liệu.

### 3. Khi tạo file ngoài `.scratch/`

Trước khi tạo, phải trả lời được:

1. File thực hiện chức năng gì?
2. Code, notebook hoặc người nào sử dụng?
3. File có thể sinh lại không và bằng lệnh nào?
4. File thuộc task hoặc phase nào?
5. File là sản phẩm cuối hay chỉ là trung gian?

Nếu không trả lời được thì tạo file trong `.scratch/`.

File máy sinh được commit phải có nơi ghi script/lệnh sinh lại, trực tiếp trong
README liên quan hoặc tài liệu của phase.

### 4. Nhánh và commit

- Mỗi task dùng một nhánh riêng theo quy ước `task/<số>-<tên>`.
- Không trộn preprocessing, split, query generation, training và app trong cùng
  một commit.
- Code chưa hoàn thiện nhưng cần chia sẻ được commit WIP trên nhánh task.
- Commit WIP không merge trực tiếp vào nhánh chính; phải review và squash hoặc
  chỉnh lại lịch sử trước khi merge.
- Không chờ đến cuối dự án mới commit và dọn toàn bộ.
- Artifact đã ghi hash trong `data/FROZEN.md` không được sửa trong commit
  thông thường. Mọi thay đổi phải theo mục 0 của SPEC và ghi vào Changelog.

Một nhánh chỉ được đưa vào nhánh chính khi:

- test liên quan đạt;
- phạm vi chỉ thuộc một task;
- danh sách file đã được kiểm kê;
- không chứa file local hoặc output trung gian;
- người phụ trách đã duyệt.

### 5. Trước mỗi commit

- Không dùng `git add -A`, `git add .` hoặc stage toàn repo.
- Liệt kê từng file dự định commit kèm chức năng.
- Stage bằng đường dẫn cụ thể.
- Kiểm tra `git diff --cached`.
- Dùng `git diff --ignore-cr-at-eol` để phát hiện thay đổi chỉ do EOL.
- File chỉ khác EOL không đưa vào commit chức năng.
- Nếu cần chuẩn hóa EOL, thực hiện bằng một commit housekeeping riêng.
- Quét `.env`, API key, token và secret.
- Liệt kê mọi file lớn hơn 1 MB kèm lý do cần commit.
- Không commit model, checkpoint, index, dữ liệu tải về, SQLite, cache hoặc
  artifact bị SPEC 13.2 loại khỏi Git.
- File thuộc task khác để lại cho nhánh tương ứng.
- Không tự xóa, di chuyển, stage, commit, push hoặc merge thay đổi của người
  khác.
- Chỉ push khi người dùng cho phép.
- Khi chưa chắc file có cần chia sẻ hay không, để local và báo lại.
