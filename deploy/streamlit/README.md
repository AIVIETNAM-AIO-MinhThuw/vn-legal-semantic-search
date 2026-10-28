# Streamlit Community Cloud: UI + API + model CPU

Entrypoint này khởi động toàn bộ demo trên Cloud, không gọi API trên máy cá nhân.
Không cần Quick Tunnel hoặc Docker trên máy người xem. Đây là bản thử đóng gói
nguyên source `main` tại commit `4a83ee616084f43f220ab4c73ee77ece9b54469c`;
không phải loader D3 của nhánh đóng gói và không tuyên bố D3/D6 đã đạt.

## Tạo ứng dụng

Sau khi các file đóng gói đã được commit/push lên nhánh task, đăng nhập
[Streamlit Community Cloud](https://share.streamlit.io/) bằng GitHub, cấp quyền
repo rồi chọn **Create app**:

| Trường | Giá trị |
|---|---|
| Repository | `AIVIETNAM-AIO-MinhThuw/vn-legal-semantic-search` |
| Branch | `task/TestCheckErrorDocker` |
| Main file path | `deploy/streamlit/app.py` |
| Advanced settings → Python | **3.11** |

Không chọn `src/ui/app.py`: entrypoint đó chỉ gọi API và không chuẩn bị model.
Community Cloud tìm `requirements.txt` cạnh entrypoint; file này dùng lại
`requirements-api.txt` và `requirements-ui.txt` của repo. `packages.txt` ở gốc repo khai báo
Java headless và libgomp. Không dùng dependency training hoặc Torch CUDA.
Không cần nhập secret/API key cho gói public hiện tại.

## Lần khởi động đầu

1. Tải source snapshot từ GitHub ở commit đã ghim. Chỉ lấy 53 file được liệt kê
   trong `source_manifest.json`, kiểm SHA-256 từng file, không thay core trong repo.
2. Tải ZIP v1 từ URL Drive public, kiểm SHA-256 ZIP, gọi lại
   `scripts/fetch_artifacts.py` để kiểm đủ file và hash từng artifact.
3. Source và artifact nằm trong runtime tạm `/tmp/vnlegal-streamlit/<commit>`.
   Các đường dẫn legacy của main được nối bằng symlink; artifact chuyển sang
   quyền chỉ đọc. Feedback nằm riêng dưới `source/data/app`.
4. Chạy API với CPU, 2 luồng tính toán và một worker trên localhost, cổng động.
   Chỉ mở UI sau khi API `/health` trả 200. Nếu API lỗi/không healthy thì hiện lỗi,
   không chuyển sang dữ liệu mẫu. Không mở thêm cổng API công khai.
5. UI chạy nguyên file main; theme root giữ `primaryColor = "#1F4E8C"` đúng main.

Chuẩn bị dữ liệu và nạp model có thể mất nhiều phút; xem log deploy nếu tải Drive
bị quota hoặc hết RAM. Không sửa manifest/index để vượt qua lỗi. URL app Cloud
chỉ được coi là hoạt động sau khi đã thử tìm kiếm thật và kiểm tra phản hồi.

## Giới hạn cần giữ khi bàn giao

- Community Cloud có hạn mức CPU/RAM và ngủ khi lâu không truy cập. Chưa có số
  đo tài nguyên trên Cloud; không bảo đảm nguồn lực tương đương máy local.
- Đổi nơi chạy không sửa hạn chế tính toán highlight chậm hoặc API main xử lý
  đồng bộ. UI chờ tối đa 180 giây; nhiều truy vấn đồng thời vẫn có thể timeout.
- SQLite runtime **không có cam kết lưu bền qua reboot/redeploy**. Tải CSV feedback
  trong UI trước khi reboot hoặc bàn giao; muốn lưu bền cần phương án storage riêng.
- Không commit ZIP/model/index/SQLite hoặc tải log chứa truy vấn người dùng lên Git.

## Kiểm tra local

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_streamlit_bootstrap.py -q --basetemp=.scratch/streamlit-tests
```

Linux đã có Java và dependencies có thể chạy từ gốc repo:

```sh
python -m streamlit run deploy/streamlit/app.py
```

Để tái dùng ZIP tải sẵn thay vì tải Drive, đặt `VNLEGAL_ARTIFACT_ZIP` tới file ZIP;
vẫn kiểm toàn bộ checksum. Chỉ dùng `VNLEGAL_RUNTIME_DIR` nếu cần chọn nơi lưu
runtime tạm. Không trỏ biến này vào artifact gốc.

## Tái sinh manifest source

Manifest chỉ mô tả source snapshot đã kiểm chứng, không bổ sung provenance cho
model/index. Sau khi tạo bundle bằng `scripts/package_deploy.py` như hướng dẫn
`docs/deploy_cpu.md`, dùng Python 3.11 tại gốc repo:

```python
import hashlib, json
from pathlib import Path
release = Path('release/deploy-cpu')
old = json.loads((release / 'RELEASE.json').read_text())
spec = {key: old[key] for key in ('source_commit', 'source_files_sha256')}
spec.update(
    repository='AIVIETNAM-AIO-MinhThuw/vn-legal-semantic-search',
    artifact_zip_sha256=old['artifact_zip_sha256'],
    artifact_manifest_sha256=hashlib.sha256((release / 'artifacts/MANIFEST.json').read_bytes()).hexdigest(),
    artifact_url='https://drive.usercontent.google.com/download?id=1B-9hjMnCQGQBAr_voWwYqLjViuX5pcLa&export=download&confirm=t',
)
Path('deploy/streamlit/source_manifest.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```

Tài liệu nền tảng: [dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies),
[deploy](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy),
[resource limits và sleep](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).
