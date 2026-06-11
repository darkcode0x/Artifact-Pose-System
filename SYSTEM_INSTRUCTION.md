# Hướng Dẫn Hệ Thống Artifact Pose System

> Cập nhật: 28/05/2026
> Tài liệu này mô tả cách hệ thống đang hoạt động theo source code hiện tại, bao gồm server, mobile app, Raspberry Pi device agent, pose workflow, AI inspection, tài khoản và dữ liệu runtime.

---

## 1. Tổng Quan

Artifact Pose System là hệ thống kiểm tra hiện vật bằng camera và cơ cấu điều khiển trên Raspberry Pi. Hệ thống dùng golden pose để căn chỉnh camera/thiết bị về vị trí tham chiếu, sau đó chạy kiểm tra ảnh bằng SSIM và model AI.

Các thành phần chính:

| Thành phần | Thư mục | Vai trò |
|---|---|---|
| FastAPI server | `server/` | REST API, auth, DB, MQTT bridge, pose service, AI inspection |
| PostgreSQL | Docker service `postgres` | Lưu user, artifact, schedule, image, comparison, alert, device |
| Mosquitto MQTT | Docker service `mosquitto` | Gửi lệnh tới Pi và nhận ACK/status |
| Flutter app | `client/artifact_app/` | Giao diện Android cho admin/operator |
| Raspberry Pi agent | `embed/device_agent/` | Nhận lệnh MQTT, điều khiển camera/servo/slider, upload ảnh |
| AI model | `model/` | Model YOLO `.pt`, tự mount vào `/app/model` trong container |

Luồng tổng thể:

```text
Mobile App
  -> REST API
FastAPI Server
  -> MQTT cmd/{device_code}
Raspberry Pi Agent
  -> chụp ảnh / di chuyển phần cứng
  -> MQTT ack/{device_code}, status/{device_code}
  -> upload ảnh qua HTTP
FastAPI Server
  -> pose correction / AI inspection / lưu DB
Mobile App
  -> xem kết quả
```

---

## 2. Cấu Trúc Dự Án Quan Trọng

```text
Artifact-Pose-System/
├── README.md                            Tổng quan ngắn về dự án
├── DEPLOY_INSTRUCTION.md                Hướng dẫn deploy PC, Android, Pi
├── SYSTEM_INSTRUCTION.md                Tài liệu hệ thống này
├── artifact_db.sql                      Schema PostgreSQL tham chiếu
├── model/
│   └── best_Quyen.pt                    Model AI hiện có
├── server/
│   ├── docker-compose.yml               Postgres + Mosquitto + FastAPI
│   ├── Dockerfile                       Build runtime và native pose solver
│   ├── .env.docker                      Env chạy Docker
│   ├── env.docker.example               Env mẫu
│   ├── app/
│   │   ├── api/routes/                  REST API routes
│   │   ├── models/                      SQLAlchemy models
│   │   ├── schemas/                     Pydantic schemas
│   │   ├── services/                    Business services
│   │   └── modules/artifact_pose/       Pose initialization/correction
│   ├── data/
│   │   ├── device_registry.json         Registry device Pi
│   │   ├── camera_params/               Camera calibration theo lens position
│   │   ├── uploads/                     Ảnh upload, golden poses, artifact images
│   │   └── logs/                        MQTT và inspection JSONL logs
│   └── tools/
│       ├── create_admin.py              Tạo/cập nhật admin bootstrap
│       ├── list_users.py                Liệt kê user
│       └── smoke_test_api_mqtt_ack.py   Smoke test API + MQTT + ACK
├── client/artifact_app/
│   ├── lib/services/api_config.dart     Base URL cho app
│   ├── lib/services/api_client.dart     HTTP client có Bearer token
│   └── lib/screens/                     Màn hình app
└── embed/device_agent/
    ├── .env                             Env của Pi agent
    ├── api_client.py                    HTTP client của Pi
    ├── main_app.py                      Launcher tương thích cũ
    └── runtime/main_app.py              Main loop MQTT + phần cứng
```

---

## 3. Khái Niệm Cốt Lõi

### 3.1. Artifact

Artifact là hiện vật cần kiểm tra. Mỗi artifact có:

- `artifact_id`: ID chuỗi 6 ký tự.
- `name`, `description`, `location`.
- `status`: trạng thái hiện vật.
- `baseline_image_id`: ảnh tham chiếu/baseline đang dùng để so sánh.
- lịch sử inspection và alert.

### 3.2. Golden Pose

Golden pose là tư thế chuẩn của camera so với artifact. Hệ thống tạo golden pose bằng một cặp ảnh stereo left/right và marker ChArUco.

Golden pose được lưu theo artifact:

```text
server/data/uploads/golden_poses/{artifact_id}/golden_pose.yaml
server/data/uploads/golden_poses/{artifact_id}/golden_pose_descriptors.npy
```

Nếu hệ thống thấy file golden pose kiểu cũ ở vị trí global, `PoseService` có logic migrate sang thư mục per-artifact.

### 3.3. Device

Hiện tại hệ thống theo mô hình registry-driven device.

- Pi gọi `POST /api/v1/devices/get_device_id` khi khởi động.
- Server dùng `server/data/device_registry.json` để cấp hoặc trả lại mã thiết bị.
- Server upsert record vào bảng `iot_devices`.
- App hiển thị thiết bị từ DB, nhưng thao tác vận hành dùng `device_code`.

Quy ước:

| Tên | Ý nghĩa |
|---|---|
| `device_id` | ID nội bộ DB, chuỗi 6 ký tự |
| `device_code` | Mã Pi/MQTT, ví dụ `dev-bbb742d369` |
| `machine_hash` | Fingerprint Pi dùng để map sang `device_code` |

Thiết bị hiện tại:

```text
device_code = dev-bbb742d369
```

### 3.4. Baseline Stereo

Baseline stereo đã được khóa cố định:

| Tham số | Giá trị |
|---|---:|
| Baseline vật lý | `100.0 mm` |
| Stepper scale | `800 steps/mm` |
| Slider move cho stereo | `80000 steps` |
| Pose solver baseline | `0.10 m` |

App không còn ô nhập baseline. API `start-initialization` không nhận `baseline_mm` hoặc `steps_per_mm`. Pi cũng bỏ qua baseline từ command và luôn dùng 80000 steps.

---

## 4. Auth, Role Và Bảo Vệ Route

### 4.1. Role

Hệ thống có 2 role chính:

| Role | Quyền |
|---|---|
| `admin` | Quản lý user, artifact, device workflow, schedule, model, profile |
| `operator` | Sử dụng dashboard, artifact, schedule, device workflow, profile |

User `is_active=false` không thể đăng nhập và token của user inactive cũng bị chặn.

### 4.2. Tài Khoản Mặc Định

Docker startup chạy:

```text
tools/create_admin.py --username ${ADMIN_USERNAME:-admin} --password ${ADMIN_PASSWORD:-123456} --role admin
```

Mặc định dev:

```text
username: admin
password: 123456
role: admin
```

Không có operator mặc định bắt buộc trong source hiện tại. Có thể tạo operator bằng màn hình Users của admin, bằng `/api/v1/users`, hoặc self-register qua `/api/v1/auth/register`.

### 4.3. Nhóm Route Chính

| Route | Auth hiện tại | Ghi chú |
|---|---|---|
| `GET /`, `GET /health` | Public | Health check |
| `GET /mqtt/health`, `GET /mqtt/events` | Public | Debug MQTT trong LAN |
| `POST /api/v1/auth/login` | Public | Trả JWT |
| `POST /api/v1/auth/register` | Public | Tự tạo operator |
| `/api/v1/users/*` | JWT, nhiều route admin-only | Quản lý user |
| `/api/v1/artifacts/*` | JWT | Artifact, reference, inspection từ app |
| `/api/v1/schedules/*` | JWT | Lịch kiểm tra |
| `GET /api/v1/devices` | JWT | Danh sách thiết bị |
| `POST /api/v1/devices/get_device_id` | Public cho Pi | Đăng ký/lấy `device_code` |
| `/api/v1/devices/{device_code}/status` | Public trong LAN | Status realtime từ command service |
| `/api/v1/devices/{device_code}/acks` | Public trong LAN | ACK history |
| `/api/v1/devices/{device_code}/queue_move` | Public trong LAN | Gửi lệnh MQTT tới Pi |
| `/workflows/{device_code}/*` | JWT | Start capture/alignment/initialization |
| `/pose/health`, `/pose/correct`, `/pose/golden-pose/...` | JWT | Pose manual/status |
| `POST /pose/initialize_golden` | JWT hoặc registered device | Pi upload stereo pair |
| `POST /inspections/upload` | Public cho Pi trong LAN | Pi upload ảnh alignment/inspection |
| `/models/*` | JWT; load/delete admin-only | Quản lý/chạy model |

Lưu ý bảo mật: một số endpoint device/Pi vẫn public trong LAN để không phá luồng Pi agent. Không mở server trực tiếp ra Internet khi chưa thêm device token/MQTT auth/firewall.

---

## 5. Cấu Hình Server

File Docker env chính:

```text
server/.env.docker
```

Các nhóm cấu hình quan trọng:

```env
# Database
POSTGRES_DB=artifact_auth
POSTGRES_USER=artifact
POSTGRES_PASSWORD=artifact123

# Bootstrap admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=123456
AUTH_SECRET_KEY=CHANGE_ME_AUTH_SECRET
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=60

# MQTT
MQTT_HOST=mosquitto
MQTT_PORT=1883
MQTT_CMD_TOPIC_TEMPLATE=cmd/{device_id}
MQTT_ACK_TOPIC_TEMPLATE=ack/{device_id}
MQTT_STATUS_TOPIC_TEMPLATE=status/{device_id}

# Pose/camera
ARTIFACT_LENS_POSITION=1.5
MAX_ALIGNMENT_ITERATIONS=7
ALIGNMENT_TIMEOUT_SEC=300

# Chiều correction phần cứng
SIGN_MOVE_X=1
SIGN_MOVE_Z=1
SIGN_ROTATE_PAN=-1
SIGN_ROTATE_TILT=-1
```

Docker Compose mount:

```text
server/data -> /app/data
model       -> /app/model
```

Camera params mặc định theo lens:

```text
server/data/camera_params/camera_params_lens_1.5.yaml
```

---

## 6. Raspberry Pi Device Agent

### 6.1. Cấu Hình `.env`

File:

```text
embed/device_agent/.env
```

Ví dụ:

```env
DEVICE_ID=
USE_SERVER_DEVICE_ID=true
SERVER_BASE_URL=http://192.168.137.1:8000

MQTT_HOST=192.168.137.1
MQTT_PORT=1883

IMAGE_DIR=./data/pictures
DEFAULT_ARTIFACT_ID=artifact_demo_001
LENS_POSITION=1.5

SLIDER_FAST_RATIO=0.85
SLIDER_FAST_PULSE_DELAY_SEC=0.00035
SLIDER_SLOW_PULSE_DELAY_SEC=0.0008
AUTO_CAPTURE_AFTER_MOVE=true
```

Nếu `DEVICE_ID` để trống và `USE_SERVER_DEVICE_ID=true`, Pi tự tính `machine_hash` và xin `device_code` từ server.

### 6.2. Chạy Agent

```bash
cd /home/pi/Artifact-Pose-System/embed/device_agent
PYTHONPATH=. python3 runtime/main_app.py
```

Hoặc:

```bash
PYTHONPATH=. python3 main_app.py
```

### 6.3. MQTT Topics

Với `device_code=dev-bbb742d369`, topic là:

```text
cmd/dev-bbb742d369       Server -> Pi
ack/dev-bbb742d369       Pi -> Server
status/dev-bbb742d369    Pi -> Server
```

Pi gửi heartbeat status định kỳ để app biết thiết bị online/offline.

### 6.4. Phần Cứng Điều Khiển

Mặc định trong `hardware_controller.py`:

| Thành phần | Giá trị |
|---|---|
| Servo pan channel | `0` |
| Servo tilt channel | `1` |
| Home yaw | `110°` |
| Home pitch | `35°` |
| X PUL/DIR | GPIO `17` / `27` |
| Z PUL/DIR | GPIO `22` / `23` |
| Microstep | `32` |

Khi khởi động, Pi đưa servo về home. Khi capture stereo/golden pose, Pi cũng đưa servo về home trước khi chụp.

---

## 7. Mobile App

Flutter app nằm tại:

```text
client/artifact_app/
```

Base URL được resolve trong:

```text
client/artifact_app/lib/services/api_config.dart
```

Ưu tiên cấu hình khi build:

```bash
--dart-define=API_BASE_URL=http://<server-ip>:8000
```

Nếu không truyền `--dart-define`, app dùng `_pcIp` hardcode trong `api_config.dart`.

Các màn hình chính:

| Màn hình | Chức năng |
|---|---|
| Login | Đăng nhập JWT |
| Operator Dashboard | Tổng quan artifact, alert, device, schedule, profile |
| Admin Dashboard | Tổng quan và quản lý user |
| Artifacts | Tạo/sửa/xóa artifact, reference image, inspection history |
| IoT Devices | Danh sách Pi, trạng thái online, workflow |
| Device Workflow | Capture reference, camera alignment, run inspection |
| Schedule | Tạo/cập nhật/xóa lịch kiểm tra |
| Alerts | Xem cảnh báo từ inspection |
| Profile | Xem/sửa hồ sơ, đổi mật khẩu |
| Users | Admin quản lý user |

---

## 8. Quy Trình Sử Dụng Đầu Cuối

### Bước 1: Khởi Động Hạ Tầng

Trên PC:

```bash
cd /home/thepiece/System/Artifact-Pose-System/server
docker compose --env-file .env.docker up -d
curl http://127.0.0.1:8000/health
```

Trên Pi:

```bash
cd /home/pi/Artifact-Pose-System/embed/device_agent
PYTHONPATH=. python3 runtime/main_app.py
```

Trên Android:

- Mở app đã build đúng `API_BASE_URL`.
- Đăng nhập bằng admin/operator.

### Bước 2: Kiểm Tra Device

Trong app:

1. Vào Dashboard.
2. Chọn IoT Devices.
3. Kiểm tra device `dev-bbb742d369`.
4. Device cần online trước khi start workflow.

Server xác định online bằng MQTT heartbeat trong khoảng gần nhất.

### Bước 3: Tạo Hoặc Chọn Artifact

Trong app:

1. Vào Artifacts.
2. Tạo artifact mới hoặc chọn artifact có sẵn.
3. Ghi nhớ artifact ID nếu cần debug qua API/log.

### Bước 4: Capture Reference Image / Golden Pose

Mục đích: tạo golden pose và ảnh baseline cho artifact.

Điều kiện:

- Pi online.
- Camera hoạt động.
- Marker ChArUco đúng chuẩn nằm rõ trong khung hình.
- Artifact đã được chọn.

Trong app:

1. Vào IoT Devices.
2. Chọn device.
3. Chọn artifact.
4. Nhấn Capture Reference Image.

Luồng phía sau:

```text
App -> POST /workflows/{device_code}/start-initialization
Server -> MQTT action=capture_stereo_pair
Pi -> servo về home
Pi -> chụp LEFT
Pi -> slider X +80000 steps, tương ứng baseline cố định 100mm
Pi -> chụp RIGHT
Pi -> slider X -80000 steps về vị trí ban đầu
Pi -> POST /pose/initialize_golden kèm left/right/artifact_id/device_code
Server -> detect ChArUco diamond + ORB + triangulation
Server -> lưu golden_pose.yaml per-artifact
Server -> lưu ảnh golden left làm baseline image của artifact
```

Không có bước nhập baseline trên app. Baseline luôn là 10cm.

### Bước 5: Camera Alignment

Mục đích: căn chỉnh camera/thiết bị về tư thế gần golden pose.

Trong app:

1. Sau khi reference/golden pose đã có, nhấn Start Camera Alignment.
2. Pi chụp ảnh alignment.
3. Server chạy pose correction.
4. Nếu chưa đạt tolerance, server gửi lệnh motor/servo về Pi.
5. Pi di chuyển và tự capture lại nếu `AUTO_CAPTURE_AFTER_MOVE=true`.
6. Lặp đến khi đạt tolerance, timeout, hoặc hết số vòng `MAX_ALIGNMENT_ITERATIONS`.

Luồng phía sau:

```text
App -> POST /workflows/{device_code}/start-alignment
Server -> MQTT action=capture, auto_alignment_loop=true
Pi -> capture ảnh
Pi -> POST /inspections/upload
Server -> pose correction
Server -> nếu lệch: publish movement command
Pi -> move servo/slider
Pi -> capture tiếp
Server -> nếu đạt: ACK alignment_complete, lưu latest metadata
```

### Bước 6: Run Inspection

Sau alignment thành công:

1. App gọi inspect-from-device cho artifact.
2. Server lấy ảnh capture mới nhất của device.
3. Server chạy kiểm tra so với baseline image.
4. Server tạo `ImageComparison`.
5. Nếu kết quả warning/damaged, server tạo `Alert`.

Kết quả bao gồm:

- ảnh hiện tại;
- ảnh tham chiếu;
- heatmap nếu có;
- `damage_score`;
- `ssim_score`;
- trạng thái `good`, `warning`, hoặc `damaged`;
- detections JSON nếu AI phát hiện.

### Bước 7: Xem Kết Quả

Trong app:

1. Vào Artifacts.
2. Chọn artifact.
3. Xem inspection history.
4. Vào Alerts để xem cảnh báo.

---

## 9. Marker Và Camera

Pose module hiện dùng ChArUco diamond/board với thông số trong `common.py`:

| Tham số | Giá trị |
|---|---:|
| Dictionary | `DICT_4X4_50` |
| Board | `CharucoBoard((3, 3), ...)` |
| Square length | `0.040 m` = `40 mm` |
| Marker length | `0.025 m` = `25 mm` |
| Stereo baseline solver | `0.10 m` |

Yêu cầu vật lý:

- Marker phải phẳng, không cong.
- In đúng tỷ lệ thật, không scale-to-fit.
- Marker nằm rõ trong ảnh left khi capture stereo.
- Ánh sáng đủ, không bóng lóa.
- Camera params phải khớp lens position đang dùng, hiện mặc định `1.5`.

Nếu golden initialization lỗi `400`, kiểm tra trước:

```bash
ls -lh server/data/uploads/pose_init/
docker compose --env-file server/.env.docker -f server/docker-compose.yml logs --tail=100 server
```

Thông báo thường gặp trong log:

```text
[initialize_golden] Diamond marker NOT detected in left image.
[initialize_golden] Stereo triangulation failed...
```

---

## 10. API Reference Tóm Tắt

### Auth

```text
POST /api/v1/auth/login
POST /api/v1/auth/register
```

Login:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

### Users

```text
GET    /api/v1/users/me
PATCH  /api/v1/users/me
POST   /api/v1/users/me/change-password
GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/{user_id}
PATCH  /api/v1/users/{user_id}
DELETE /api/v1/users/{user_id}
PATCH  /api/v1/users/{user_id}/toggle-active
POST   /api/v1/users/{user_id}/reset-password
```

Các route list/create/delete/toggle/reset cần admin. Reset password đặt mật khẩu về `111111`.

### Devices

```text
GET  /api/v1/devices
POST /api/v1/devices/get_device_id
POST /api/v1/devices/{device_code}/queue_move
POST /api/v1/devices/{device_code}/move
GET  /api/v1/devices/{device_code}/status
GET  /api/v1/devices/{device_code}/acks
```

Không còn API tạo/sửa/xóa device thủ công.

### Workflows

```text
POST /workflows/{device_code}/capture-request
POST /workflows/{device_code}/start-alignment
POST /workflows/{device_code}/start-initialization
GET  /workflows/{device_code}/latest-capture-metadata
```

`start-initialization` body hợp lệ:

```json
{
  "artifact_id": "abcdef",
  "camera_overrides": {}
}
```

Không gửi `baseline_mm` hoặc `steps_per_mm`.

### Pose

```text
GET  /pose/health
POST /pose/correct
POST /pose/initialize_golden
GET  /pose/golden-pose/{artifact_id}/status
```

`POST /pose/initialize_golden` nhận multipart:

| Field | Ý nghĩa |
|---|---|
| `left_file` | Ảnh stereo left |
| `right_file` | Ảnh stereo right |
| `artifact_id` | Artifact cần tạo golden pose |
| `device_id` hoặc `device_code` | Mã Pi trong registry nếu không dùng JWT |

### Artifacts

```text
GET    /api/v1/artifacts
POST   /api/v1/artifacts
GET    /api/v1/artifacts/{artifact_id}
PATCH  /api/v1/artifacts/{artifact_id}
DELETE /api/v1/artifacts/{artifact_id}
POST   /api/v1/artifacts/{artifact_id}/reference
POST   /api/v1/artifacts/{artifact_id}/inspect
POST   /api/v1/artifacts/{artifact_id}/inspect-from-device
GET    /api/v1/artifacts/{artifact_id}/inspections
```

### Schedules

```text
GET    /api/v1/schedules
POST   /api/v1/schedules
PATCH  /api/v1/schedules/{schedule_id}
DELETE /api/v1/schedules/{schedule_id}
```

`schedule_id` là chuỗi, không phải số nguyên.

### Inspections Upload Từ Pi

```text
POST /inspections/upload
```

Pi gửi multipart gồm `file` và `metadata` JSON.

### Models

```text
GET    /models
POST   /models/load
DELETE /models/{name}
POST   /models/{name}/predict
POST   /models/{name}/detect
```

`load` và `delete` cần admin.

---

## 11. Dữ Liệu Runtime

Các dữ liệu quan trọng trong `server/data/`:

| Đường dẫn | Nội dung |
|---|---|
| `device_registry.json` | Map `machine_hash -> device_code` |
| `camera_params/` | Camera calibration YAML |
| `uploads/pose_init/` | Ảnh stereo left/right Pi upload |
| `uploads/golden_poses/{artifact_id}/` | Golden pose per artifact |
| `uploads/artifacts/{artifact_id}/` | Reference/inspection images |
| `logs/mqtt_events.jsonl` | MQTT publish/status/ack events |
| `logs/inspections_log.jsonl` | Log inspection upload |

PostgreSQL lưu trong Docker volume `postgres_data`. Nếu chạy `docker compose down` không có `-v`, DB vẫn còn. Nếu chạy `docker compose down -v`, DB sẽ bị xóa.

---

## 12. Kiểm Tra Và Gỡ Lỗi

### 12.1. Server

```bash
cd /home/thepiece/System/Artifact-Pose-System/server
docker compose --env-file .env.docker ps
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/mqtt/health
docker compose --env-file .env.docker logs --tail=100 server
```

### 12.2. Auth

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

Nếu user bị inactive, login trả `403`.

### 12.3. Device Registry Và DB

```bash
cat server/data/device_registry.json

docker exec -it artifact_postgres psql -U artifact -d artifact_auth \
  -c "SELECT device_id, device_code, status, last_active_at FROM iot_devices;"
```

### 12.4. MQTT

```bash
docker exec -it artifact_mosquitto mosquitto_sub -h localhost -t "#" -v
```

Gửi lệnh test nhỏ:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/devices/dev-bbb742d369/queue_move \
  -H "Content-Type: application/json" \
  -d '{"action":"move","yaw_delta":1.0,"pitch_delta":0.0,"x_steps":0,"z_steps":0,"x_dir":1,"z_dir":1}'
```

### 12.5. Flutter

```bash
cd client/artifact_app
flutter pub get
flutter analyze
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Ghi chú: analyzer hiện còn các warning/info cũ như `withOpacity` deprecated, `use_build_context_synchronously`, unused imports. Đây là vấn đề cleanup frontend, không phải lỗi deploy chính.

### 12.6. Pose

Kiểm tra pose health:

```bash
TOKEN="<access_token>"

curl http://127.0.0.1:8000/pose/health \
  -H "Authorization: Bearer $TOKEN"
```

Kiểm tra artifact đã có golden pose:

```bash
curl http://127.0.0.1:8000/pose/golden-pose/<artifact_id>/status \
  -H "Authorization: Bearer $TOKEN"
```

---

## 13. Bảo Trì Thường Gặp

### Thay model AI

```bash
cp /path/to/new-model.pt model/
cd server
docker compose --env-file .env.docker restart server
```

### Tạo/cập nhật admin

```bash
cd server
docker compose --env-file .env.docker exec server \
  python tools/create_admin.py --username admin --password 123456 --role admin
```

### Liệt kê user

```bash
cd server
docker compose --env-file .env.docker exec server python tools/list_users.py
```

### Xóa ảnh stereo test cũ

```bash
rm -f server/data/uploads/pose_init/*.png
```

### Xóa golden pose của một artifact để khởi tạo lại

```bash
rm -rf server/data/uploads/golden_poses/<artifact_id>
```

Không xóa toàn bộ `server/data/uploads/artifacts/` nếu vẫn cần ảnh inspection/reference cũ.

---

## 14. Checklist Vận Hành

Trước khi demo hoặc chạy kiểm tra thật:

- Server Docker đang chạy.
- `/health` trả `status=ok`.
- `/mqtt/health` báo MQTT bridge connected.
- File model `.pt` nằm trong `model/`.
- Camera params lens `1.5` tồn tại.
- Pi agent đang chạy và online.
- App build đúng `API_BASE_URL`.
- User đăng nhập đang active.
- Artifact đã được tạo.
- Marker ChArUco đúng chuẩn và nằm trong khung hình.
- Baseline vật lý của slider đúng 10cm cho 80000 steps.
- Device workflow dùng `device_code`, ví dụ `dev-bbb742d369`.

---

## 15. Tóm Tắt Nhanh

```text
Server:
  cd server
  docker compose --env-file .env.docker up -d

Android USB:
  adb reverse tcp:8000 tcp:8000
  flutter build apk --release --dart-define=API_BASE_URL=http://127.0.0.1:8000

Pi:
  cd embed/device_agent
  PYTHONPATH=. python3 runtime/main_app.py

Admin mặc định dev:
  admin / 123456

Device hiện tại:
  dev-bbb742d369

Baseline stereo:
  100mm cố định, 80000 steps, không chỉnh từ UI/API
```
