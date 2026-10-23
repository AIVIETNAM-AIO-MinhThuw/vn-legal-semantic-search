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

Sau `validate_data`, giữ điểm chờ người trước split. Test đạt và có output không đồng nghĩa phase đã được review/duyệt. Chưa dùng số liệu WIP làm kết luận cuối.

## Các bước chưa bàn giao

Gom họ/split, query, retrieval/training, pooling/annotation, final evaluation và demo thực hiện theo SPEC và các điểm chờ. Chưa cung cấp lệnh tái lập final evaluation, lệnh tải checkpoint/index hoặc lệnh chạy app vì chưa có bằng chứng chúng hoạt động. Bổ sung hướng dẫn tại đây sau khi phase tương ứng được bàn giao và kiểm chứng.

## Phối hợp và lưu tiến độ

Sau mỗi phase: người code bàn giao bằng chứng → người phụ trách trình bày kiểm tra và hoàn thiện phần tương ứng → nhóm review → người được nhóm phân công commit. Dùng [mẫu bàn giao](docs/templates/phase_handoff.md), không gom phần đang làm dở vào cùng mốc hoàn tất.

Tên thành viên và phân công thực tế được cập nhật trong [docs/README.md](docs/README.md). Ghi nhận việc dùng công cụ hỗ trợ theo yêu cầu môn học; chưa có rubric gốc trong phần tài liệu này nên không tuyên bố đã đáp ứng toàn bộ tiêu chí chấm.
