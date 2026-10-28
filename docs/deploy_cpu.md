# Deploy web dùng chung cho Windows và macOS

Người dùng mở đường link bằng trình duyệt trên Windows/macOS. Docker và model chạy trên một server Linux/amd64 CPU; máy người dùng không cần Docker, Python, Java hoặc GPU. Bundle đã kiểm chứng nằm trong `release/deploy-cpu`; xem `RELEASE.json` để biết commit main nguyên bản đã đóng gói.

## 1. Chuẩn bị server

Cần server Linux x86_64 có quyền SSH, Docker Engine và Compose plugin. Máy ARM/Apple Silicon chưa được kiểm chứng cho bundle này. Server cần mạng lúc build/tải dependency; inference dùng model/index local.

Kiểm tra trên server:

```sh
uname -m
docker version
docker compose version
free -h
df -h .
```

Kiến trúc phải là `x86_64`. Cài Docker theo [hướng dẫn chính thức cho Ubuntu](https://docs.docker.com/engine/install/ubuntu/) hoặc [bản Linux khác](https://docs.docker.com/engine/install/). Dùng user có quyền Docker hoặc thêm `sudo` trước các lệnh Docker trong tài liệu.

Đã chạy trên host RAM 16 GiB, Docker VM giới hạn 7.604 GiB; đây là môi trường đo, chưa phải mức RAM tối thiểu của server. Bundle có artifact khoảng 1.28 GB và hai image khoảng 2.15 GB/0.84 GB; cần thêm chỗ cho build cache và image layers.

## 2. Chuyển bundle lên server

Từ PowerShell Windows, thay ba giá trị tương ứng với máy của bạn:

```powershell
$deployHost = 'IP_HOAC_HOSTNAME_SERVER'
$deployUser = 'USER_SSH'
$bundle = 'C:\Users\nhatm\Downloads\NLP\Project\vn-legal-semantic-search\release\deploy-cpu'
scp -r $bundle "${deployUser}@${deployHost}:~/vnlegal-demo-20261028"
ssh "${deployUser}@${deployHost}"
```

Từ macOS, dùng `scp -r /duong-dan/deploy-cpu USER@SERVER:~/vnlegal-demo-20261028` rồi `ssh USER@SERVER`.

Chuyển cả `artifacts/`, không chỉ source hoặc Dockerfile. Bundle đã giải nén và xác minh ZIP/SHA-256; không phải ghép ZIP với file checksum.

## 3. Build và khởi chạy trên server

```sh
cd ~/vnlegal-demo-20261028
docker compose -p vnlegal-demo config --quiet
docker compose -p vnlegal-demo build
docker compose -p vnlegal-demo up -d --wait --wait-timeout 900
docker compose -p vnlegal-demo ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8501/_stcore/health
curl --fail http://127.0.0.1:8000/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Quyền của người lao động","mode":"semantic","top_k":1}'
```

Giữ project name `vnlegal-demo` ở mọi lệnh để dùng cùng volume feedback. API chỉ sẵn sàng khi health trả 200. Nếu lỗi, xem `docker compose -p vnlegal-demo logs --tail 100 api ui`; kiểm tra artifact đúng vị trí/quyền đọc và RAM server. Không rebuild index hoặc sửa manifest để xử lý deploy.

## 4. Mở dùng thử ngay bằng SSH tunnel

Trên Windows PowerShell hoặc macOS Terminal, mở một terminal khác và giữ lệnh này chạy:

```sh
ssh -N -L 18501:127.0.0.1:8501 USER_SSH@SERVER
```

Mở `http://127.0.0.1:18501` bằng trình duyệt. Cách này chỉ cần SSH, chưa cần domain hoặc public cổng ứng dụng. Dừng tunnel bằng Ctrl+C; ứng dụng trên server vẫn chạy.

## 5. Tạo đường link HTTPS cho mọi người

Trỏ DNS domain/subdomain về IP server, mở cổng 80/443 tại firewall nhà cung cấp, cài Caddy trên server theo [hướng dẫn chính thức](https://caddyserver.com/docs/install). Giữ API/UI bind `127.0.0.1` như Compose; không mở trực tiếp cổng 8000/8501 ra Internet.

Thêm site vào cấu hình Caddy hiện có, thay domain mẫu bằng domain thật:

```caddyfile
legal.example.com {
    reverse_proxy 127.0.0.1:8501
}
```

Kiểm tra và reload sau khi đã lưu cấu hình:

```sh
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
curl --fail https://legal.example.com/_stcore/health
```

Caddy tự cấp/gia hạn HTTPS khi DNS và cổng 80/443 đúng; reverse proxy hỗ trợ kết nối ứng dụng. Xem [reverse proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy) và [automatic HTTPS](https://caddyserver.com/docs/automatic-https). Sau bước này, Windows/macOS chỉ cần mở `https://DOMAIN_CUA_BAN`.

## 6. Vận hành và giữ feedback

```sh
docker compose -p vnlegal-demo logs --tail 100 api ui
docker compose -p vnlegal-demo restart
docker compose -p vnlegal-demo down
docker compose -p vnlegal-demo up -d --wait --wait-timeout 900
```

Không thêm `-v` vào `down` nếu cần giữ feedback. Để lưu CSV backup trên server:

```sh
curl --fail http://127.0.0.1:8000/v1/feedback/export -o feedback-backup.csv
```

Trước khi triển khai bản mới, giữ bundle cũ và tag image cũ bằng tên riêng, ví dụ `vnlegal-api:previous` và `vnlegal-ui:previous`. Nếu bản mới lỗi, trỏ lại hai image `:local` vào tag cũ rồi `up --no-build -d --force-recreate --wait --wait-timeout 900` với cùng project name; không xóa volume. Lần triển khai đầu chưa có bản trước để rollback.

## Phạm vi đã kiểm chứng

Bundle nguyên main đã build/chạy CPU, bốn mode tìm kiếm, offline inference, feedback qua endpoint sau recreate và render kết quả bằng Streamlit AppTest. Chưa triển khai trên server của nhóm hoặc kiểm tra domain/HTTPS thật vì chưa có thông tin server.

Bundle giữ nguyên cách kiểm tra manifest/startup của main; không bổ sung D3 strict provenance/fail-fast. Các giới hạn này được giữ trong `RELEASE.json`/biên bản phase; không coi deploy thành công là đã hoàn thành yêu cầu D3 nghiêm ngặt.
