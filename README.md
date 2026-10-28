# Tìm kiếm ngữ nghĩa văn bản pháp luật tiếng Việt

Đồ án NLP — Đề tài 8. Mục tiêu là tìm các **Điều** pháp luật liên quan đến câu hỏi tiếng Việt. Chunk phục vụ xử lý và lập chỉ mục; đơn vị kết quả là Điều.

Methodology và các quyết định đã duyệt nằm trong [SPEC.md](SPEC.md). Quy tắc làm việc và các điểm chờ nằm trong [CLAUDE.md](CLAUDE.md). Tài liệu trình bày không thay thế hai file này.

## Truy cập demo nhanh

**[Mở demo tra cứu pháp luật trên Streamlit Cloud](https://vn-legal-semantic-search-jqxydgjrta2e54c3ldqv2l.streamlit.app/)**

Người xem chỉ cần trình duyệt trên Windows, macOS hoặc điện thoại; không cần clone repo hay cài Python, Java, Docker.

1. Mở link demo, chờ ứng dụng nạp model nếu đang khởi động.
2. Nhập câu hỏi pháp luật rồi bấm **Tìm**.
3. Chọn **Semantic**, **BM25**, **Hybrid** hoặc **So sánh** để xem kết quả theo từng chế độ.

Truy vấn có nhiều kết quả dài có thể mất thêm thời gian xử lý. Kết quả không thay thế tư vấn pháp lý. Link trên là địa chỉ bản triển khai thử; việc có URL không đồng nghĩa mọi kiểm tra nghiệm thu đã đạt. Nếu cần lưu feedback, tải CSV trước khi reboot/redeploy vì bản Cloud chưa bảo đảm lưu bền SQLite.

## Chọn nội dung cần đọc

| Bạn muốn làm gì? | Đọc mục |
|---|---|
| Dùng thử ngay, không cài đặt | [Truy cập demo nhanh](#truy-cập-demo-nhanh) |
| Đưa toàn bộ UI và API/model lên Streamlit Cloud | [Hướng dẫn Streamlit Cloud](deploy/streamlit/README.md) |
| Đóng gói nguyên ứng dụng main để chạy CPU | [Đóng gói CPU](#đóng-gói-nguyên-ứng-dụng-main-cho-máy-cpu) |
| Clone repo và chọn mức chạy phù hợp | [Bốn mức chạy](#chọn-mức-chạy-phù-hợp) |
| Clone và cài môi trường Windows/macOS | [Chuẩn bị trước khi chạy trực tiếp](#chuẩn-bị-trước-khi-chạy-trực-tiếp) |
| Xem số liệu và tài liệu dự án | [Tài liệu theo phase](#tài-liệu-theo-phase) |

## Đóng gói nguyên ứng dụng main cho máy CPU

Phần này dành cho người chuẩn bị bản triển khai. Nếu chỉ muốn dùng thử, mở link demo phía trên.

### Chọn nơi triển khai

Deploy miễn phí toàn bộ UI + API/model trên Streamlit Community Cloud: [hướng dẫn và entrypoint](deploy/streamlit/README.md). Bản thử dùng nguyên source main đã ghim commit; cần nghiệm thu thực tế trên Cloud, chưa bảo đảm lưu bền feedback.

Deploy web dùng chung cho người dùng Windows/macOS: [các bước chuyển bundle, chạy server và tạo link HTTPS](docs/deploy_cpu.md). Người dùng chỉ cần trình duyệt; Docker chạy trên server Linux/amd64.

### Tạo và chạy bundle CPU

Chuẩn bị Python 3.11 và môi trường `.venv` theo [hướng dẫn cài đặt](#cài-môi-trường-demo-cpu-và-test) nếu chưa có.

Trên nhánh `task/TestCheckErrorDocker`, dùng ZIP và file checksum đã tải ở thư mục cha:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/package_deploy.py --zip ..\vnlegal-demo-v1.zip --checksum ..\vnlegal-demo-v1.sha256
cd release\deploy-cpu
docker compose up --build -d --wait --wait-timeout 900
```

Script đọc commit `main` bằng Git archive, giữ nguyên byte source/config của main, chỉ bổ sung Docker/dependency CPU và symlink đường dẫn trong image. `main` và artifact không bị sửa. `RELEASE.json` ghi commit, checksum ZIP và hash từng file; `DEPLOY.md` nằm trong bundle. Script từ chối ghi đè bundle có sẵn. Chép cả thư mục bundle, gồm `artifacts/`, sang máy deploy có Docker Linux/amd64. Windows dùng Docker Desktop Linux containers; không cần GPU hoặc Java trên host.

Hai file `.zip` và `.sha256` không ghép với nhau: checksum kiểm tra ZIP, sau đó 23 file được giải nén và kiểm tra hash vào `artifacts/`, mount chỉ đọc. SQLite dùng volume riêng.

| Sau khi bundle khởi động | Địa chỉ hoặc lệnh |
|---|---|
| Giao diện tìm kiếm | `http://127.0.0.1:8501` |
| Tài liệu API | `http://127.0.0.1:8000/docs` |
| Dừng ứng dụng và giữ volume | `docker compose down` |

Không thêm `-v` khi dừng nếu cần giữ feedback.

### Phân biệt bundle main và checkout tích hợp

Bundle này đóng gói hành vi hiện có trên main; main kiểm tra manifest theo loader cũ, không có đầy đủ kiểm tra provenance/fail-fast của D3. Vì vậy kết quả chạy bundle không phải xác nhận D3/D6 nghiêm ngặt đã đạt. Các mục tiếp theo mô tả checkout tích hợp D1–D6; khi chạy bundle, dùng lệnh trong `release/deploy-cpu/DEPLOY.md`.

## Hướng dẫn chạy (cho người clone repo)

### Chọn mức chạy phù hợp

Có 4 mức, chọn mức cần dùng. Hướng dẫn chạy trực tiếp bên dưới có lệnh riêng cho Windows CPU, Windows NVIDIA và macOS CPU. Mức 1–2 không bắt buộc GPU; đọc giới hạn artifact trước khi cài.

**Trạng thái nghiệm thu:** gói `vnlegal-demo-v1.zip` đúng checksum nhưng bị loader từ chối do manifest BM25 không khớp môi trường và dense B thiếu provenance. D6 chưa đạt; chưa bàn giao deploy. Xem [kết quả và các chặn D6](docs/phases/docker.md#12-d6--kiểm-thử-tích-hợp-trên-máy-windows-chưa-đạt).

| Mức | Mục đích | Cần | Thời gian |
|---|---|---|---|
| 1 | Xem và tính lại bảng kết quả | Python 3.11 | 2 phút |
| 2 | Chạy demo (giao diện + API) | Python 3.11, Java 64-bit, gói artifact ~1,3 GB | 15 phút |
| 3 | Chạy lại toàn bộ thực nghiệm (train, truy hồi, đánh giá) | GPU NVIDIA ≥ 6 GB, mạng tới Hugging Face | 1–1,5 giờ |
| 4 | Dựng lại từ dữ liệu gốc | Như mức 3 | vài giờ |

### Cái gì nằm ở đâu

Repo chứa code và kết quả nhỏ đã được commit. Corpus, trọng số model và index được phân phối riêng trong gói artifact.

| Thành phần | Vị trí | Cách có |
|---|---|---|
| Code, config, test | repo | `git clone` |
| Query (4.641), nhãn, split, query test/val/biến thể | `data/interim/full_v2/queries_v2.csv`, `data/interim/source_qrels_v1/`, `data/splits_v2/`, `data/eval_v1/` | có sẵn trong git |
| Kết quả truy hồi từng hệ thống (`run.trec`, `summary.json`) | `runs/<tập query>/<hệ thống>/` | có sẵn trong git |
| Bảng kết quả, phân tích | `reports/results/` | có sẵn trong git |
| Log train, chọn LR | `models/*/val_metrics.json`, `train_log.jsonl`, `models/lr_selection.json` | có sẵn trong git |
| Corpus đã xử lý, VNCoreNLP, index BM25, index + model E5 fine-tune B | `data/processed/`, `data/raw/vncorenlp/`, `indexes/`, `models/e5_ft_B_lr3e-05/model/` | **gói artifact** `vnlegal-demo-v1.zip` ([Google Drive](https://drive.google.com/drive/folders/1wTvyZm74OFUHFgUwGDfhE6u2H034BoAr?usp=sharing), 1,28 GB) |
| Model gốc E5, SBERT | `data/raw/` | tải bằng script (mức 3) |

### Chuẩn bị trước khi chạy trực tiếp

Thực hiện các lệnh từ **thư mục gốc repo**. Windows dùng **PowerShell**; macOS dùng **Terminal**. Cần Git, Python **3.11 64-bit**, Java **64-bit** và mạng để cài thư viện/tải artifact lần đầu. Không dùng Python 3.14. Không cần kích hoạt venv: các lệnh gọi thẳng Python trong venv để tránh dùng nhầm interpreter.

**Giới hạn hiện tại cần đọc trước:** source `main` sau tích hợp D3 kiểm tra manifest nghiêm ngặt. Gói v1 có SHA-256 đúng nhưng BM25 ghi Python `3.11.9`/Java `1.8.0_471`, còn dense B thiếu metadata `encoder`/`versions`. Vì vậy **hiện chưa có quy trình chạy tìm kiếm thật từ source hiện tại với gói v1 được nghiệm thu thành công**, trên cả CPU và GPU. Cài Java đúng vẫn không bổ sung được metadata dense còn thiếu. Các bước dưới hướng dẫn chuẩn bị và chẩn đoán đúng; cần nhóm phát hành artifact tương thích theo SPEC trước khi có thể xác nhận API chạy được. Không sửa manifest, bỏ kiểm tra hoặc dựng lại artifact đã freeze để vượt lỗi.

Link Cloud dùng source snapshot riêng tại commit `4a83ee6` qua `deploy/streamlit/bootstrap.py`; Cloud chạy được không chứng minh source hiện tại chạy được với cùng gói. Chi tiết lỗi đã ghi trong [biên bản D6](docs/phases/docker.md#125-sửa-lỗi-và-kiểm-chứng-lại-ngày-2026-10-2728).

#### Bước 1 — clone repo

Windows PowerShell và macOS Terminal đều chạy:

```sh
git clone https://github.com/AIVIETNAM-AIO-MinhThuw/vn-legal-semantic-search.git
cd vn-legal-semantic-search
```

Nếu đã clone thì mở terminal ngay tại thư mục repo, không clone lồng thêm một bản. Nếu có thay đổi local, lưu chúng trước khi tự cập nhật Git.

#### Bước 2A — Windows không có GPU NVIDIA: môi trường CPU

Cài Python 3.11 64-bit từ [python.org](https://www.python.org/downloads/), gồm Python Launcher. Mở lại PowerShell sau khi cài rồi chạy:

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt -r requirements-ui.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import torch; print('Torch:', torch.__version__, 'CUDA:', torch.cuda.is_available())"
```

Torch phải là `2.5.1+cpu`; CUDA là `False`. Nếu không có lệnh `py`, dùng đường dẫn đầy đủ tới `python.exe` của Python 3.11 ở hai lệnh đầu. Không dùng alias `python` của Microsoft Store nếu nó chỉ mở Store. Không cài `requirements-train.txt` vào venv này.

#### Bước 2B — Windows có GPU NVIDIA

**Chỉ muốn mở demo:** làm theo bước 2A; `configs/app.yaml` mặc định `device: cpu`, nên máy có GPU vẫn chạy bằng CPU.

**Muốn thử inference bằng NVIDIA:** cần driver NVIDIA tương thích CUDA 12.1. Kiểm tra `nvidia-smi` trước; GPU AMD/Intel không dùng nhánh CUDA này. Dùng venv riêng và tạo bản dependency local thay đúng pin Torch CPU bằng CUDA, giữ các phiên bản còn lại:

```powershell
nvidia-smi
py -3.11 -m venv .venv-gpu
New-Item -ItemType Directory -Force .scratch | Out-Null
.\.venv-gpu\Scripts\python.exe -c "from pathlib import Path; s=Path('requirements-api.txt').read_text(); Path('.scratch/requirements-api-gpu.txt').write_text(s.replace('https://download.pytorch.org/whl/cpu', 'https://download.pytorch.org/whl/cu121').replace('torch==2.5.1+cpu', 'torch==2.5.1+cu121'))"
.\.venv-gpu\Scripts\python.exe -m pip install -r .scratch/requirements-api-gpu.txt -r requirements-ui.txt -r requirements.txt
.\.venv-gpu\Scripts\python.exe -m pip check
.\.venv-gpu\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available()); assert torch.cuda.is_available(), 'CUDA chua san sang'"
.\.venv-gpu\Scripts\python.exe -c "from pathlib import Path; import yaml; c=yaml.safe_load(Path('configs/app.yaml').read_text(encoding='utf-8')); c['device']='cuda'; Path('.scratch/app-gpu.yaml').write_text(yaml.safe_dump(c, allow_unicode=True), encoding='utf-8')"
$env:PYTHON = (Resolve-Path '.\.venv-gpu\Scripts\python.exe').Path
$env:APP_CONFIG = '.scratch/app-gpu.yaml'
```

Ở bước tải artifact, thay `.\.venv\Scripts\python.exe` bằng `.\.venv-gpu\Scripts\python.exe`. Giữ hai biến trên trong cùng cửa sổ PowerShell khi chạy demo. GPU không giải quyết lỗi manifest. Đây là hướng dẫn cấu hình CUDA, chưa có nghiệm thu inference GPU với gói v1 trên source hiện tại. Muốn quay lại CPU: `Remove-Item Env:PYTHON, Env:APP_CONFIG -ErrorAction SilentlyContinue`.

#### Bước 2C — macOS: môi trường CPU

Kiểm tra kiến trúc bằng `uname -m`: `arm64` là Apple Silicon, `x86_64` là Intel. Cài Python 3.11 và JDK cùng kiến trúc với Python; tránh trộn interpreter chạy qua Rosetta với Java arm64. Repo chưa nghiệm thu native macOS; nếu pip không có wheel tương ứng với máy thì dừng và ghi lại lỗi, không tự đổi phiên bản để ép cài.

`requirements-api.txt` ghim `torch==2.5.1+cpu` cho Windows/Linux, không dùng nguyên pin đó trên macOS. Tạo bản dependency local dùng wheel macOS theo [hướng dẫn PyTorch 2.5.1](https://pytorch.org/get-started/previous-versions/#v251):

```sh
python3.11 --version
uname -m
python3.11 -m venv .venv
mkdir -p .scratch
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -c "from pathlib import Path; s=Path('requirements-api.txt').read_text(); s=s.replace('--extra-index-url https://download.pytorch.org/whl/cpu', '').replace('torch==2.5.1+cpu', 'torch==2.5.1'); Path('.scratch/requirements-api-macos.txt').write_text(s)"
.venv/bin/python -m pip install -r .scratch/requirements-api-macos.txt -r requirements-ui.txt -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -c "import platform, torch; print(platform.machine(), torch.__version__)"
```

Nếu pip báo cần compiler để build PyJNIus, cài Command Line Tools bằng `xcode-select --install` rồi chạy lại bước cài dependency. macOS dùng CPU trong hướng dẫn này; CUDA và acceleration MPS chưa được nghiệm thu. Đặc biệt Mac Intel có thể không có wheel cho các phiên bản đã ghim; hiện chưa có bộ dependency native Intel được xác nhận cho repo này.

#### Bước 3 — tải và kiểm tra artifact

Tải **hai file** `vnlegal-demo-v1.zip` và `vnlegal-demo-v1.sha256` từ [Google Drive](https://drive.google.com/drive/folders/1wTvyZm74OFUHFgUwGDfhE6u2H034BoAr?usp=sharing). Đặt chúng ở thư mục cha của repo, hoặc sửa đường dẫn ZIP trong lệnh bên dưới. File `.sha256` là checksum để đối chiếu, không ghép vào ZIP và không giải nén thủ công.

Windows CPU:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/fetch_artifacts.py --zip "../vnlegal-demo-v1.zip" --sha256 059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096 --output-dir ./artifacts
```

macOS:

```sh
.venv/bin/python -X utf8 scripts/fetch_artifacts.py --zip ../vnlegal-demo-v1.zip --sha256 059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096 --output-dir ./artifacts
```

Script kiểm SHA-256 ZIP và từng file, kiểm đủ đầu vào rồi chuẩn bị `artifacts/MANIFEST.json`, corpus, VNCoreNLP, BM25 index và dense index/model. `models/lr_selection.json` lấy từ Git. Không dùng `--force` khi checksum sai; tải lại gói hoặc báo nhóm. Checksum hợp lệ chỉ xác nhận byte của gói, chưa xác nhận manifest tương thích runtime.

#### Bước 4 — cấu hình Java trong terminal chạy demo

Cài JDK/JRE 64-bit và đặt `JAVA_HOME` tới **thư mục chứa `bin`**, không tới `bin` hay file executable. Thay đường dẫn ví dụ bằng vị trí cài thực tế. Chạy `java -version` là bước kiểm tra cài đặt; gói v1 còn yêu cầu provenance Java/Python khớp chính xác như đã nêu ở đầu hướng dẫn.

Windows PowerShell:

```powershell
$env:JAVA_HOME = 'C:\duong-dan-thuc-te\jdk'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "$env:JAVA_HOME\bin\java.exe" -version
```

macOS Terminal (liệt kê Java đã cài rồi chọn bản tương ứng):

```sh
/usr/libexec/java_home -V
export JAVA_HOME="$(/usr/libexec/java_home -v 1.8)"
export PATH="$JAVA_HOME/bin:$PATH"
"$JAVA_HOME/bin/java" -version
```

Nếu chưa cài Java 8, lệnh chọn `-v 1.8` sẽ thất bại; cài runtime phù hợp trước. Không có tùy chọn README nào tự bổ sung provenance bị thiếu của dense B.

### Mức 1 — tính lại bảng kết quả từ run có sẵn

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/evaluate.py --config configs/eval.yaml
```

Ghi ra `reports/results/results.md`. Số liệu phải trùng bản đã commit (metric và bootstrap tất định, seed 42; cột latency lấy từ `summary.json` của lần chạy gốc; cột "Index (MB)" đo thư mục `indexes/`, sẽ bằng 0 nếu chưa giải nén gói artifact).

Trên macOS thay `.\.venv\Scripts\python.exe` bằng `.venv/bin/python`; Windows dùng venv GPU thì thay bằng `.\.venv-gpu\Scripts\python.exe`. Đây là tính lại bảng từ run có sẵn, không chạy truy hồi hay tune lại trên test/OOD.

### Mức 2 — chạy demo

#### Bước 5 — khởi động API và UI trực tiếp

Chỉ tiếp tục khi đã cài dependency, tải artifact thành công và đặt Java trong **cùng terminal**. Với gói v1 hiện tại, có thể gặp lỗi manifest đã nêu; khi đó dùng mục xử lý lỗi dưới đây, không coi giao diện mở được là tìm kiếm đã hoạt động.

Windows CPU hoặc NVIDIA đã đặt `PYTHON`/`APP_CONFIG` ở bước 2B:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
```

macOS:

```sh
bash scripts/run_demo.sh
```

Script nạp API một worker tại `http://127.0.0.1:8000`, đợi `/health` thành công tối đa 900 giây rồi mới chạy UI tại **http://127.0.0.1:8501**. Giữ terminal mở; `Ctrl+C` dừng UI và API. Lần sau chỉ cần vào repo, đặt lại Java (và biến GPU nếu dùng), rồi chạy lại script; không cần cài lại venv/tải lại artifact.

Mở terminal thứ hai để kiểm tra API:

```powershell
# Windows
Invoke-RestMethod http://127.0.0.1:8000/health
```

```sh
# macOS
curl --fail http://127.0.0.1:8000/health
```

Health phải trả `{"status":"ok"}`. Tài liệu API ở `http://127.0.0.1:8000/docs`. SQLite feedback nằm tại `data/app/feedback.sqlite`, ngoài `artifacts/`. Chỉ chạy một bản demo trên cổng 8000/8501.

#### Nếu không chạy được

| Dấu hiệu | Kiểm tra và cách xử lý |
|---|---|
| `py`/`python3.11` không tồn tại | Cài Python 3.11 đúng nền tảng; Windows mở lại PowerShell, kiểm tra Python Launcher; có thể dùng đường dẫn đầy đủ tới interpreter. |
| `No matching distribution ... torch==2.5.1+cpu` trên Mac | Dùng bước 2C; wheel CPU có hậu tố `+cpu` trong file API không dành cho macOS. Nếu vẫn thiếu wheel theo kiến trúc, nền tảng đó chưa được hỗ trợ bởi bộ pin này. |
| `ModuleNotFoundError` | Cài đủ ba nhóm dependency bằng đúng Python trong venv đã chọn; dùng `-m pip check`. |
| Thiếu `JAVA_HOME`, JVM hoặc Java không chạy | Kiểm tra bước 4; Java và Python phải cùng kiến trúc 64-bit. |
| Thiếu `artifacts/MANIFEST.json` hoặc file runtime | Chạy fetch từ gốc repo với `--output-dir ./artifacts`; kiểm tra ZIP tải đủ. |
| `BM25 manifest mismatch: provenance...` | Runtime không khớp provenance của index. Ghi lại lỗi và phiên bản Python/Java; cần nhóm giải quyết artifact theo SPEC. Cài Java bất kỳ hoặc đổi CPU/GPU không bảo đảm khắc phục. |
| `Dense manifest missing required metadata: encoder, versions` | Gói v1 thiếu metadata; đây là chặn artifact/code đã ghi nhận, không phải lỗi thao tác người clone. Dừng và báo nhóm; không sửa manifest để bỏ qua. |
| `Address already in use`, cổng 8000/8501 bận | Dừng phiên demo/Compose cũ rồi chạy lại; không mở đồng thời hai runner. |
| UI báo dịch vụ chưa sẵn sàng | Xem lỗi API trong terminal; chỉ chạy `src/ui/app.py` riêng không tự khởi động backend. |
| Nạp chậm/timeout | Kiểm tra log, RAM và ổ đĩa; script cho phép chờ 900 giây. Lỗi manifest phải xử lý theo dòng tương ứng, không giải quyết bằng tăng thời gian chờ. |

#### Docker Compose và kiểm tra smoke (tùy chọn)

Đây là đường chạy đóng gói, dùng cùng cấu hình CPU/artifact và cũng chịu chặn manifest của source hiện tại. Windows cần mở Docker Desktop ở chế độ Linux containers trước; macOS cần Docker Desktop và image đúng kiến trúc (bundle Linux/amd64 chưa nghiệm thu trên Apple Silicon). Docker đã cài Java bên trong image; host không cần Java cho đường chạy này.

```sh
docker version
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 900
docker compose logs --tail 80 api
docker compose down
```

Dừng stack trước khi chạy smoke để giải phóng cổng:

```powershell
# Windows CPU; nhánh GPU thay bằng Python .venv-gpu
.\.venv\Scripts\python.exe -X utf8 scripts/smoke_demo.py
```

```sh
# macOS, khi đã có môi trường tương thích
.venv/bin/python -X utf8 scripts/smoke_demo.py
```

Smoke kiểm tra bốn mode và health UI, tự dừng project riêng và giữ volume feedback. Không thêm `-v` vào `docker compose down` nếu cần giữ feedback. Hai cờ Hugging Face offline trong runner ngăn tải model lúc inference; kiểm tra chặn mạng outbound riêng được ghi trong tài liệu D6.

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
| Deploy toàn bộ ứng dụng trên Streamlit Cloud | [Hướng dẫn Streamlit Cloud](deploy/streamlit/README.md) |
| Đóng gói CPU, chạy server và Quick Tunnel | [Hướng dẫn deploy CPU](docs/deploy_cpu.md) |
| Kết quả kiểm thử và giới hạn Docker/D6 | [Biên bản phase Docker](docs/phases/docker.md) |

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
