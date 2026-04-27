# Hướng Dẫn Sử Dụng Hệ Thống Artifact Pose System

> Phiên bản: 1.0 — Cập nhật: 27/04/2026

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Yêu cầu phần cứng và phần mềm](#2-yêu-cầu-phần-cứng-và-phần-mềm)
3. [Cấu hình mạng](#3-cấu-hình-mạng)
4. [Khởi động Server (PC/WSL2)](#4-khởi-động-server-pcwsl2)
5. [Cấu hình Raspberry Pi](#5-cấu-hình-raspberry-pi)
6. [Cài đặt App Mobile](#6-cài-đặt-app-mobile)
7. [Tài khoản người dùng](#7-tài-khoản-người-dùng)
8. [Quy trình sử dụng đầu đến cuối](#8-quy-trình-sử-dụng-đầu-đến-cuối)
9. [Marker ChArUco — Yêu cầu vật lý](#9-marker-charuco--yêu-cầu-vật-lý)
10. [Chi tiết chức năng app](#10-chi-tiết-chức-năng-app)
11. [Kiểm tra và gỡ lỗi](#11-kiểm-tra-và-gỡ-lỗi)
12. [Cấu trúc file quan trọng](#12-cấu-trúc-file-quan-trọng)

---

## 1. Tổng quan hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                      PC (Windows + WSL2)                    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Docker Compose                                       │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │  PostgreSQL  │  │   FastAPI    │  │  Mosquitto  │ │   │
│  │  │  :5432       │  │   :8000      │  │  MQTT :1883 │ │   │
│  │  └─────────────┘  └──────────────┘  └─────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  WiFi Home: 192.168.0.102    Hotspot: 192.168.137.1         │
└─────────────────────────────────────────────────────────────┘
         │ WiFi Home (192.168.0.x)        │ PC Hotspot
         ▼                                ▼
┌─────────────────┐              ┌─────────────────────┐
│  Mobile Phone   │              │   Raspberry Pi      │
│  Android App    │              │   device_agent      │
│  192.168.0.100  │              │   → :8000 và :1883  │
└─────────────────┘              └─────────────────────┘
```

**Luồng hoạt động:**
1. App Mobile gửi lệnh workflow đến Server qua REST API
2. Server publish lệnh qua MQTT → Raspberry Pi nhận
3. Pi chụp ảnh và upload lên Server
4. Server xử lý pose + AI detection → trả kết quả về app

---

## 2. Yêu cầu phần cứng và phần mềm

### PC (máy chủ)
- Windows 10/11 với WSL2 (Ubuntu 22.04)
- Docker Desktop (v24+)
- Python 3.10+ (trong WSL2)
- ADB (Android Debug Bridge) để cài app

### Raspberry Pi
- Raspberry Pi 4B trở lên
- Camera module (Pi Camera v2 hoặc HQ Camera)
- Slider cơ (stepper motor + driver)
- Servo pan/tilt
- Python 3.10+
- Thư viện: `paho-mqtt`, `requests`, `picamera2`

### Điện thoại Android
- Android 8.0 trở lên
- Cùng mạng WiFi gia đình với PC
- (Không cần cùng mạng với Pi)

### Phần mềm
- Flutter SDK 3.29.3+
- Docker Compose v2

---

## 3. Cấu hình mạng

### Bảng IP

| Thiết bị | Mạng | IP | Kết nối tới |
|---|---|---|---|
| PC — WiFi Home | Home WiFi | `192.168.0.102` | Mobile → Server |
| PC — Hotspot | PC Mobile Hotspot | `192.168.137.1` | Pi → Server + MQTT |
| Raspberry Pi | PC Hotspot | `192.168.137.x` | `192.168.137.1:8000` |
| Mobile Phone | Home WiFi | `192.168.0.100` | `192.168.0.102:8000` |
| Docker (WSL2) | Internal | `0.0.0.0:8000` | Lắng nghe tất cả |

### Kiểm tra IP PC

```bash
# Trên WSL2 / Terminal
cmd.exe /c "ipconfig" | grep "IPv4" | grep -v "169.254"
```

Kết quả mong đợi:
```
IPv4 Address: 192.168.0.102    ← WiFi Home (mobile dùng cái này)
IPv4 Address: 192.168.137.1   ← Hotspot (Pi dùng cái này)
```

> ⚠️ **Lưu ý:** Nếu IP WiFi Home của PC thay đổi, cần rebuild lại APK với IP mới.

---

## 4. Khởi động Server (PC/WSL2)

### Lần đầu tiên (setup)

```bash
cd ~/System/Artifact-Pose-System/server

# 1. Copy file env mẫu
cp env.docker.example .env

# 2. (Tùy chọn) Sửa mật khẩu trong .env
# ADMIN_USERNAME=admin
# ADMIN_PASSWORD=123456

# 3. Build và khởi động
docker compose build
docker compose up -d
```

### Các lần sau (start bình thường)

```bash
cd ~/System/Artifact-Pose-System/server
docker compose up -d
```

### Kiểm tra server đang chạy

```bash
# Kiểm tra containers
docker compose ps

# Kiểm tra health endpoint
curl http://localhost:8000/health

# Kiểm tra MQTT kết nối
curl http://localhost:8000/mqtt/health
```

Kết quả mong đợi:
```json
{"status": "ok", "mqtt_connected": true, "ai_model_loaded": true}
```

### Dừng server

```bash
docker compose down
```

### Xem logs

```bash
# Xem logs real-time
docker compose logs -f server

# Xem 50 dòng cuối
docker compose logs --tail=50 server
```

---

## 5. Cấu hình Raspberry Pi

### File cấu hình: `embed/device_agent/.env`

```env
# Kết nối server qua PC Hotspot
SERVER_BASE_URL=http://192.168.137.1:8000

# MQTT qua PC Hotspot
MQTT_HOST=192.168.137.1
MQTT_PORT=1883

# Device ID (để trống → tự đăng ký với server)
DEVICE_ID=
USE_SERVER_DEVICE_ID=true

# Artifact mặc định
DEFAULT_ARTIFACT_ID=artifact_demo_001

# Camera
LENS_POSITION=1.5

# Lưu ảnh
IMAGE_DIR=./data/pictures
```

### Chạy device agent trên Pi

```bash
cd embed/device_agent
PYTHONPATH=. python3 runtime/main_app.py

```

### Kiểm tra Pi đã kết nối

Khi Pi khởi động thành công, terminal hiển thị:
```
[MQTT] Connected to 192.168.137.1:1883
[APP] Device ID: dev-bbb742d369
[APP] Listening for commands on: cmd/dev-bbb742d369
```

---

## 6. Cài đặt App Mobile

### Yêu cầu trước khi build

- Flutter SDK 3.29.3+
- ADB kết nối với điện thoại qua WiFi:
  ```bash
  adb connect 192.168.0.100:5555
  adb devices  # xác nhận thấy device
  ```

### Build và cài APK

```bash
cd ~/System/Artifact-Pose-System/client/artifact_app

# Build APK với IP server
flutter build apk --release \
  --dart-define=API_BASE_URL=http://192.168.0.102:8000 \
  -t lib/main.dart

# Cài lên điện thoại
adb -s 192.168.0.100:5555 install -r \
  build/app/outputs/flutter-apk/app-release.apk
```

> ⚠️ **Thay `192.168.0.102`** bằng IP WiFi Home thực tế của PC nếu khác.

### Chạy trực tiếp (debug mode)

```bash
flutter run -d 192.168.0.100:5555 \
  --dart-define=API_BASE_URL=http://192.168.0.102:8000
```

---

## 7. Tài khoản người dùng

| Tài khoản | Mật khẩu | Vai trò | Quyền |
|---|---|---|---|
| `admin` | `123456` | Admin | Toàn bộ + quản lý user |
| `operator` | `operator123` | Operator | Dashboard, devices, artifacts |

### Đăng nhập

Mở app → nhập username/password → nhấn **Login**.

- **Admin** → vào **Admin Dashboard** (quản lý user, xem tất cả)
- **Operator** → vào **Operator Dashboard** (điều khiển thiết bị, kiểm tra hiện vật)

### Tạo thêm tài khoản (chỉ Admin)

Từ PC terminal:

```bash
# Lấy token admin
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Tạo tài khoản mới
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"operator2","password":"pass123","role":"operator"}'
```

---

## 8. Quy trình sử dụng đầu đến cuối

### Bước 0: Chuẩn bị

1. ✅ Server đang chạy trên PC (`docker compose up -d`)
2. ✅ Pi đang kết nối hotspot PC và chạy `device_agent`
3. ✅ App đã cài trên điện thoại, đăng nhập bằng `operator`

---

### Bước 1: Khởi tạo Golden Pose (Stereo Initialization)

> **Mục đích:** Dạy cho hệ thống biết "tư thế chuẩn" của hiện vật.

**Yêu cầu vật lý bắt buộc:**
- In marker ChArUco (xem [Mục 9](#9-marker-charuco--yêu-cầu-vật-lý))
- Đặt marker TRƯỚC hiện vật, trong tầm nhìn camera Pi

**Trên app:**
1. **Dashboard → Devices**
2. Xác nhận **Device ID**: `dev-bbb742d369`
3. Xác nhận **Artifact ID**: `artifact_demo_001`
4. Đặt **Baseline (mm)**: `100` (khoảng cách slider di chuyển)
5. Nhấn **Start Stereo Initialization**
6. Chờ Pi di chuyển slider, chụp 2 ảnh (LEFT + RIGHT), upload lên server
7. Server xử lý → tạo file `golden_pose.yaml`
8. Kết quả hiển thị: ✓ Command sent

**Điều gì xảy ra phía sau:**
```
App → POST /workflows/{device_id}/start-initialization
Server → MQTT publish: action=capture_stereo_pair
Pi nhận → chụp ảnh LEFT → di chuyển slider 100mm → chụp ảnh RIGHT
Pi → POST /pose/initialize_golden (upload 2 ảnh)
Server → detect_diamond() + ORB matching + triangulate → lưu golden_pose.yaml
```

> ⚠️ **Lỗi 400?** Xem [Mục 9](#9-marker-charuco--yêu-cầu-vật-lý) — marker không được phát hiện trong ảnh.

---

### Bước 2: Căn chỉnh tư thế (Alignment)

> **Mục đích:** Tự động căn chỉnh Pi đến vị trí chuẩn so với golden pose.

**Điều kiện:** Bước 1 đã hoàn thành (có file `golden_pose.yaml`).

**Trên app:**
1. **Dashboard → Devices**
2. Nhấn **Start Alignment**
3. Hệ thống tự động lặp: chụp ảnh → tính độ lệch → gửi lệnh điều chỉnh motor
4. Khi `within_tolerance = true` → dừng vòng lặp, AI chạy tự động

**Điều gì xảy ra:**
```
App → POST /workflows/{device_id}/start-alignment
Server → MQTT: action=capture (auto_alignment_loop=true)
Pi → chụp ảnh → POST /inspections/upload
Server → pose_correction() → tính deviation
  Nếu ngoài dung sai: MQTT → Pi điều chỉnh motor → lặp lại
  Nếu trong dung sai: AI chạy → lưu kết quả
```

---

### Bước 3: Xem kết quả kiểm tra

**Trên app:**
1. **Dashboard → Artifacts**
2. Chọn hiện vật (vd: `artifact_demo_001`)
3. Nhấn **Inspect** để xem kết quả mới nhất
4. Xem: ảnh chụp, heatmap hư hỏng (nếu AI phát hiện), điểm số

---

### Bước 4: Chụp ảnh thủ công (tùy chọn)

**Trên app:**
1. **Dashboard → Devices → Request Capture**
2. Hoặc: **Artifacts → chọn hiện vật → Capture**

---

### Bước 5: Xem cảnh báo

- **Dashboard → Alerts**: Danh sách hiện vật có vấn đề phát hiện
- Badge số đỏ hiển thị số cảnh báo hiện tại

---

## 9. Marker ChArUco — Yêu cầu vật lý

### Tại sao cần marker?

Hệ thống dùng **ChArUco Diamond Board** để:
- Xác định vị trí 3D chính xác của camera so với vật thể
- Tính toán tư thế chuẩn (golden pose)

### Thông số marker

| Tham số | Giá trị |
|---|---|
| Dictionary | `DICT_4X4_50` (ArUco 4×4) |
| Board | 3×3 ChArUco |
| Kích thước ô vuông | **40mm** |
| Kích thước marker | **25mm** |
| Kích thước tổng | ~120mm × 120mm |

### File marker sẵn có

File đã tạo sẵn: `server/data/diamond_marker_print.png`

### Cách in

1. Mở file `diamond_marker_print.png`
2. In trên giấy trắng, **đảm bảo kích thước thực là 120mm × 120mm**
   - Trong phần mềm in, bỏ chọn "Fit to page" / "Scale to fit"
   - Đặt tỉ lệ 100%
3. Dán lên bìa cứng phẳng (không bị cong)
4. Đo lại: mỗi ô vuông phải đúng **40mm**

### Vị trí đặt marker

```
┌──────────────────────────────────────┐
│                                      │
│      [HIỆN VẬT]                      │
│                                      │
│  ┌────────────┐                      │
│  │  MARKER   │  ← đặt phẳng,        │
│  │ (120×120) │    nhìn thấy rõ      │
│  └────────────┘    từ camera         │
│                                      │
│                  [Pi Camera] ────►   │
└──────────────────────────────────────┘
```

- Marker phải nằm trong tầm nhìn camera
- Ánh sáng đủ, không bị lóa/tối
- Marker không bị che khuất, không bị cong

---

## 10. Chi tiết chức năng app

### Operator Dashboard

| Nút | Màn hình | Chức năng |
|---|---|---|
| Schedule | ScheduleScreen | Xem/tạo lịch kiểm tra định kỳ |
| Artifacts | ArtifactListScreen | Danh sách hiện vật, chụp ảnh, lịch sử |
| Alerts | AlertScreen | Hiện vật có cảnh báo hư hỏng |
| Devices | DeviceControlScreen | Điều khiển Pi, gửi lệnh workflow |

### Admin Dashboard

- Quản lý tài khoản người dùng (thêm/xóa)
- Xem tổng quan hệ thống

### DeviceControlScreen (Devices)

```
┌─────────────────────────────────────────┐
│ [MQTT: ● connected]                     │
│                                         │
│ Device ID:    [dev-bbb742d369        ]  │
│ Artifact ID:  [artifact_demo_001     ]  │
│ Baseline(mm): [100                   ]  │
│                                         │
│ [🔲 Start Stereo Initialization      ]  │
│    Pi chụp cặp ảnh stereo → golden pose │
│                                         │
│ [⚡ Start Alignment                   ]  │
│    Bắt đầu vòng căn chỉnh tự động      │
│                                         │
│ [📷 Request Capture                   ]  │
│    Chụp ảnh alignment đơn lẻ            │
│                                         │
│ [ℹ️ Check Device Status               ]  │
│    Xem trạng thái Pi                    │
└─────────────────────────────────────────┘
```

---

## 11. Kiểm tra và gỡ lỗi

### App không kết nối được server

```bash
# Kiểm tra server đang chạy
curl http://localhost:8000/health

# Kiểm tra từ điện thoại — mở browser trên phone, vào:
http://192.168.0.102:8000/health

# Nếu không vào được:
# 1. Kiểm tra Windows Firewall có chặn port 8000 không
# 2. Kiểm tra IP PC: cmd.exe /c ipconfig
# 3. Rebuild APK với đúng IP
```

### Pi không nhận lệnh (MQTT disconnected)

```bash
# Kiểm tra MQTT health
curl http://localhost:8000/mqtt/health

# Nếu mqtt_connected = false:
docker compose logs --tail=30 server | grep -i mqtt
docker compose restart server

# Kiểm tra Pi có kết nối không:
# Xem log trên Pi terminal
```

### Lỗi 400 khi Stereo Initialization

Nguyên nhân: `detect_diamond` không tìm thấy marker trong ảnh.

Kiểm tra:
1. ✅ Marker đã được in đúng kích thước (120×120mm)?
2. ✅ Marker nằm trong khung hình camera?
3. ✅ Ánh sáng đủ, không bị lóa?
4. ✅ Marker phẳng, không bị cong?
5. ✅ Pi đã chụp ảnh thành công (kiểm tra `server/data/uploads/pose_init/`)?

```bash
# Kiểm tra ảnh đã upload
ls server/data/uploads/pose_init/

# Xem log server
docker compose logs --tail=50 server | grep -E "400|initialize|diamond"
```

### Kiểm tra ảnh stereo thủ công

```bash
docker exec artifact_server bash -c "
python3 -c \"
from pathlib import Path
import cv2
from app.modules.artifact_pose.common import load_camera_params
from app.modules.artifact_pose.initialize import run_initialization
from app.core.config import get_settings
import sys; sys.path.insert(0, '/app')

s = get_settings()
K, D = load_camera_params(s.artifact_camera_params)
d = Path('/app/data/uploads/pose_init')
left = sorted(d.glob('*left*.png'))[-1]
right = sorted(d.glob('*right*.png'))[-1]
img_l = cv2.imread(str(left))
img_r = cv2.imread(str(right))
print('Left:', img_l.shape, '  Right:', img_r.shape)

# Test detect diamond
from app.modules.artifact_pose.common import detect_diamond
result = detect_diamond(img_l, K, D)
print('Diamond detected:', result is not None)
\""
```

### Pi offline / không phản hồi

```bash
# Kiểm tra device registry
cat server/data/device_registry.json

# Ping Pi (nếu biết IP)
ping 192.168.137.x

# Kiểm tra MQTT topic qua mosquitto sub
docker exec artifact_mosquitto mosquitto_sub -h localhost -t "status/#" -v
```

### Reset toàn bộ data (cẩn thận)

```bash
# Xóa golden pose (để init lại)
rm server/data/golden_pose.yaml

# Xóa ảnh stereo cũ
rm -f server/data/uploads/pose_init/*.png

# Restart server
docker compose restart server
```

---

## 12. Cấu trúc file quan trọng

```
Artifact-Pose-System/
│
├── server/                          # FastAPI server
│   ├── docker-compose.yml           # ← Cấu hình Docker
│   ├── env.docker.example           # ← Mẫu file .env
│   ├── .env                         # ← File env thực tế (tạo từ example)
│   ├── data/
│   │   ├── device_registry.json     # ← Danh sách device đã đăng ký
│   │   ├── golden_pose.yaml         # ← Golden pose (tạo sau Stereo Init)
│   │   ├── diamond_marker_print.png # ← Marker để in
│   │   ├── camera_params/
│   │   │   └── camera_params_lens_1.5.yaml  # ← Thông số camera Pi
│   │   └── uploads/
│   │       ├── pose_init/           # ← Ảnh stereo upload từ Pi
│   │       └── aligned/             # ← Ảnh khi căn chỉnh thành công
│   └── app/
│       └── modules/artifact_pose/
│           └── common.py            # ← Thông số marker (SQUARE=40mm, etc.)
│
├── embed/device_agent/              # Phần mềm chạy trên Pi
│   ├── .env                         # ← SERVER_BASE_URL, MQTT_HOST
│   ├── api_client.py                # ← HTTP client
│   └── runtime/
│       └── main_app.py              # ← Main loop + xử lý lệnh MQTT
│
├── client/artifact_app/             # Flutter mobile app
│   ├── lib/
│   │   ├── services/
│   │   │   └── api_config.dart      # ← baseUrl = 192.168.0.102:8000
│   │   └── screens/
│   │       ├── dashboard/           # Màn hình chính operator
│   │       ├── devices/             # ← DeviceControlScreen (mới)
│   │       ├── artifact/            # Quản lý hiện vật
│   │       ├── inspect/             # Xem kết quả
│   │       ├── schedule/            # Lịch kiểm tra
│   │       ├── alerts/              # Cảnh báo
│   │       └── admin/               # Quản lý user (admin only)
│   └── pubspec.yaml
│
└── model/
    └── best_83_7pt_train_2604_testch.pt  # ← AI model (YOLO damage detection)
```

---

## Tóm tắt nhanh (Quick Reference)

```bash
# Khởi động server
cd server && docker compose up -d

# Build + cài app (thay IP nếu cần)
cd client/artifact_app
flutter build apk --release --dart-define=API_BASE_URL=http://192.168.0.102:8000 -t lib/main.dart
adb -s 192.168.0.100:5555 install -r build/app/outputs/flutter-apk/app-release.apk

# Kiểm tra health
curl http://localhost:8000/health
curl http://localhost:8000/mqtt/health
```

```
Tài khoản:
  admin    / 123456       (Admin Dashboard)
  operator / operator123  (Operator Dashboard)

Device ID Pi: dev-bbb742d369
Artifact ID:  artifact_demo_001
Pi → Server:  http://192.168.137.1:8000
Phone → Server: http://192.168.0.102:8000
```
