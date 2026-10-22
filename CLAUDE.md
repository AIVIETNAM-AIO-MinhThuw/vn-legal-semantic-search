# CLAUDE.md — Đề tài 8: Tìm kiếm ngữ nghĩa văn bản pháp luật

`SPEC.md` là **nguồn sự thật duy nhất** về methodology. File này chỉ là bản tóm tắt để Claude Code đọc ở đầu mỗi phiên.

Nếu `CLAUDE.md` và `SPEC.md` khác nhau, **`SPEC.md` thắng**. Trước khi làm một phần việc, đọc đúng mục tương ứng trong `SPEC.md` theo bảng cuối file này.

---

## Quy tắc cứng — không được tự thay đổi

- Đơn vị truy hồi, gán nhãn và tính metric = **Điều**. Chunk chỉ dùng để encode/index; điểm Điều = **MaxP**.
- Mọi chunk **bắt buộc** `≤ 450 token` theo tokenizer E5 (kể cả tiền tố); `validate_data` dừng với lỗi nếu vi phạm. Điều dài tách theo **Khoản → câu → cửa sổ token**. Nếu một câu `> 450 token`, cắt theo token với **overlap 50 token** và ghi log `article_id`.
- `validate_data` chạy **sau parse/chunk, trước split**.
- Split 80/10/10 theo **họ văn bản** bằng union-find trên quan hệ sửa đổi/bổ sung/thay thế; union-find chạy trên dataset gốc trước khi lọc. Không sửa `splits.json` sau khi đã có query test.
- Query train và hard negative chỉ lấy từ split train. Không đưa bất kỳ dữ liệu val/test/OOD nào vào training.
- Query đã được người sửa câu chữ phải chạy lại kiểm tra **chép nguyên văn N = 8 âm tiết** trước khi được giữ.
- E5: `query: ` / `passage: ` gắn **đúng một lần trong một hàm duy nhất**; `max_length = 512`; mean pooling; L2 normalize; float32; exact search; không truncate passage âm thầm.
- Mỗi index có `manifest.json`; config/manifest không khớp thì **dừng với lỗi**. Evaluation và app dùng chung loader/retriever.
- 5 hệ thống chính:
  - S1 BM25 — tune `k1`,`b` trên val;
  - S2 e5 zero-shot;
  - S3 fine-tune A — in-batch negative;
  - S4 fine-tune B — A + 1 hard negative;
  - S5 RRF — S1 + dense tốt hơn trên val, `k = 60`.
- Learning rate chỉ tune trên A với `{1e-5, 3e-5}`, tối đa 2 epoch. B dùng **cùng LR, batch size, epoch budget và seed**; A/B chỉ khác hard negative.
- Mọi lựa chọn model/config/chkpt chỉ dựa trên **val**.
- Test/OOD chỉ chạy metric hiệu năng **một lần** sau khi qrels freeze. Trước đó chỉ kiểm tra integrity, không in metric hiệu năng.
- Pooling tăng dần, depth = 10. Mọi system trong main table phải đóng góp vào pool trước khi freeze qrels.
- **Final qrels hoàn toàn do người gán.** LLM draft label chỉ dùng đo agreement; không hiển thị, không sắp thứ tự, không chọn cặp, không làm nhãn cuối.
- Annotation calibration: 5 người cùng chấm 20 cặp val. Đồng thời đo tốc độ chấm. Nếu cần giảm/tăng quy mô đánh giá thì chỉ được thay đổi **trước pool v1** qua change procedure.
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

2. **Sau `validate_data`, trước split**
   - báo tỷ lệ cạnh `relationships` không ánh xạ được;
   - báo các lỗi dữ liệu quan hệ;
   - chờ người xác nhận rồi mới split.

3. **Khi cần đổi methodology**
   - mô tả vấn đề;
   - đề xuất thay đổi;
   - nêu ảnh hưởng tới methodology và artifact đã tạo;
   - **dừng chờ người duyệt**;
   - nếu được duyệt, cập nhật Changelog trong `SPEC.md`.

4. **Khi `SPEC.md` không nói rõ hoặc có thể hiểu theo hai cách**
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
- tự thay đổi cách split khi `relationships` có vấn đề;
- tự chọn lĩnh vực hoặc relation mapping;
- dùng LLM/Claude để viết, gợi ý hay sửa OOD query;
- cho annotator thấy system source, rank, score, LLM label hoặc provisional metric;
- để LLM quyết định final label;
- tạo retrieval logic riêng trong Streamlit;
- thêm system vào main table mà không đưa vào pooling;
- sửa expected metric trong unit test để test pass.

Danh sách đầy đủ: **`SPEC.md` mục 16**.

---

## Những hạn chế phải giữ trong paper

Không được viết claim vượt quá `SPEC.md` mục 1.

Paper phải nêu ít nhất:

- val chỉ có nhãn Điều nguồn và query val do cùng LLM sinh;
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
| Split, union-find, leakage | 4 |
| Sinh query, sửa query, lexical overlap, variants | 5 |
| OOD | 6 |
| Retriever, E5 encode, manifest, BM25 tuning, RRF | 7 |
| Training, hard negative, LR/checkpoint | 8 |
| Incremental pooling, qrels freeze | 9 |
| Annotation tool/protocol | 10 |
| Metric, significance test, judged coverage, analysis dimensions | 11 |
| Error analysis | 12 |
| Repo structure, artifacts, reproducibility, README | 13 |
| Streamlit app | 14 |
| Freeze order | 15 |
| Danh sách cấm | 16 |
| OI-10: lĩnh vực + relation mapping | 17 |

---

## Trước khi kết thúc mỗi phiên

- Không tự sửa methodology.
- Không để code/config lệch `SPEC.md`.
- Ghi rõ file nào đã tạo/sửa.
- Ghi rõ test nào đã chạy và kết quả.
- Nếu đang bị chặn bởi quyết định của người, **dừng ở trạng thái an toàn và nêu chính xác cần người quyết định gì**.
