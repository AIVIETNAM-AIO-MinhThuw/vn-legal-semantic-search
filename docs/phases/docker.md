# Đóng gói Docker — quy ước tích hợp và bàn giao

## 1. Phạm vi và trạng thái

- Ngày lập: 2026-10-27; nhánh làm việc: `task/Docker-Compose`.
- D0 chỉ xác lập quy ước kỹ thuật cho hai người đóng gói. Tài liệu này là đầu vào chung cho D1–D7 và người tiếp nhận deploy; không phải ghi chú phiên hay báo cáo chạy Docker thành công.
- Căn cứ: [SPEC mục 7.4, 13 và 14](../../SPEC.md), [quy tắc file/commit](../../CLAUDE.md), [quy trình bàn giao](../workflow.md).
- Người 1 phụ trách API, dependency, artifact và runtime; người 2 phụ trách UI, Compose, lệnh chạy, kiểm thử tích hợp và tổng hợp bàn giao. Chưa gán tên cá nhân.
- D0: đã được hai người thống nhất theo xác nhận của người giao việc trong chat ngày 2026-10-27; chưa cung cấp tên cá nhân/liên kết review.
- D1: đã build và kiểm chứng image API CPU trên Linux/amd64; kết quả và giới hạn ghi tại mục 9. D2–D7 chưa triển khai trong thay đổi này.
- Phạm vi bàn giao cuối: hai image và bộ chạy local đã kiểm chứng. Registry, server, domain, HTTPS, reverse proxy và vận hành thuộc người deploy.

## 2. Service, kết nối và cổng

Thư mục làm việc của cả hai image là `/app`. Đường chạy chính là Docker Compose; Python local là phương án dự phòng. Luồng ứng dụng giữ nguyên UI → API → SearchService → retrieval.

| Thành phần | Quy ước Docker | Quy ước Python local |
|---|---|---|
| Service API | Tên `api`; `python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 1` | Cùng entry point, bind `127.0.0.1:8000`, một worker |
| Service UI | Tên `ui`; `python -m streamlit run src/ui/app.py --server.address 0.0.0.0 --server.port 8501` | Cùng entry point, bind `127.0.0.1:8501` |
| API mà UI gọi | `http://api:8000` qua mạng nội bộ Compose | `http://127.0.0.1:8000` |
| Cổng publish trên host | API `127.0.0.1:8000:8000`; UI `127.0.0.1:8501:8501` | Như địa chỉ bind trên |
| Readiness | API `GET /health` trả 200 sau khi nạp model/index và kiểm tra manifest; UI chờ `service_healthy` | Script chạy local chờ cùng endpoint trước khi mở UI |
| Runtime | CPU, user không phải root; UI không chứa Torch | CPU, cùng dependency suy luận và config với image API |

Hai tiến trình dùng cổng cố định ở mốc đóng gói. Nếu máy host đã chiếm cổng thì báo rõ và giải phóng/đổi ánh xạ host khi chạy; không đổi cổng nội bộ hoặc tự bỏ kiểm tra readiness. Không dùng `localhost` để UI trong container gọi API.

Healthcheck gọi `http://127.0.0.1:8000/health` từ bên trong container API. D4/D6 đo thời gian nạp thực tế để đặt `start_period`, timeout và số lần thử; D0 chưa có số đo để chốt các giá trị này. Sai manifest phải làm tiến trình chạy thật thoát với mã khác 0 theo SPEC; không chạy với index sai hoặc chỉ dựa vào thông báo tiến trình còn sống.

## 3. Artifact và filesystem

### 3.1 Cấu trúc trên máy host

Mọi đường dẫn dưới đây tính từ gốc checkout. D2 sẽ giải nén vào `artifacts/`, giữ nguyên tên đường dẫn tương đối trong ZIP và giữ nguyên byte của artifact.

```text
artifacts/                              # local, không commit/không vào image
  MANIFEST.json                         # manifest cấp gói từ ZIP
  data/
    processed/
      articles_index.jsonl
      chunks_index.jsonl
      docs_index.jsonl
    raw/vncorenlp/
      VnCoreNLP-1.2.jar
      models/wordsegmenter/...
  indexes/
    bm25_s10/                           # gồm manifest.json và các file index
    e5_ft_B/                            # gồm manifest.json, chunk_ids.json, vectors.npy
  models/e5_ft_B_lr3e-05/model/           # model/tokenizer hiện được gói demo sử dụng
data/app/feedback.sqlite                # chỉ cho demo-local
models/lr_selection.json                # metadata nhỏ đã có trong Git, không phải trọng số
```

Nguồn hiện được README ghi là gói `vnlegal-demo-v1.zip`; lệnh đóng gói hiện tại là `python -X utf8 scripts/package_artifacts.py`. D2 tiếp tục dùng gói này nếu đủ đầu vào, kiểm tra hash ZIP theo README và hash từng file trong `MANIFEST.json`. Không tự đóng gói lại chỉ để đổi thư mục đích. File cấp gói và file manifest của từng index có vai trò khác nhau, đều cần được giữ lại.

`models/lr_selection.json` lấy từ cùng checkout với code/config, có thể copy vào image API ở đúng đường dẫn này; không cần đưa toàn bộ thư mục `models/` vào image. Service dùng metadata đó để thay `{lr}` trong đường dẫn model, không chọn lại LR khi chạy. Nếu metadata không khớp model có trong gói, dừng và báo lỗi; không tự đổi model hay bổ sung model khác bằng mạng.

### 3.2 Mount và quyền truy cập

| Nguồn | Đích trong container | Quyền / người dùng |
|---|---|---|
| Host `./artifacts` | API `/app/artifacts` | Bind mount chỉ đọc; user API phải đọc được file và đi qua được thư mục |
| Named volume `feedback_data` | API `/app/data/app` | Ghi được; chứa `feedback.sqlite` và các file phụ SQLite nếu có |
| Code/config từ image | `/app/src`, `/app/configs` và metadata cần thiết | Được copy lúc build, không mount cả checkout vào runtime |
| Artifact/SQLite | UI: không mount | UI chỉ gọi HTTP, không đọc corpus hay ghi database |

D4 phải cấu hình bind mount không tự tạo thư mục artifact rỗng khi thiếu nguồn. D1/D4 bảo đảm volume feedback ghi được bởi user không phải root; D6 kiểm tra cả trường hợp volume mới và tái sử dụng. Dừng hoặc tạo lại container không xóa volume feedback. Không dùng `down -v` trong smoke test.

D2 bổ sung `artifacts/` vào `.gitignore`; D4 loại nó khỏi build context bằng `.dockerignore`. Cả hai image còn phải loại qrels, query test/OOD, `runs/`, SQLite, ZIP, cache, secret và file local. Không copy nguyên repo vào image rồi dựa vào việc xóa sau đó.

## 4. Config chung và quy tắc giải quyết đường dẫn

Đây là hợp đồng triển khai ở D2 (kết quả kiểm chứng ghi tại mục 10):

1. Giữ entry config là `configs/app.yaml` cho Docker và demo-local. D2 bổ sung khóa `artifact_root: artifacts`, giải quyết tương đối với gốc code (`/app` trong container, gốc checkout ở local).
2. Trong SearchService, đường dẫn corpus, index, model và `segmenter.model_dir` được giải quyết từ `artifact_root` rồi nối đường dẫn tương đối hiện có. Ví dụ `data/processed/chunks_index.jsonl` → `/app/artifacts/data/processed/chunks_index.jsonl` trong Docker.
3. Đường dẫn config như `configs/bm25.yaml`, `configs/dense_e5_ft.yaml` vẫn tính từ gốc code. `models/lr_selection.json` cũng tính từ gốc code như mục 3.1; không bị thêm tiền tố `artifacts`.
4. `feedback_db: data/app/feedback.sqlite` vẫn tính từ gốc code, nằm ngoài artifact. Nhờ đó Docker ghi vào named volume, local ghi vào thư mục đã được Git bỏ qua.
5. D2 đặt `device: cpu` cho config chạy đóng gói và demo-local. Giữ `semantic_system: e5_ft_B`, model được chọn, prefix, MaxP, giới hạn query, top-k và tham số BM25/RRF hiện có. Không tạo một bộ giá trị truy hồi riêng trong Compose.
6. Không đổi đường dẫn mặc định của training/evaluation sang `artifacts/` chỉ để phục vụ app. Việc thêm gốc artifact thuộc lớp giải quyết đường dẫn ứng dụng; retriever dùng chung tiếp tục nhận đường dẫn đã giải quyết. Không có hai bộ logic truy hồi.
7. Khi không có `artifact_root`, D2 giữ tương thích với bố trí cũ ở gốc repo. Khi đã có khóa, thiếu file phải báo lỗi; không tìm vòng sang dữ liệu cũ và vô tình che lỗi thiếu artifact.

`configs/bm25.yaml` hiện ghi `java_executable: java.exe`. D1/D2 phải kiểm tra việc dùng Java trên Linux, bảo đảm `JAVA_HOME` đúng và executable phù hợp theo nền tảng; không sửa manifest/frozen artifact để vượt kiểm tra môi trường. Khác biệt môi trường không được bỏ qua trái SPEC mục 7.4.

## 5. Biến môi trường

| Biến | Docker | Demo-local | Nơi dùng / trách nhiệm |
|---|---|---|---|
| `APP_CONFIG` | `configs/app.yaml` | `configs/app.yaml` | API; bắt buộc trong lệnh chạy thật, thiếu biến hiện tạo API không có service |
| `API_BASE_URL` | `http://api:8000` | `http://127.0.0.1:8000` | UI; D4/D5 đặt rõ |
| `UI_SAMPLE` | `0` | `0` | UI dùng API thật, không dùng fixture |
| `UI_TIMEOUT_S` | `30` | `30` | Timeout HTTP hiện có của UI; D6 ghi nhận nếu cần thay sau đo |
| `HF_HUB_OFFLINE` | `1` | `1` | API không tải từ Hugging Face khi chạy |
| `TRANSFORMERS_OFFLINE` | `1` | `1` | API chỉ dùng model/tokenizer đã chuẩn bị |
| `PYTHONUTF8` | `1` | `1` | API và UI |
| `JAVA_HOME` | Đường dẫn Java thực tế trong image | Đường dẫn Java 64-bit đã cài trên host | API; D1 xác định giá trị trong image, D5 kiểm tra local |

Không cần token hay API key cho inference từ gói đã chuẩn bị. Tải artifact là bước riêng trước khi chạy app; offline vẫn cho phép HTTP nội bộ UI → API. Không đặt cờ tắt mạng bằng cách chặn luôn kết nối giữa hai service.

## 6. Nền tảng và điểm chưa kiểm chứng

- Mục tiêu đóng gói ban đầu: Linux containers `linux/amd64`, Python 3.11, CPU, Java 64-bit. Đây là phạm vi triển khai dự kiến, chưa phải nền tảng đã test.
- Windows có thể chạy Linux containers qua Docker Desktop; task này chưa xác nhận máy nào đã bật Docker/WSL2.
- Chưa có thông tin kiến trúc server deploy. ARM64, GPU và multi-architecture không thuộc nghiệm thu ban đầu; nếu máy đích khác `linux/amd64`, người deploy cần báo để đánh giá lại dependency và kiểm chứng.
- D6 phải ghi OS/kiến trúc, Docker/Compose, CPU/RAM, Java/Python, phiên bản dependency, thời gian nạp, RAM và dung lượng image/artifact thực đo. Chưa đặt yêu cầu RAM tối thiểu bằng số ước đoán.
- OI-11 về máy demo vẫn cần nhóm xác nhận theo SPEC mục 17; không ngăn soạn quy ước hoặc làm code độc lập với máy đích. Đường chạy chính của bộ đóng gói giữ theo SPEC 13.3: Compose, dự phòng local.

## 7. Trách nhiệm và phụ thuộc D1–D7

| Task | Người / file chính | Đầu ra và phụ thuộc |
|---|---|---|
| D1 — Image API | Người 1; `Dockerfile.api`, `requirements-api.txt`, `requirements-train.txt` | CPU, Java, một worker, non-root, dependency ghim và tương thích manifest; cung cấp image cho D4/D6 |
| D2 — Artifact/runtime | Người 1; `scripts/fetch_artifacts.py`, `src/app/service.py`, `configs/app.yaml`, `.gitignore`; kiểm tra config retrieval/Java | Thực hiện mục 3–4, giữ checksum và model; cần D0; cung cấp layout/lệnh fetch cho D4/D5, chặn D6 nếu thiếu đầu vào |
| D3 — Startup/manifest | Người 1; `src/api/app.py`, service, loader chung, test liên quan | Nạp thành công mới healthy, sai manifest thoát lỗi, đối chiếu phiên bản theo SPEC; D4/D6 cần hành vi này |
| D4 — UI/Compose | Người 2; `Dockerfile.ui`, `requirements-ui.txt`, `docker-compose.yml`, `.dockerignore` | Thực hiện cổng/env/mount/health dependency; viết UI song song D1–D3, ghép chạy thật cần D0–D3 |
| D5 — Lệnh vận hành | Người 2; `Makefile`, `scripts/run_demo.sh`, `scripts/run_demo.ps1`, script smoke nếu cần | `fetch-artifacts`, `up`, `smoke`, `demo-local`; cùng artifact/config; hoàn tất cần D2/D4 |
| D6 — Nghiệm thu | Người 2 chạy, người 1 sửa/review API | Checkout sạch, offline, bốn mode tìm kiếm, lỗi artifact, user/quyền mount, feedback qua restart, kiểm tra image; cần D1–D5 |
| D7 — Bàn giao | Người 2 tổng hợp, người 1 xác nhận; `README.md`, tài liệu này, `CHANGELOG.md` | Lệnh đã chạy, commit/tag, nguồn/hash artifact, số đo/giới hạn và hướng dẫn cho người deploy; chỉ chốt sau D6 |

D2 sở hữu `.gitignore` và đường dẫn runtime; D4 sở hữu `.dockerignore` và Compose. Người 1 cung cấp thông tin API/artifact để người 2 cập nhật tài liệu này; tránh hai người sửa cùng phần cùng lúc. Mỗi task dùng nhánh riêng theo CLAUDE.md; không tự stage/commit thay đổi của người khác.

## 8. Điều kiện đóng D0 và bàn giao tiếp

- [x] Đọc SPEC và đối chiếu code/config/script hiện có.
- [x] Xác định service, cổng, config, bố trí artifact và feedback.
- [x] Xác định biến môi trường, kiến trúc mục tiêu và việc chưa kiểm chứng.
- [x] Chỉ rõ người sở hữu và task bị phụ thuộc.
- [x] Người 1 review/xác nhận quy ước API, đường dẫn và artifact (theo xác nhận của người giao việc trong chat ngày 2026-10-27).
- [x] Người 2 review/xác nhận quy ước UI, Compose và lệnh chạy (cùng nguồn xác nhận trên).

D0 được đóng theo xác nhận của người giao việc nêu trên; không tự điền tên người duyệt chưa được cung cấp. D1–D5 triển khai theo hợp đồng này; không coi D0 là bằng chứng bộ đóng gói đã chạy.

Kiểm chứng D0 chỉ gồm đọc/đối chiếu tài liệu, đường dẫn tham chiếu, diff và nội dung file định commit. Không áp dụng test runtime cho thay đổi chỉ có tài liệu. Khi có kết quả D1–D7, cập nhật cùng tài liệu này bằng lệnh, môi trường và kết quả thực tế; không tạo báo cáo trùng nội dung.

## 9. D1 — Image API và dependency CPU

### 9.1 File bàn giao và lựa chọn dependency

| File | Chức năng |
|---|---|
| `Dockerfile.api` | Python 3.11 trên Debian Bookworm, OpenJDK 17 headless, libgomp, user UID/GID 10001, một worker Uvicorn; chỉ copy module/config runtime và metadata chọn LR |
| `requirements-api.txt` | Dependency trực tiếp cho API, BM25/VNCoreNLP và encoder; Torch `2.5.1+cpu` từ index CPU chính thức |
| `requirements-train.txt` | Gom `requirements.txt` và `requirements-e5.txt` bằng `-r`, giữ nguyên pin training hiện tại, gồm Torch `2.5.1+cu121`; cài ở venv riêng |

API giữ Transformers 4.46.3, tokenizers 0.20.3 và các phiên bản số học theo requirements/config hiện có. Không thêm `sentence-transformers`: encoder/training hiện gọi AutoModel trực tiếp, `scripts/run_e5.py` ghi phiên bản gói này là null khi không cài. D3 vẫn phải đối chiếu manifest index thật; manifest training trong Git chỉ ghi Torch 2.5.1+cu121, không đủ để kết luận toàn bộ phiên bản index khớp.

Nguồn kiểm tra biến thể CPU: [hướng dẫn chính thức PyTorch 2.5.1](https://docs.pytorch.org/get-started/previous-versions/). Metadata/source PyPI của py-vncorenlp 0.1.4 xác nhận dependency pyjnius; pyjnius 1.9.0 có wheel CPython 3.11 Linux x86_64. Dockerfile yêu cầu wheel cho pyjnius, không cài compiler vào runtime.

Không sửa các file requirements gốc, code API/retrieval hay config runtime trong D1. Image có thư mục `/app/artifacts` trống và `/app/data/app` thuộc user app để chuẩn bị mount ở D4. Chỉ copy `models/lr_selection.json`, không copy trọng số. Chỉ copy `scripts/run_e5.py` vì SearchService có loader động cho E5 S2; không copy script training hay pipeline dữ liệu.

### 9.2 Lệnh kiểm chứng

Chạy từ gốc repo trên Docker Engine hỗ trợ Linux containers. Các lệnh này kiểm tra image độc lập, không thay thế smoke Compose của D5/D6.

```powershell
docker build --platform linux/amd64 --progress plain -f Dockerfile.api -t vnlegal-api:d1 .
docker run --rm --network none --entrypoint python vnlegal-api:d1 -c "import os, numpy as np, torch; from src.app.service import SearchService; from src.retrieval.bm25 import BM25Retriever; from src.retrieval.dense import DenseEncoder; from jnius import autoclass; assert os.getuid() == 10001; assert torch.__version__ == '2.5.1+cpu' and torch.version.cuda is None; assert torch.from_numpy(np.ones(1, dtype=np.float32)).numpy()[0] == 1; print('JVM:', autoclass('java.lang.System').getProperty('java.version')); print('CPU/imports/non-root: OK')"
docker run --rm --network none --entrypoint python vnlegal-api:d1 -c "from pathlib import Path; assert not any(Path('/app/artifacts').iterdir()); assert not Path('/app/runs').exists(); assert not Path('/app/src/ui').exists(); assert not Path('/app/scripts/train_e5.py').exists(); assert not list(Path('/app').rglob('*.safetensors')); assert not list(Path('/app').rglob('*.sqlite')); assert not list(Path('/app').rglob('*.jsonl')); print('App payload excludes artifacts/training/UI: OK')"
docker image inspect vnlegal-api:d1 --format '{{.Config.User}} {{json .Config.Cmd}}'
```

Dockerfile đã có self-check import, Torch–NumPy, non-root và JVM ngay trong build; bước này không nạp model. APP_CONFIG chỉ được xóa trong RUN self-check, vẫn là `configs/app.yaml` khi chạy container thật.

Sau khi có artifact đúng hash ở `./artifacts`, kiểm tra VNCoreNLP thật bằng một tiến trình mới (không gọi `autoclass` trước khi wrapper cấu hình JVM):

```powershell
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/artifacts,target=/app/artifacts,readonly" --entrypoint python vnlegal-api:d1 -c "from src.retrieval.text import load_segmenter; s = load_segmenter({'model_dir': '/app/artifacts/data/raw/vncorenlp', 'annotators': ['wseg'], 'max_heap_size': '-Xmx2g'}); words = s.word_segment('Tôi đang kiểm tra hệ thống tìm kiếm pháp luật.'); assert words and any(line.strip() for line in words); print(words)"
```

Lệnh mount ở trên là PowerShell; trên Linux dùng đường dẫn host tuyệt đối tương ứng. Không gọi hàm tải model của wrapper trong runtime. D1 không khởi động app tìm kiếm thật: cách giải quyết `artifact_root` và hành vi lỗi startup vẫn lần lượt thuộc D2/D3.

### 9.3 Kết quả và điều kiện đóng

Kiểm chứng ngày 2026-10-27, Docker Desktop 4.94.0, Engine 29.8.2, Linux/amd64 trên host Windows. Python trong image 3.11.18, Java 17.0.21. Đây là bằng chứng kỹ thuật của D1; chưa có xác nhận review chéo của người 2.

| Kiểm tra thực chạy | Kết quả |
|---|---|
| Resolve `requirements-api.txt` và `requirements-train.txt` cho Python 3.11/Linux x86_64 bằng uv | Exit 0 cho cả hai; giữ nguyên pin training gốc và phiên bản chính trùng API |
| `docker build --platform linux/amd64 --progress plain -f Dockerfile.api -t vnlegal-api:d1 .` | Exit 0; `pip check` báo không có dependency hỏng; self-check import, CPU Torch–NumPy, non-root và JVM đạt |
| Container `--network none`, import service/BM25/dense/E5, kiểm tra môi trường và JVM | Exit 0; Torch 2.5.1+cpu, Transformers 4.46.3, tokenizers 0.20.3; Java hoạt động, hai cờ offline bằng 1 |
| Kiểm tra payload và quyền ghi feedback | Exit 0; artifact rỗng, không có UI/training script, corpus, trọng số hay SQLite đóng sẵn; UID 10001 tạo/ghi SQLite được trong `/app/data/app` |
| VNCoreNLP wseg, `--network none`, bind model chỉ đọc | Exit 0; trả `['Tôi đang kiểm_tra hệ_thống tìm_kiếm pháp_luật .']` |
| Diff, link nội bộ, whitespace, pin requirements và danh sách COPY | Đạt; không có file bàn giao lớn hơn 1 MB, không phát hiện mẫu secret đã quét |

Image local: `vnlegal-api:d1`, ID `sha256:484f202161b7dfe1ee0d2c1c0c80167c8ef4926322c184ca2705787d03fa1fca`. `docker image inspect` ghi Size = 2068021408 byte; đây là giá trị CLI báo cho image, không gồm model/index/corpus mount ngoài. User mặc định `10001:10001`, CMD đúng một worker như mục 2. Chưa publish image lên registry.

Bộ VNCoreNLP kiểm thử được tải riêng từ `https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/{revision}/{file}`, với revision và ba tên file trong `configs/bm25.yaml`, đặt tại `.scratch/d1/vncorenlp`. Đã tính SHA-256 các file tải. Kiểm thử dùng lệnh VNCoreNLP ở mục 9.2 nhưng thay nguồn bind bằng đường dẫn tuyệt đối tới thư mục local đó; đích vẫn là `/app/artifacts/data/raw/vncorenlp`, chỉ đọc. Bộ này kiểm chứng wrapper/JVM/wseg, chưa thay thế việc xác minh toàn gói demo và manifest index ở D2/D3.

## 10. D2 — Chuẩn bị artifact và đường dẫn runtime

### 10.1 Lệnh bàn giao cho D4/D5

Chạy từ gốc checkout, dùng Python đã cài dependency của dự án. Tải ZIP gốc từ [thư mục phát hành](https://drive.google.com/drive/folders/1wTvyZm74OFUHFgUwGDfhE6u2H034BoAr?usp=sharing), rồi chạy (thay đường dẫn ZIP theo máy):

```sh
python -X utf8 scripts/fetch_artifacts.py --zip /path/to/vnlegal-demo-v1.zip --sha256 059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096 --output-dir ./artifacts
```

Trên Windows có thể dùng đường dẫn Python/ZIP của máy trong cùng lệnh. Mặc định `--output-dir` là `artifacts` ở gốc code; đích tương đối được chỉ định trên CLI tính từ thư mục chạy lệnh. Script kiểm tra hash ZIP, đường dẫn an toàn, danh sách file, file runtime bắt buộc (kể cả file nhị phân khai trong manifest BM25), kích thước và hash từng file trước khi ghi. Chạy lại bỏ qua file cùng hash; file khác nội dung bị từ chối nếu không có `--force`. Không dùng `--force` để thay frozen artifact.

Không cần đóng gói lại: `scripts/package_artifacts.py` hiện đã chứa đủ corpus, VNCoreNLP, index BM25, index dense B, model/tokenizer B và manifest. Metadata nhỏ `models/lr_selection.json` thuộc checkout/image theo mục 3.1; không lấy từ thư mục artifact và không chọn lại LR. D1 đã copy riêng metadata này vào image.

### 10.2 File và hành vi

- `scripts/fetch_artifacts.py`: chuẩn bị gói đã kiểm tra vào đích riêng, giữ nguyên byte. File mới có quyền `0644`; bổ sung quyền đọc/đi qua cho thư mục trong đích và quyền đọc cho file cùng hash để UID API đọc được, kể cả thư mục có sẵn với umask `077`. Không đổi quyền các thư mục nằm ngoài đích.
- `src/app/artifacts.py`: dùng chung kiểm tra SHA-256, manifest và đường dẫn cho fetch/service.
- `src/app/service.py`: giải quyết đường dẫn artifact từ `artifact_root`, kiểm tra đủ file/hash trước khi nạp; config và LR metadata từ gốc code; SQLite từ gốc code ngoài artifact. Không fallback sang dữ liệu legacy khi đã có `artifact_root`.
- `configs/app.yaml`: cùng `artifact_root: artifacts`, `device: cpu`, model B và tham số truy hồi cho Docker/local. `configs/bm25.yaml`, `configs/dense_e5_ft.yaml` giữ nguyên để không đổi cấu hình pipeline; service truyền đường dẫn đã giải quyết và device từ app config.
- `src/retrieval/text.py`: ánh xạ executable Java mặc định theo Windows/Linux, giữ các đường dẫn executable tùy chỉnh.
- `.gitignore`: bỏ qua `artifacts/`.
- `tests/test_artifacts.py`: bảo vệ checksum, kiểm kê, đường dẫn ZIP, xung đột đích, metadata LR và SQLite nằm ngoài artifact.

D4 mount `./artifacts` → `/app/artifacts:ro`, volume ghi feedback → `/app/data/app`; không mount artifact vào UI. D5 dùng cùng `configs/app.yaml`. Các đường dẫn và cờ offline giữ theo mục 4–5. D2 không sửa/rebuild corpus, model, index hay manifest đã freeze.

### 10.3 Kiểm chứng ngày 2026-10-27

- Gói gốc giải nén vào `./artifacts`: SHA-256 ZIP khớp giá trị README; cả 23 file khớp kích thước/hash trong `MANIFEST.json`. Chạy lại sau sửa code thành công, không thay file cùng hash.
- `python -m pytest tests/test_artifacts.py tests/test_api_contract.py -q`: **47 passed, 2 skipped**, một cảnh báo deprecation từ Starlette/AnyIO trong môi trường test host Python 3.12. Hai trường hợp test quyền POSIX được skip trên Windows; kiểm thử riêng trong Linux xác nhận file/thư mục đọc được với umask `077`, gồm thư mục đích có sẵn quyền `0700`. Đã tái hiện lỗi quyền file và thiếu file nhị phân BM25 trước sửa; test S2 thiếu đường dẫn provenance cũng fail trước sửa và pass sau sửa.
- Đã thử `python -m pytest -q` trên host: dừng ở collection của `test_bm25.py`, `test_data_pipeline.py`, `test_e5.py`, `test_review_tables.py` do môi trường thiếu `bm25s`, `transformers`, `torch`, `pyarrow`; chưa coi toàn bộ suite đạt.

Kiểm thử runtime Linux dùng image `vnlegal-api:d1` và code D2, user UID 10001, `--network none`, bind mount `./artifacts` chỉ đọc, SQLite trên tmpfs riêng tại `/app/data/app`: service nạp thành công; `/health`, `/v1/info`, tìm kiếm đủ bốn mode, ghi feedback và export CSV đều HTTP 200. Gửi lặp feedback vẫn một dòng; đóng/mở lại SQLite đọc được bản ghi. Cả 23 hash artifact vẫn đúng sau tìm kiếm/feedback. Lần nạp qua bind mount Windows mất khoảng **598 giây**; tiến trình chờ I/O `p9_client_rpc` khi Java đọc vocabulary. Đây là số đo của lần kiểm thử này, không phải yêu cầu RAM hay thời gian khởi động đã chốt cho D4/D6.

Đây không thay thế nghiệm thu Compose D6, nhất là volume feedback mới/tái sử dụng qua restart và thời gian healthcheck trên máy triển khai. D2 không thay đổi hành vi fail-fast startup hoặc chính sách đối chiếu môi trường manifest thuộc D3.

Kiểm thử lại với bản code cuối và cùng byte artifact được sao chép sang volume Linux, mount chỉ đọc: nạp service **19,6 giây**, toàn bộ kiểm tra HTTP/feedback/hash nêu trên đạt. Chênh lệch với Windows bind mount cần được D6 xét khi chọn vị trí lưu artifact và thời gian healthcheck. Không dùng số đo này để mặc định thời gian khởi động cho mọi máy.

Resolver có thể tái hiện bằng `uv pip compile <requirements-api.txt hoặc requirements-train.txt> --python-version 3.11 --python-platform x86_64-manylinux_2_28 --index-strategy unsafe-best-match --output-file <file local trong .scratch/d1/>` (cần interpreter Python 3.11 và mạng). Chiến lược index ở đây theo cách pip chọn phiên bản giữa PyPI và index Torch. Các source tải, output resolver, script kiểm tra tạm và log JSON nằm local trong `.scratch/d1/`, không commit và không là đầu vào của pipeline chính thức.

D1 hoàn thành kiểm chứng kỹ thuật theo tiêu chí đã giao: build Linux, import, Torch CPU, non-root, JVM và tách từ thật đều đạt. Chưa chạy training, chưa nạp index/model semantic thật, chưa đối chiếu đủ manifest index, chưa nghiệm thu `/health` của service tìm kiếm, Compose hay persistence qua volume. Các phần này tiếp tục ở D2–D6; không dùng kết quả D1 để tuyên bố ứng dụng đã sẵn sàng deploy.
