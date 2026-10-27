# Đóng gói Docker — quy ước tích hợp và bàn giao

## 1. Phạm vi và trạng thái

- Ngày lập: 2026-10-27; nhánh làm việc: `task/Docker-Compose`.
- D0 chỉ xác lập quy ước kỹ thuật cho hai người đóng gói. Tài liệu này là đầu vào chung cho D1–D7 và người tiếp nhận deploy; không phải ghi chú phiên hay báo cáo chạy Docker thành công.
- Căn cứ: [SPEC mục 7.4, 13 và 14](../../SPEC.md), [quy tắc file/commit](../../CLAUDE.md), [quy trình bàn giao](../workflow.md).
- Người 1 phụ trách API, dependency, artifact và runtime; người 2 phụ trách UI, Compose, lệnh chạy, kiểm thử tích hợp và tổng hợp bàn giao. Chưa gán tên cá nhân.
- D0: đã soạn quy ước, chờ hai người phụ trách review/xác nhận. Chưa có bằng chứng đồng thuận của hai người.
- D1–D7: chưa thực hiện trong mốc D0. Chưa build image, chạy Compose, đo tài nguyên hay kiểm chứng Linux/offline.
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

Đây là hợp đồng cần triển khai ở D2, **chưa phải hành vi hiện có**:

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
- [ ] Người 1 review/xác nhận quy ước API, đường dẫn và artifact.
- [ ] Người 2 review/xác nhận quy ước UI, Compose và lệnh chạy.

D0 hoàn tất về nội dung tài liệu khi bốn mục đầu đủ rõ; chỉ đóng mốc phối hợp khi hai xác nhận cuối được ghi bằng tên/ngày hoặc liên kết review thật. Không tự điền người duyệt. Sau đó D1–D5 triển khai theo hợp đồng này; không coi D0 là bằng chứng bộ đóng gói đã chạy.

Kiểm chứng D0 chỉ gồm đọc/đối chiếu tài liệu, đường dẫn tham chiếu, diff và nội dung file định commit. Không áp dụng test runtime cho thay đổi chỉ có tài liệu. Khi có kết quả D1–D7, cập nhật cùng tài liệu này bằng lệnh, môi trường và kết quả thực tế; không tạo báo cáo trùng nội dung.
