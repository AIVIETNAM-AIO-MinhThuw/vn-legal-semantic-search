# Bàn giao baseline và pilot gán nhãn — 2026-10-25

> **Đã dừng (2026-10-26).** Luồng gán nhãn bằng LLM trong tài liệu này không dùng cho bản nộp; dataset dùng nhãn Điều nguồn (`scripts/build_source_qrels.py`). Xem Changelog SPEC ngày 2026-10-26. Code (`src/annotation/`, `scripts/build_labeled_dataset.py`) giữ lại làm lịch sử.

## Trạng thái bàn giao

**ĐÃ XÁC MINH:** BM25 S1₀ và E5 zero-shot S2 đã chạy trên cùng 500 query và 14.281 chunk; mỗi hệ thống xuất 5.000 cặp query–Điều. Pipeline đã hợp nhất top-10 Điều mỗi hệ thống theo `(query_id, article_id)`, không cộng điểm hoặc dùng RRF, rồi gọi Gemini API thật cho pilot 10 query, 171 cặp.

**NEEDS_HUMAN_REVIEW:** 152 cặp qua kiểm tra kỹ thuật, chưa chứng minh nhãn đúng về nội dung. Có 18 cặp thuộc query Q0046 bị giữ lại vì phản hồi trả thêm ID ngoài pool ở cả ba lần thử; một cặp Q0218 có evidence không khớp nguyên văn. Mẫu blind có 27 cặp: 10 nhãn 0, 10 nhãn 1, 7 nhãn 2. Không bù số thiếu bằng nhãn khác. Sáu ví dụ hướng dẫn có nguồn từ pool thật, trạng thái `unverified`, không được dùng tính agreement.

**CHƯA HOÀN TẤT:** kiểm chứng của người, agreement/kappa, phân xử bất đồng, xử lý 19 cặp tồn, nghiệm thu pilot, dataset chính thức, split, training và đánh giá retrieval. Chưa được chạy hàng loạt khi chưa chốt OI-13. Split chờ OI-12; các quyết định khác theo SPEC. Không sửa `data/FROZEN.md` trong bàn giao này.

Nguồn số là `summary.json` của hai baseline, `annotation_pilot_v1/validation_v1/report.json`, `review_v1/selection.json` và các `attempts/*/record.json`. Không coi thành công API hoặc schema hợp lệ là chất lượng đạt.

## Những gì cần nhận

### Qua GitHub

Nhận cùng phiên bản của `SPEC.md`, `CLAUDE.md`, code trong `src/retrieval/`, `src/annotation/`, các script tải/chạy, ba config `bm25.yaml`, `e5.yaml`, `annotation.yaml`, các file requirements, prompt, guideline, examples và test. Điểm vào là `scripts/run_bm25.py`, `scripts/run_e5.py`, `scripts/build_labeled_dataset.py`.

Mốc code kiểm tra khi lập tài liệu: nhánh `task/6-labeling-pipeline`, HEAD `2942afde55473969a1f8827c26a3f01e7b42752b`; working tree sạch trước khi thêm tài liệu này. Đây là SHA nền; commit chứa báo cáo sẽ có SHA khác. Người bàn giao cần cung cấp commit cuối thực tế. Chưa xác minh commit đã có trên remote; tài liệu này không thực hiện push.

### Gói dữ liệu gửi riêng

Giải nén vào thư mục gốc repo, giữ nguyên cấu trúc:

```text
data/
  processed/                         # toàn bộ dữ liệu processed đang dùng
  interim/
    semantic_queries_500.csv          # bản CSV nguyên gốc, chỉ đổi vị trí lưu
    bm25_s10/                        # run.trec, candidates, summary, warnings
    e5_s2/                           # tương tự BM25
    annotation_pilot_v1/              # toàn bộ, kể cả manifest và attempts
```

CSV gốc trên máy bàn giao ở `C:/Users/Vu/Downloads/semantic_queries_500.csv`; chép nguyên byte vào vị trí trên hoặc dùng `--queries` với đường dẫn thực. SHA-256 CSV phải là `bde66b9897c5af76bbdf88f1216ba684c086062fe2ddf7d0fd1423a8dddc2b44`.

Giữ `pool.jsonl`, `requests.jsonl`, `manifest.json`, toàn bộ `attempts/`, `validation_v1/`, `review_v1/` trong gói pilot: cần chúng để đối chiếu nhãn và tiếp tục mà không gọi lại API. `annotation/examples.jsonl` tham chiếu pool ở `data/interim/annotation_pilot_v1`; chỉ clone repo sẽ chưa đủ để nạp ví dụ.

Không gửi API key, `.env`, `.venv`, cache, model E5, VNCoreNLP hoặc index. Các phần có thể dựng lại được hướng dẫn bên dưới. Nếu chỉ tiếp tục kiểm chứng pilot, không cần tải model hay dựng index.

**Người chấm blind chỉ nhận** `review_v1/sample.csv`, `review_v1/pending.csv` và `annotation/GUIDELINE.md`. Không cho xem `private_sample.jsonl`, nhãn Gemini, pool có nguồn/rank/score trước khi chấm. Người tiếp quản kỹ thuật được nhận cả gói nhưng nên là người khác với người chấm độc lập.

## Cài môi trường trên Windows PowerShell

Mọi lệnh bên dưới chạy từ thư mục gốc repo. Dùng Python 3.11 64-bit và Java 64-bit. Máy đã chạy E5 dùng NVIDIA RTX 4050 Laptop, PyTorch 2.5.1+cu121. Cấu hình mặc định yêu cầu CUDA; không tự fallback CPU.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements.txt -r requirements-bm25.txt -r requirements-e5.txt
$queryCsv = (Resolve-Path 'data/interim/semantic_queries_500.csv').Path
Get-FileHash -Algorithm SHA256 -LiteralPath $queryCsv
```

Cài Java và đặt `JAVA_HOME` tới thư mục cài Java thực tế trên máy nhận, không phải thư mục `bin`. Kiểm tra trước khi chạy BM25:

```powershell
if (-not $env:JAVA_HOME) { throw 'Cần cấu hình JAVA_HOME trước' }
& (Join-Path $env:JAVA_HOME 'bin/java.exe') -version
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print('CUDA available:', torch.cuda.is_available())"
```

Nếu không có GPU NVIDIA phù hợp: dùng bản sao config E5, đặt `runtime.device: cpu` trước build; cài biến thể torch CPU cùng phiên bản thay cho dòng CUDA trong requirements E5. Quy trình CPU chưa kiểm chứng trên máy nhận. Đổi runtime/model/encoding cần index mới, không tái sử dụng manifest cũ. Không đổi tham số chỉ để vượt kiểm tra manifest.

## Tải lại phần không gửi: VNCoreNLP và E5

Chỉ chạy khi thư mục đích chưa tồn tại. Không xóa artifact đang có để ép chạy lại. Bước tải cần mạng; BM25/E5 inference sau đó chạy local, không gọi API.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/download_vncorenlp.py --config configs/bm25.yaml --url-template 'https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/{revision}/{file}' --timeout 60
.\.venv\Scripts\python.exe -X utf8 scripts/download_e5.py --config configs/e5.yaml
```

VNCoreNLP được lưu ở `data/raw/vncorenlp/`, revision đọc từ config. E5 `intfloat/multilingual-e5-base` ở `data/raw/multilingual-e5-base/`, revision `d128750597153bb5987e10b1c3493a34e5a4502a`, kèm tokenizer và `download.json` có checksum. Không chỉ tải weights rồi bỏ tokenizer. E5 dùng văn bản tự nhiên, không nhận đầu ra tách từ VNCoreNLP.

## Dựng lại index, giữ kết quả baseline đã nhận

Gói bàn giao đã có `data/interim/bm25_s10/` và `e5_s2/`. Vì script cấm ghi đè, dùng `--output` mới khi dựng index chưa được gửi:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries $queryCsv --build --output data/interim/bm25_rebuild_v1
.\.venv\Scripts\python.exe -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries $queryCsv --build --output data/interim/e5_rebuild_v1
```

Index mới ở `indexes/bm25_s10/`, `indexes/e5_s2/`. Mỗi output có `run.trec`, `candidates.jsonl`, `warnings.jsonl`, `summary.json`. Đối chiếu summary: 500 query, 14.281 chunk, 5.000 cặp mỗi baseline; xem warnings, source hashes và config. Không khẳng định kết quả E5 giống byte giữa phần cứng khác nhau.

Nếu không nhận hai thư mục kết quả baseline và dựng từ đầu trên máy sạch, bỏ `--output` trong hai lệnh để tạo đúng đường dẫn mặc định. Không chạy cách này nếu output mặc định đã tồn tại.

Những lần sau bỏ `--build` để nạp index, vẫn xuất sang thư mục mới:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries $queryCsv --output data/interim/bm25_replay_v1
.\.venv\Scripts\python.exe -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries $queryCsv --output data/interim/e5_replay_v1
```

Tên hậu tố `v1` là ví dụ; nếu đích đã tồn tại, chọn tên mới. Tham số thí nghiệm nằm trong YAML. Khi giữ nguyên pilot hiện tại, tiếp tục dùng baseline gốc đã bàn giao; không thay baseline của pilot bằng kết quả mới mà giữ manifest cũ.

## Tiếp tục pilot đã nhận — không cần gọi API

Kiểm tra lại response đã lưu, xuất sang thư mục mới:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/build_labeled_dataset.py --config configs/annotation.yaml validate --output data/interim/annotation_pilot_v1/validation_received_v1
```

Kết quả hiện tại phải có 152 accepted, 19 pending nếu toàn bộ đầu vào/protocol giữ nguyên. Đọc `accepted.jsonl`/`pending.jsonl` để xem nhãn và lỗi; người chấm độc lập không đọc các file này trước khi chấm.

Sử dụng CSV `review_v1/` đã nhận, hoặc xuất lại sang đích mới:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/build_labeled_dataset.py --config configs/annotation.yaml review-export --output data/interim/annotation_pilot_v1/review_received_v1
```

Người chấm đọc query, tên văn bản, số/tiêu đề và body, điền `human_label` (0/1/2), `reviewer`, `note`. Nhãn 2 trả lời đầy đủ, 1 hữu ích một phần, 0 không giúp trả lời. Thiếu căn cứ thì để trống và ghi lý do, không ép thành 0. Giữ nguyên `candidate_id` và các cột dữ liệu, lưu UTF-8; CSV có body nhiều dòng nên dùng trình đọc CSV đúng chuẩn.

Để trống `adjudicated_label`/`adjudicator` ở lần chấm độc lập. Bất đồng với LLM cần người thứ hai phân xử, kèm lý do, không ghi đè nhãn người ban đầu. Chấm `pending.csv` riêng; các cặp đó không thuộc mẫu tính agreement. Hai CSV có thể import riêng vào hai thư mục mới; CLI hiện không có chức năng tự gộp nhiều lần import thành một bộ nhãn cuối.

Ví dụ nhập mẫu người chấm đã lưu thành `sample_completed.csv` trong `review_v1/`:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/build_labeled_dataset.py --config configs/annotation.yaml review-import --input data/interim/annotation_pilot_v1/review_v1/sample_completed.csv --review-dir data/interim/annotation_pilot_v1/review_v1 --output data/interim/annotation_pilot_v1/human_sample_v1
```

Đầu ra `human.jsonl`, `report.json` lưu nhãn LLM, nhãn người, nhãn cuối và trạng thái phân xử; report có raw agreement, linear weighted kappa và confusion matrix. Chỉ mô tả mẫu cân bằng theo nhãn, không diễn giải thành độ chính xác của cả dataset. Dùng đúng `--review-dir` đã sinh CSV đang chấm.

## Khi cần gọi Gemini lại

Chỉ người tiếp quản kỹ thuật thực hiện. Lệnh có phí và gửi nội dung query/Điều tới Gemini. Dùng API key riêng qua biến môi trường `GOOGLE_API_KEY`; code hiện đọc môi trường, không tự nạp `.env`. Ví dụ nhập key trong phiên PowerShell mà không lưu giá trị vào command history:

```powershell
$secretKey = Read-Host 'Gemini API key' -AsSecureString
$credential = [System.Net.NetworkCredential]::new('', $secretKey)
$env:GOOGLE_API_KEY = $credential.Password
.\.venv\Scripts\python.exe -X utf8 scripts/build_labeled_dataset.py --config configs/annotation.yaml label
Remove-Item Env:GOOGLE_API_KEY
Remove-Variable secretKey, credential
```

Model/config hiện tại: `gemini-3.5-flash-lite`, temperature 1.0, tối đa 8.192 output token, thinking minimal, tối đa ba lần thử/query. Lệnh chạy tiếp bỏ qua query có record hoàn tất cùng request hash; query chưa hoàn tất được gọi lại. Q0046 có thể tái diễn lỗi; không chạy lặp vô hạn hoặc tự chấp nhận ID thừa. Sau khi gọi lại, validate và review-export sang thư mục mới; không trộn sample cũ và mới.

`attempts/` giữ request, response và trạng thái từng lần gọi, không xóa lịch sử. Không chạy hai tiến trình trên một run. Nếu có `.label.lock` sau sự cố, chỉ xử lý khi đã xác minh tiến trình cũ không còn chạy. Resume chưa được kiểm chứng bằng thử nghiệm ngắt tiến trình thật.

Nếu đổi prompt/guideline/examples/model để sửa lỗi, giữ nguyên run cũ, tăng version protocol và chuẩn bị pilot mới bằng bản sao config với `paths.run` mới. Lệnh chuẩn bị là:

```powershell
# configs/annotation_pilot_v2.yaml phải được người tiếp quản tạo và đối chiếu trước.
.\.venv\Scripts\python.exe -X utf8 scripts/build_labeled_dataset.py --config configs/annotation_pilot_v2.yaml prepare --queries $queryCsv
```

Không chạy `prepare` lại trên run đã nhận. Config phải giữ đúng nguồn baseline, corpus, ví dụ và quyết định pilot; config đã chuẩn bị có hash trong manifest. Nhãn API chạy lại có thể khác; chỉ response đã lưu mới tái hiện đúng lần pilot đang bàn giao.

## Điểm dừng và hạn chế của code hiện tại

- Hoàn thành kiểm chứng, phân xử và báo cáo lỗi rồi mới xin nhóm chốt ngưỡng chấp nhận OI-13. Không tự bật bulk hoặc kết luận pilot đạt.
- `finalize` có CLI nhưng chưa nghiệm thu end-to-end. Config hiện trỏ tới `annotation_metadata.jsonl` chưa có; export có thể dừng ngay do thiếu file, kể cả `--draft`. Không hướng dẫn coi đây là dataset chính thức.
- Chưa hoàn thiện/xác minh việc dùng `annotation_exclusions.jsonl`, quy tắc hard negative và gộp nhiều bộ human import. Người tiếp quản cần đối chiếu SPEC và xử lý trước export chính thức.
- Metadata nguồn, `dup_group_id`, source group cần xác minh; không suy từ rank 1 hoặc tự lấy `intent_id` làm nhóm trùng ý. Split, training và qrels freeze chưa thực hiện.
- Chưa kiểm chứng toàn bộ môi trường máy sạch, CPU, resume khi crash hoặc toàn bộ nhánh lỗi API. Không cam kết chỉ clone repo là chạy được nếu chưa nhận dữ liệu.

## Kiểm tra khi nhận bàn giao

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_annotation.py tests/test_bm25.py tests/test_e5.py
```

ĐÃ XÁC MINH ngày 2026-10-25: lệnh trên đạt **24 passed** (6 annotation, 10 BM25, 8 E5). Đây là kiểm tra offline, không gọi Gemini và không phải nghiệm thu chất lượng dataset. Người nhận vẫn chạy lại và ghi kết quả trên máy mình. Đối chiếu checksum nguồn trong manifest và kết quả validate; yêu cầu người bàn giao gửi lại đúng file nếu mismatch, không sửa hash để bỏ qua lỗi.

Chi tiết baseline: [BM25](bm25.md), [E5](e5.md). Quy định phương pháp và điểm chờ: [SPEC](../../SPEC.md), [CLAUDE](../../CLAUDE.md). API/UI chưa tích hợp baseline trong phạm vi bàn giao này.

## Checksum để đối chiếu gói bàn giao

SHA-256 dưới đây được đọc trực tiếp từ file khi lập báo cáo; không bao gồm API key. Manifest baseline/pilot chứa checksum chi tiết cho các file khác.

| File | SHA-256 |
|---|---|
| `configs/annotation.yaml` | `df1a3966527077dd42390da02bc4669c9295ed15481ff64fae14739671b205a8` |
| `prompts/relevance_v1.txt` | `3684227512d2f5c2cdadbe24e5e1752e2df2468c693943f26176a1153138fc26` |
| `annotation/GUIDELINE.md` | `600135d865a7b66b79157ddeca5533c3fbdaf898e8a3484dd32d0c754c4ede03` |
| `annotation/examples.jsonl` | `e9fb349932bb4da0c3cb6e914828f60014b9297aaa57d99ff7a7e72232d4e83b` |
| `data/processed/chunks_index.jsonl` | `f82c95585e41dce541cd73d5e021067666a1652965393f9d5fe1f4a58e59387d` |
| `data/processed/articles_index.jsonl` | `4597ae7a7f08129fa224cfd829845ed7df751ec747097b0e674b664bdb86e30e` |
| `data/processed/docs_index.jsonl` | `22dd377eeb4f5f08881d5c3da765e07c9e1c6870d751d741b228a9e9f2af3962` |
| `data/interim/annotation_pilot_v1/manifest.json` | `b6dfaad1e5764e1d5f9ab872d9325a398c6f81528b378361feaaaac4b045bdb7` |
| `data/interim/annotation_pilot_v1/validation_v1/report.json` | `230f7e14b2d50aafe74ddf0d0ddca73f86cafee9c044294c32437f2c01164947` |
| `data/interim/annotation_pilot_v1/review_v1/selection.json` | `db77503bc386fb19a2616f9734962fa07685684bf2b4ff6719f4c231bd6f2c96` |

## Tiếp quản query đã xử lý và pilot v2 — 2026-10-25

Đây là bàn giao **chuẩn bị chạy**, chưa phải kết quả pilot v2 hoặc phê duyệt
gán nhãn hàng loạt. Kết quả pilot v1 ở trên thuộc bộ 500 query thử cũ.

### Phần nhận từ Git

- Code BM25/E5/annotation, prompt và guideline hiện có.
- `configs/annotation_pilot_v2.yaml`: đường dẫn và 10 query đề xuất của pilot mới;
  giữ protocol/model của config annotation cũ, `selection.mode: pilot`, chưa có approval.
- `scripts/check_query_keyword_length.py`: đếm từ keyword bằng đúng segmenter BM25,
  chỉ gắn cờ trên 4 từ; không loại hoặc sửa query.

Không cần nhận cả bản sao project bằng ZIP. Nhận commit chứa cập nhật này trên
nhánh Task 6; kiểm tra thay đổi local trước khi pull, không reset công việc đang làm.

### Phần gửi riêng, giữ nguyên byte

1. Gói `handoff_task6_pilot_v2/`: `pilot/pilot_queries_v2.csv`, bộ query v1/v2,
   báo cáo, decision log, merge manifest và provenance 61 lượt. Gói đang là dữ liệu
   nháp: 4.776 dòng trước xử lý, 4.641 query được đánh dấu dùng được ở v2; còn các
   đề xuất cần người xác nhận và `dup_group_id` chưa chốt.
2. Ba file `data/processed/{articles,docs,chunks}_index.jsonl` nếu máy nhận chưa có
   bản đúng checksum trong bảng phía trên. Không cần nhận lại nếu hash khớp.

Sau giải nén vào đường dẫn ngắn như `C:/T6/`, từ **gốc repo của máy nhận**:

```powershell
# Chỉ chép khi file đích chưa có; nếu đã có thì đối chiếu hash trước.
New-Item -ItemType Directory -Force data/interim/pilot_v2 | Out-Null
# Thay đường dẫn nguồn bằng vị trí gói vừa giải nén trên máy nhận.
if (Test-Path -LiteralPath 'data/interim/pilot_v2/pilot_queries_v2.csv') { throw 'File pilot đã có; kiểm tra hash trước khi chép.' }
Copy-Item -LiteralPath 'C:/T6/handoff_task6_pilot_v2/pilot/pilot_queries_v2.csv' -Destination data/interim/pilot_v2/pilot_queries_v2.csv
Get-FileHash -LiteralPath data/interim/pilot_v2/pilot_queries_v2.csv -Algorithm SHA256
```

Hash phải khớp dòng pilot CSV trong `CHECKSUMS.sha256` của gói. Không lưu lại CSV
bằng Excel. Bộ 4.641 câu nằm trong
`query_data/query_processing_v2/out/queries_usable_v2_DRAFT.csv` của gói; không
dùng bộ đó thay file 10 câu để chạy pilot.

### Chạy pilot trên máy tiếp quản

Kiểm tra môi trường/model/index theo các phần trước của tài liệu và README trong
gói. Nếu chưa có index thì thêm `--build` cho baseline tương ứng. Nếu loader báo
manifest không khớp, dừng đối chiếu, không sửa manifest để chạy cho qua.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries data/interim/pilot_v2/pilot_queries_v2.csv --output data/interim/pilot_v2/bm25_s10
.venv/Scripts/python.exe -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries data/interim/pilot_v2/pilot_queries_v2.csv --output data/interim/pilot_v2/e5_s2
.venv/Scripts/python.exe -X utf8 scripts/build_labeled_dataset.py --config configs/annotation_pilot_v2.yaml prepare
```

Sau đó dùng quy trình examples-import → label → validate → review-export →
review-import trong README của gói, luôn truyền config pilot v2. Người thật chấm
few-shot, kiểm chứng blind và phân xử. Không tự điền nhãn người; chưa gọi API nếu
người tiếp quản chưa xác nhận quota/chi phí. Chạy bulk phải có quyết định OI-13 và
approval hợp lệ, không tự coi xong pilot là được chạy bulk. Metadata/exclusions
và finalize cho bulk còn phải được chuẩn bị và kiểm tra; chưa split/train/freeze.

Sau khi máy nhận có VNCoreNLP, có thể đếm keyword song song:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/check_query_keyword_length.py --queries C:/T6/handoff_task6_pilot_v2/query_data/query_processing_v2/out/queries_usable_v2_DRAFT.csv --output data/interim/keyword_word_check_v2
```

Điều chỉnh đường dẫn gói cho máy nhận; output phải mới. Ba script xử lý v1/v2 và
chọn mẫu hiện là hồ sơ tái lập theo riêng lượt dữ liệu, còn chứa đường dẫn local
và đề xuất theo ID, nên giữ trong gói provenance; pipeline annotation không gọi
chúng. Không force-add `.scratch/`, corpus, model hoặc index vào Git.
