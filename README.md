# Tìm kiếm ngữ nghĩa văn bản pháp luật tiếng Việt

Đồ án NLP — Đề tài 8. Mục tiêu là tìm các **Điều** pháp luật liên quan đến câu hỏi tiếng Việt. Chunk phục vụ xử lý và lập chỉ mục; đơn vị kết quả là Điều.

Methodology và các quyết định đã duyệt nằm trong [SPEC.md](SPEC.md). Quy tắc làm việc và các điểm chờ nằm trong [CLAUDE.md](CLAUDE.md). Tài liệu trình bày không thay thế hai file này.

## Xem dự án theo từng phase

| Muốn xem | Điểm bắt đầu |
|---|---|
| Tiến độ, cấu trúc trình bày và phân công | [Mục lục đồ án](docs/README.md) |
| Cách bàn giao sau mỗi phase nhỏ | [Quy trình phối hợp](docs/workflow.md) và [mẫu bàn giao](docs/templates/phase_handoff.md) |
| Số liệu, bằng chứng nằm ở đâu | [Danh mục artifact](docs/artifacts.md) |
| Cách tổ chức notebook | [Hướng dẫn notebook](notebooks/README.md) |
| Quy tắc xuất hình dùng trong báo cáo/slide | [Hướng dẫn hình minh họa](reports/figures/README.md) |
| Trình bày EDA | [Notebook EDA](notebooks/01_eda.ipynb); [danh mục bảng](reports/data_stats/README.md) và [schema](reports/data_stats/schema.md) ở phía sau |

Hiện có EDA, notebook trình bày và quyết định OI-10 đã chốt. Pipeline chuẩn bị dữ liệu đã có code và output nhưng còn trong quá trình review. Các giai đoạn sau chưa được xác nhận hoàn tất. Xem trạng thái chi tiết tại [docs/README.md](docs/README.md).

## Cấu trúc repo

```text
configs/           Tham số, đường dẫn, seed và revision
scripts/           Chương trình chạy từng bước
src/               Module dùng chung của pipeline
tests/             Kiểm thử
data/raw/          Dữ liệu nguồn và tokenizer; không commit
data/processed/    Dữ liệu xử lý; không commit
data/FROZEN.md     Hash và thời điểm freeze theo SPEC
reports/data_stats/  Thống kê EDA và báo cáo kiểm tra dữ liệu
reports/figures/   Hình xuất phục vụ báo cáo/slide
notebooks/         Phân tích và minh họa từ artifact đã bàn giao
docs/              Mục lục, tiến độ, quy trình và mẫu bàn giao
logs/              Nhật ký chạy, loại dữ liệu và bất thường
prompts/           Prompt có version cho các bước được phép dùng LLM
annotation/        Tài liệu/công cụ gán nhãn theo SPEC
runs/              Kết quả chạy thực nghiệm theo SPEC
.evidence-loop/    Hồ sơ bằng chứng và cải tiến quy trình, không phải methodology
```

## Cài đặt

Yêu cầu Python 3.11. Trên Windows, chạy từ thư mục gốc repo:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Trên Linux/macOS, dùng `.venv/bin/python` thay cho `.\.venv\Scripts\python.exe`.

Để mở và chạy notebook trình bày (không cần cho pipeline chính):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-notebooks.txt
.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name vn-legal-semantic-search --display-name "Python (vn-legal-semantic-search)"
.\.venv\Scripts\python.exe -m jupyterlab notebooks/01_eda.ipynb
```

## Tải dữ liệu và tokenizer

Dataset `th1nhng0/vietnamese-legal-documents` và tokenizer E5 đều ghim revision trong [configs/data.yaml](configs/data.yaml).

```powershell
.\.venv\Scripts\python.exe scripts/download_data.py --config configs/data.yaml
```

Dữ liệu ở `data/raw/`; không commit parquet, tokenizer hoặc model lớn. Nếu dùng API ở phase sau, không ghi API key vào repo.

## Chạy EDA

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/eda.py --config configs/data.yaml
```

Đầu ra ở [reports/data_stats/](reports/data_stats/): schema, CSV thống kê, báo cáo tổng hợp và mẫu trong `samples/`. Đây là thống kê đầu vào; số Điều từ regex là **ước lượng**. Lệnh chạy lại ghi vào các đường dẫn hiện có; lưu bản kết quả trước nếu muốn so sánh hai lần chạy.

Notebook [01_eda.ipynb](notebooks/01_eda.ipynb) là điểm vào để trình bày các artifact này. Theo SPEC mục 13, số trong báo cáo phải tái lập được bằng script; không chép số thủ công từ notebook.

Sau khi EDA sinh các CSV, chạy notebook từ đầu và xuất lại biểu đồ bằng:

```powershell
.\.venv\Scripts\python.exe -m nbconvert --to notebook --execute notebooks/01_eda.ipynb --inplace --ExecutePreprocessor.timeout=180 --ExecutePreprocessor.kernel_name=vn-legal-semantic-search
```

## Chuẩn bị dữ liệu và kiểm tra — đang review

Các lệnh đã được triển khai, chỉ chạy khi nằm trong phạm vi phase được giao:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/prepare_data.py --config configs/data.yaml
.\.venv\Scripts\python.exe -X utf8 scripts/validate_data.py --config configs/data.yaml
.\.venv\Scripts\python.exe -m pytest -q
```

Đầu ra: `data/processed/`, `logs/` và `reports/data_stats/after_filter/`. Log từng văn bản bị loại là `logs/filtered_out.tsv`. Các file có tên `*_index.jsonl` là dữ liệu sau dedup, chưa chứng minh đã xây index truy hồi hoặc được phép split.

Test đạt và có output không đồng nghĩa phase đã được review/duyệt. Chưa dùng số liệu WIP làm kết luận cuối.

## Các bước chưa bàn giao

Từ ngày 2026-10-25, thứ tự theo SPEC là: sinh query bằng LLM → truy hồi ứng viên (BM25 tạo dataset và E5 zero-shot) → gán nhãn bằng LLM, kiểm chứng bằng người trên mẫu pilot → tạo dataset có nhãn → split → training → pooling bổ sung và final evaluation → demo. `data/splits.json` là artifact lịch sử của quy trình cũ, không phải split đang áp dụng. Các bước thực hiện theo SPEC và các điểm chờ. Chưa cung cấp lệnh tái lập final evaluation, lệnh tải checkpoint/index hoặc lệnh chạy app vì chưa có bằng chứng chúng hoạt động. Bổ sung hướng dẫn tại đây sau khi phase tương ứng được bàn giao và kiểm chứng.

## Phối hợp và lưu tiến độ

Sau mỗi phase: người code bàn giao bằng chứng → người phụ trách trình bày kiểm tra và hoàn thiện phần tương ứng → nhóm review → người được nhóm phân công commit. Dùng [mẫu bàn giao](docs/templates/phase_handoff.md), không gom phần đang làm dở vào cùng mốc hoàn tất.

Tên thành viên và phân công thực tế được cập nhật trong [docs/README.md](docs/README.md). Ghi nhận việc dùng công cụ hỗ trợ theo yêu cầu môn học; chưa có rubric gốc trong phần tài liệu này nên không tuyên bố đã đáp ứng toàn bộ tiêu chí chấm.

### Baseline BM25 S1₀

Theo [SPEC mục 7](SPEC.md#7-systems), BM25 S1₀ dùng `bm25s` + VNCoreNLP word segmentation + unigram, `k1 = 1.2`, `b = 0.75`. Không bigram, không bỏ stopword. BM25 S1 giữ cùng pipeline và chỉ tune `k1`, `b` trên val sau split. E5 nhận văn bản tự nhiên với tokenizer riêng; không dùng đầu ra VNCoreNLP. BM25 đã được triển khai và chạy local; kết quả và giới hạn ở [bàn giao BM25](docs/phases/bm25.md). E5 chưa triển khai trong phase này.


Chạy từ thư mục gốc repo, đặt `JAVA_HOME` trỏ tới Java 64-bit và dùng môi trường `.venv`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements.txt -r requirements-bm25.txt
```

Nếu chưa có model tách từ, tải đúng revision trong config (lệnh tải đã có unit test; không tải model POS/NER/parser):

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/download_vncorenlp.py --config configs/bm25.yaml --url-template 'https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/{revision}/{file}' --timeout 60
```

Đặt `$queryCsv` thành đường dẫn CSV của bạn; file phải có `query_id`, `query`. Không cần chép CSV vào source. Mọi tham số/đường dẫn mặc định nằm trong [config BM25](configs/bm25.yaml); các đường dẫn tương đối được tính từ thư mục gốc repo.

```powershell
# Lần đầu: xây index mới và chạy query. Lệnh này đã chạy thành công trên corpus local.
.\.venv\Scripts\python.exe -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries $queryCsv --build
# Các lần sau: nạp index, xuất sang thư mục mới; không tách từ lại corpus.
.\.venv\Scripts\python.exe -X utf8 scripts/run_bm25.py --config configs/bm25.yaml --queries $queryCsv --output data/interim/bm25_replay
```

Index ở `indexes/bm25_s10/`; đầu ra mặc định ở `data/interim/bm25_s10/`: `run.trec`, `candidates.jsonl`, `warnings.jsonl`, `summary.json`. Index và output local không commit. `candidates.jsonl` chứa query và nội dung Điều đầy đủ, xáo trộn theo seed; không chứa rank/score hoặc nguồn sinh query. Đây là ứng viên BM25, cần hợp nhất với E5 trước gán nhãn. `summary.json` ghi cấu hình hiệu lực, hashes và thời gian. Không ghi đè thư mục có sẵn; đổi đường dẫn khi cần một lần chạy mới.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_bm25.py -q
```


### E5 zero-shot S2

E5 dùng văn bản tự nhiên và tokenizer của checkpoint, không qua VNCoreNLP. Cấu hình tại [configs/e5.yaml](configs/e5.yaml): model/revision, paths, batch size, max length, device, seed, top-k và phiên bản thư viện. Config đi kèm dùng CUDA fp32; không có GPU thì chọn `runtime.device: cpu` một cách tường minh trước khi build. Đổi runtime/encoding phải tạo index mới vì manifest kiểm tra cấu hình nghiêm ngặt.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements.txt -r requirements-e5.txt
# Tải đúng revision một lần. Bước này cần mạng, không ghi đè thư mục model đã có.
.\.venv\Scripts\python.exe -X utf8 scripts/download_e5.py --config configs/e5.yaml
# Đặt $queryCsv tới CSV đã kiểm tra, có query_id và query.
.\.venv\Scripts\python.exe -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries $queryCsv --build
# Nạp lại index và xuất sang thư mục mới; không encode lại corpus.
.\.venv\Scripts\python.exe -X utf8 scripts/run_e5.py --config configs/e5.yaml --queries $queryCsv --output data/interim/e5_replay
```

Lệnh truy hồi chỉ nạp file model local, không gọi API hoặc tự tải model. Prefix được gắn qua `src/retrieval/e5_format.py`; mean pooling theo attention mask, L2, fp32; không truncate âm thầm passage/query vượt max length. Index lưu `vectors.npy`, mapping chunk và manifest kiểm tra checksum, model/revision, preprocessing version và dependency versions. Search exact dot product trên chunk, chung hàm top-200/MaxP/tie-break với BM25.

Kết quả mặc định ở `data/interim/e5_s2/`, index ở `indexes/e5_s2/`. Các file xuất giống BM25: TREC có rank/score; candidate blind chỉ có query và nội dung Điều, xáo trộn theo seed. Không cộng trực tiếp điểm BM25/E5. Cần hợp nhất hai tập ứng viên theo query/Điều rồi xáo trộn union trước khi gán nhãn; bước hợp nhất chưa nằm trong phase này.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_e5.py tests/test_bm25.py -q
```

Bằng chứng chạy, hashes, kiểm thử và giới hạn ở [bàn giao E5](docs/phases/e5.md). Chưa có nhãn nên chưa báo cáo Precision/Recall/MRR/MAP/NDCG hoặc khẳng định chất lượng tìm kiếm.
