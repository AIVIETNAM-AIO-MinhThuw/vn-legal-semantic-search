# Tìm kiếm ngữ nghĩa văn bản pháp luật tiếng Việt

Đồ án NLP — Đề tài 8. Mục tiêu là tìm các **Điều** pháp luật liên quan đến câu hỏi tiếng Việt. Chunk phục vụ xử lý và lập chỉ mục; đơn vị kết quả là Điều.

Methodology và các quyết định đã duyệt nằm trong [SPEC.md](SPEC.md). Quy tắc làm việc và các điểm chờ nằm trong [CLAUDE.md](CLAUDE.md). Tài liệu trình bày không thay thế hai file này.

## Hướng dẫn chạy (cho người clone repo)

### Đóng gói nguyên ứng dụng main cho máy CPU

Deploy web dùng chung cho người dùng Windows/macOS: [các bước chuyển bundle, chạy server và tạo link HTTPS](docs/deploy_cpu.md). Người dùng chỉ cần trình duyệt; Docker chạy trên server Linux/amd64.

Trên nhánh `task/TestCheckErrorDocker`, dùng ZIP và file checksum đã tải ở thư mục cha:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/package_deploy.py --zip ..\vnlegal-demo-v1.zip --checksum ..\vnlegal-demo-v1.sha256
cd release\deploy-cpu
docker compose up --build -d --wait --wait-timeout 900
```

Script đọc commit `main` bằng Git archive, giữ nguyên byte source/config của main, chỉ bổ sung Docker/dependency CPU và symlink đường dẫn trong image. `main` và artifact không bị sửa. `RELEASE.json` ghi commit, checksum ZIP và hash từng file; `DEPLOY.md` nằm trong bundle. Script từ chối ghi đè bundle có sẵn. Chép cả thư mục bundle, gồm `artifacts/`, sang máy deploy có Docker Linux/amd64. Windows dùng Docker Desktop Linux containers; không cần GPU hoặc Java trên host.

Hai file `.zip` và `.sha256` không ghép với nhau: checksum kiểm tra ZIP, sau đó 23 file được giải nén và kiểm tra hash vào `artifacts/`, mount chỉ đọc. SQLite dùng volume riêng. UI ở `http://127.0.0.1:8501`, API ở `http://127.0.0.1:8000/docs`. Dừng bằng `docker compose down`, giữ volume khi không thêm `-v`.

Bundle này đóng gói hành vi hiện có trên main; main kiểm tra manifest theo loader cũ, không có đầy đủ kiểm tra provenance/fail-fast của D3. Vì vậy kết quả chạy bundle không phải xác nhận D3/D6 nghiêm ngặt đã đạt. Các mục tiếp theo mô tả checkout tích hợp D1–D6; khi chạy bundle, dùng lệnh trong `release/deploy-cpu/DEPLOY.md`.

Có 4 mức, chọn mức cần dùng. Demo dùng Docker Compose làm đường chạy chính; môi trường Python local là dự phòng. Mức 1–2 không cần GPU.

**Trạng thái nghiệm thu:** gói `vnlegal-demo-v1.zip` đúng checksum nhưng bị loader từ chối do manifest BM25 không khớp môi trường và dense B thiếu provenance. D6 chưa đạt; chưa bàn giao deploy. Xem [kết quả và các chặn D6](docs/phases/docker.md#12-d6--kiểm-thử-tích-hợp-trên-máy-windows-chưa-đạt).

| Mức | Mục đích | Cần | Thời gian |
|---|---|---|---|
| 1 | Xem và tính lại bảng kết quả | Python 3.11 | 2 phút |
| 2 | Chạy demo (giao diện + API) | Python 3.11, Java 64-bit, gói artifact ~1,3 GB | 15 phút |
| 3 | Chạy lại toàn bộ thực nghiệm (train, truy hồi, đánh giá) | GPU NVIDIA ≥ 6 GB, mạng tới Hugging Face | 1–1,5 giờ |
| 4 | Dựng lại từ dữ liệu gốc | Như mức 3 | vài giờ |

### Cái gì nằm ở đâu

| Thành phần | Vị trí | Cách có |
|---|---|---|
| Code, config, test | repo | `git clone` |
| Query (4.641), nhãn, split, query test/val/biến thể | `data/interim/full_v2/queries_v2.csv`, `data/interim/source_qrels_v1/`, `data/splits_v2/`, `data/eval_v1/` | có sẵn trong git |
| Kết quả truy hồi từng hệ thống (`run.trec`, `summary.json`) | `runs/<tập query>/<hệ thống>/` | có sẵn trong git |
| Bảng kết quả, phân tích | `reports/results/` | có sẵn trong git |
| Log train, chọn LR | `models/*/val_metrics.json`, `train_log.jsonl`, `models/lr_selection.json` | có sẵn trong git |
| Corpus đã xử lý, VNCoreNLP, index BM25, index + model E5 fine-tune B | `data/processed/`, `data/raw/vncorenlp/`, `indexes/`, `models/e5_ft_B_lr3e-05/model/` | **gói artifact** `vnlegal-demo-v1.zip` ([Google Drive](https://drive.google.com/drive/folders/1wTvyZm74OFUHFgUwGDfhE6u2H034BoAr?usp=sharing), 1,28 GB) |
| Model gốc E5, SBERT | `data/raw/` | tải bằng script (mức 3) |

### Cài môi trường demo CPU và test

```powershell
git clone https://github.com/AIVIETNAM-AIO-MinhThuw/vn-legal-semantic-search.git
cd vn-legal-semantic-search
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt -r requirements-ui.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Linux: dùng `python3.11 -m venv .venv && source .venv/bin/activate` và `python` thay cho `.\.venv\Scripts\python.exe`. Image hiện nghiệm thu trên Linux/amd64; macOS/ARM chưa được kiểm chứng. Bộ API ghim Torch CPU và cả `sentence-transformers` mà loader manifest yêu cầu. Training mức 3–4 dùng venv riêng và `requirements-train.txt` (Torch CUDA); không cài vào venv demo CPU.

Nếu `python` trỏ tới Windows Store, dùng đường dẫn Python 3.11 đã cài. Nếu dùng `uv`, có thể tạo venv bằng `uv venv --python 3.11 --seed .venv`.

Chạy test không tính lại metric trên test/OOD:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=.scratch/pytest -q
```

### Mức 1 — tính lại bảng kết quả từ run có sẵn

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/evaluate.py --config configs/eval.yaml
```

Ghi ra `reports/results/results.md`. Số liệu phải trùng bản đã commit (metric và bootstrap tất định, seed 42; cột latency lấy từ `summary.json` của lần chạy gốc; cột "Index (MB)" đo thư mục `indexes/`, sẽ bằng 0 nếu chưa giải nén gói artifact).

### Mức 2 — chạy demo

1. Chạy Docker Desktop ở chế độ Linux containers. Dockerfile API có sẵn Java; chỉ đường chạy Python local mới cần Java 64-bit và `JAVA_HOME`. Phiên bản phải khớp manifest BM25; cài Java tùy ý không giải quyết được lỗi provenance.
2. Tải `vnlegal-demo-v1.zip` từ [thư mục Google Drive](https://drive.google.com/drive/folders/1wTvyZm74OFUHFgUwGDfhE6u2H034BoAr?usp=sharing) (SHA-256 của zip: `059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096`), rồi giải nén vào repo (script kiểm tra SHA-256 từng file):
   ```powershell
   .\.venv\Scripts\python.exe -X utf8 scripts/fetch_artifacts.py --zip <đường dẫn>\vnlegal-demo-v1.zip --sha256 059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096
   ```
3. Từ gốc repo, chạy Compose:
   ```powershell
   docker compose up --build -d --wait --wait-timeout 900
   ```
4. Mở `http://localhost:8501`. API và tài liệu endpoint: `http://127.0.0.1:8000/docs`.

Config demo hiện ghim CPU cho cả Docker/local, dùng `./artifacts` chỉ đọc và cùng tham số truy hồi. SQLite Docker ở volume `feedback_data` riêng; local ở `data/app/feedback.sqlite`. Khởi động phụ thuộc storage; chờ tối đa 900 giây, xem lỗi bằng `docker compose logs --tail 80 api`.

Chạy smoke với project riêng (bốn mode và health UI), dừng stack trước để tránh trùng cổng 8000/8501:

```powershell
docker compose down
.\.venv\Scripts\python.exe -X utf8 scripts/smoke_demo.py
```

Smoke tự dừng container của nó và giữ volume feedback. Không thêm `-v` vào lệnh dừng nếu cần giữ feedback. Hai cờ Hugging Face offline ngăn tải model trong runtime; bài kiểm tra chặn mạng ra ngoài riêng được ghi trong tài liệu D6.

Chạy local dự phòng sau khi đặt `JAVA_HOME` tới thư mục runtime tương thích (không trỏ tới `bin`):

```powershell
$env:JAVA_HOME = 'C:\duong-dan\java-runtime'
& "$env:JAVA_HOME\bin\java.exe" -version
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
```

Linux dùng `export JAVA_HOME=/path/to/java-runtime` rồi `bash scripts/run_demo.sh`. Các script chọn `.venv` mặc định; có thể đặt `PYTHON` để chỉ định interpreter khác. Khi thiếu file/sai manifest, API thoát lỗi, UI không được khởi động; không sửa artifact để ép lên healthy.

### Mức 3 — chạy lại toàn bộ thực nghiệm

Cần thêm model gốc và index BM25/E5 zero-shot:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/download_e5.py --config configs/e5.yaml
.\.venv\Scripts\python.exe -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries data/eval_v1/queries_val.csv --output runs/_build_e5 --build
powershell -ExecutionPolicy Bypass -File scripts\run_pipeline.ps1
```

Script pipeline tự tải SBERT, chạy BM25 / SBERT / E5 zero-shot trên `test`, `val`, `test_no_diacritic`, `test_typo`, fine-tune E5 cấu hình A (LR `1e-5`, `3e-5`, chọn trên val) và B (thêm hard negative), truy hồi bằng hai model fine-tune, rồi xuất `reports/results/`. Bước nào đã có output thì bỏ qua; muốn chạy lại từ đầu thì xóa (hoặc đổi tên) `runs/`, `models/e5_ft_*`, `indexes/e5_ft_*`, `indexes/sbert_mminilm`.

Lưu ý tái lập: index BM25/E5 S2 lưu provenance (phiên bản Java, Python, thư viện). Máy khác phiên bản thì `run_bm25.py`/`run_e5.py` từ chối nạp index cũ; dựng lại bằng `--build` vào thư mục index mới và trỏ config tới đó. Fine-tune trên GPU khác có thể lệch nhỏ ở chữ số thập phân cuối dù cùng seed.

### Mức 4 — dựng lại từ dữ liệu gốc

Tải corpus (`scripts/download_data.py`), lọc/parse/chunk (`scripts/prepare_data.py`, `scripts/validate_data.py`) theo các mục bên dưới, rồi:

```powershell
python -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries data/interim/full_v2/queries_v2.csv --output data/interim/full_v2/bm25_s10 --build
python -X utf8 scripts/run_e5.py   --config configs/e5.yaml   --queries data/interim/full_v2/queries_v2.csv --output data/interim/full_v2/e5_s2
python -X utf8 scripts/build_source_qrels.py --queries data/interim/full_v2/queries_v2.csv --output data/interim/source_qrels_v1
python -X utf8 scripts/split_queries.py
python -X utf8 scripts/make_eval_queries.py
```

Query tổng hợp (`queries_v2.csv`) do LLM sinh nên **không sinh lại**; file trong git là artifact gốc. Các script trên không ghi đè output đã có.

### Phương pháp tóm tắt

- Đơn vị kết quả: Điều; index ở mức chunk, gộp về Điều bằng MaxP.
- Nhãn: Điều nguồn của query (pseudo-qrels); split 80/10/10 theo nhóm Điều nguồn + query trùng ý (3.718 / 461 / 462), seed 42.
- Hệ thống: BM25 (VNCoreNLP + unigram, `k1 = 1.2`, `b = 0.75`), SBERT đa ngôn ngữ (MiniLM-L12), E5-base zero-shot, E5 fine-tune A (in-batch negatives), E5 fine-tune B (+1 hard negative/query).
- Metric: P@k, R@k, MRR@10, MAP@10, NDCG@10, latency, kích thước index; paired bootstrap 10.000 lần.
- Quyết định và giới hạn: Changelog trong [SPEC.md](SPEC.md) ngày 2026-10-26.

## Cấu trúc repo

```text
configs/             Tham số, đường dẫn, seed, revision (data, bm25, e5, train_e5, dense_*, eval, app)
scripts/             Entry point từng bước (dữ liệu → nhãn/split → train → truy hồi → đánh giá → demo)
src/                 Module dùng chung: data/, retrieval/, eval/, app/ (service), api/, contracts/, ui/
tests/               Kiểm thử (pytest)
data/processed/      Corpus đã xử lý — gói artifact, không commit
data/interim/        Query, ứng viên top-10, qrels (commit phần nhỏ; xem .gitignore)
data/splits_v2/      Split train/val/test và báo cáo chồng lấn
data/eval_v1/        File query theo split và biến thể test
data/FROZEN.md       Hash và thời điểm freeze theo SPEC
models/              Log train/chọn LR (commit); trọng số model — gói artifact
indexes/             Index BM25/dense — gói artifact hoặc dựng lại
runs/                run.trec + summary.json của từng hệ thống × tập query
reports/results/     Bảng kết quả, phân tích, per-query (sinh bởi scripts/evaluate.py)
reports/data_stats/  Thống kê EDA và kiểm tra dữ liệu
reports/figures/     Hình EDA
notebooks/           Notebook trình bày EDA
docs/                Mục lục, bàn giao từng phase, quy trình
annotation/, prompts/  Guideline và prompt của pilot gán nhãn LLM (đã dừng, giữ làm lịch sử)
```

## Tài liệu theo phase

| Muốn xem | Điểm bắt đầu |
|---|---|
| Tiến độ và bằng chứng từng phase | [Mục lục đồ án](docs/README.md) |
| Số liệu, bằng chứng nằm ở đâu | [Danh mục artifact](docs/artifacts.md) |
| EDA | [Notebook EDA](notebooks/01_eda.ipynb), [bảng thống kê](reports/data_stats/README.md), [schema](reports/data_stats/schema.md) |
| Baseline BM25 S1₀ / E5 S2 | [bàn giao BM25](docs/phases/bm25.md), [bàn giao E5](docs/phases/e5.md) |
| Pilot gán nhãn LLM (đã dừng 2026-10-26) | [docs/phases/annotation.md](docs/phases/annotation.md) |
| Kết quả cuối | [reports/results/results.md](reports/results/results.md) |
| Quy trình phối hợp, mẫu bàn giao | [workflow](docs/workflow.md), [mẫu](docs/templates/phase_handoff.md) |

## Dữ liệu gốc, EDA và chuẩn bị corpus (mức 4)

Dataset `th1nhng0/vietnamese-legal-documents` và tokenizer E5 ghim revision trong [configs/data.yaml](configs/data.yaml).

```powershell
.\.venv\Scripts\python.exe scripts/download_data.py --config configs/data.yaml
.\.venv\Scripts\python.exe -X utf8 scripts/eda.py --config configs/data.yaml
.\.venv\Scripts\python.exe -X utf8 scripts/prepare_data.py --config configs/data.yaml
.\.venv\Scripts\python.exe -X utf8 scripts/validate_data.py --config configs/data.yaml
```

Đầu ra: `data/raw/`, `reports/data_stats/`, `data/processed/`, `logs/`. VNCoreNLP cho BM25:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/download_vncorenlp.py --config configs/bm25.yaml --url-template 'https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/{revision}/{file}' --timeout 60
```

Notebook EDA cần thêm `requirements-notebooks.txt`; số trong báo cáo lấy từ script, không chép tay từ notebook.

## Quy ước

- Methodology và mọi quyết định: [SPEC.md](SPEC.md) (bảng Changelog cuối file). Thay đổi kỹ thuật của repo: [CHANGELOG.md](CHANGELOG.md).
- Quy tắc file/commit cho người và agent: [CLAUDE.md](CLAUDE.md).
- Script không ghi đè output đã có; muốn chạy lại thì đổi thư mục output.
