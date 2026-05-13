# Hướng dẫn Deploy & Test — USB (adb reverse) hoặc WiFi LAN

**Mục tiêu:** Chạy server Docker trên máy tính, kết nối app Flutter trên điện thoại Android tới server — qua dây USB (dùng `adb reverse`) **hoặc** qua WiFi LAN.

---

## Chọn phương thức kết nối

| Phương thức | Điều kiện | Lệnh build app |
|---|---|---|
| **USB + adb reverse** | Cắm dây USB, bật USB Debugging | `--dart-define=API_BASE_URL=http://127.0.0.1:8000` |
| **WiFi LAN** | PC và điện thoại cùng mạng WiFi | `--dart-define=API_BASE_URL=http://<IP_PC>:8000` |

> **Quan trọng về 127.0.0.1:** Khi dùng `adb reverse tcp:8000 tcp:8000`, lệnh này tạo một **tunnel từ điện thoại lên máy tính**. Lúc này `127.0.0.1:8000` trên điện thoại **không phải** điện thoại — mà thực sự đi đến `127.0.0.1:8000` trên **máy tính**. Nếu không có `adb reverse` chạy trước, app sẽ không kết nối được server.

---

## Kiến trúc khi dùng USB (adb reverse)

```
┌──────────────────────────────┐
│       MÁY TÍNH (PC/Laptop)   │
│                              │
│  Docker: FastAPI :8000       │
│  Docker: PostgreSQL :5432    │
│  Docker: MQTT :1883          │
│                              │
│  adb reverse tcp:8000 tcp:8000│
└──────────────┬───────────────┘
               │ Cáp USB
┌──────────────▼───────────────┐
│     ĐIỆN THOẠI ANDROID       │
│                              │
│  Flutter App                 │
│  → gọi http://127.0.0.1:8000 │
│    tunnel qua USB đến PC     │
└──────────────────────────────┘
```

---

## Kiến trúc khi dùng WiFi LAN

```
┌──────────────────────────────┐
│  MÁY TÍNH (IP: 192.168.x.y)  │
│  Docker: FastAPI :8000       │
│  Firewall: mở port 8000      │
└──────────────┬───────────────┘
               │ WiFi Router
┌──────────────▼───────────────┐
│  ĐIỆN THOẠI ANDROID          │
│  Flutter App                 │
│  → http://192.168.x.y:8000   │
└──────────────────────────────┘
```

---

## Cấu hình IP trong app

File: `client/artifact_app/lib/services/api_config.dart`

```dart
// Thay đổi IP này thành IP LAN thực tế của máy tính bạn
static const String _pcIp = '192.168.1.169';
```

- Nếu dùng **WiFi LAN**: sửa `_pcIp` thành IP WiFi của PC (xem bằng `ip addr` / `ipconfig`)
- Nếu dùng **USB adb reverse**: truyền `--dart-define=API_BASE_URL=http://127.0.0.1:8000` khi build/run

---

## Yêu cầu cài đặt trên máy tính

| Phần mềm | Kiểm tra |
|---|---|
| Docker + Docker Compose | `docker --version` |
| Flutter SDK ≥ 3.7 | `flutter --version` |
| Android SDK / ADB | `adb --version` |

---

## Bước 1 — Bật Developer Options trên điện thoại (chỉ cho USB)

1. Vào **Cài đặt → Giới thiệu điện thoại**
2. Nhấn **Số phiên bản** (Build number) **7 lần liên tiếp** → bật chế độ nhà phát triển
3. Vào **Cài đặt → Tùy chọn nhà phát triển**
4. Bật **USB Debugging** (Gỡ lỗi USB)
5. Cắm dây USB vào máy tính → điện thoại hiện hộp thoại, chọn **Cho phép**

```bash
adb devices
# Kết quả: trạng thái "device", không phải "unauthorized"
```

---
### Lưu ý: Khi bạn thay model .pt mới, chạy lại:
docker cp /path/to/new-model.pt artifact_server:/app/model/
docker restart artifact_server



## Bước 2 — Khởi động Server (Docker)

```bash
cd /home/thepiece/System/Artifact-Pose-System/server
```

### Lần đầu (build image):
```bash
docker compose --env-file .env.docker up -d --build
```

### Các lần sau:
```bash
docker compose --env-file .env.docker up -d
```

### Kiểm tra server OK:
```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}
```

### Kiểm tra tài khoản admin:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

### (Nếu dùng WiFi) Mở port 8000 trên firewall:
```bash
# Linux (UFW)
sudo ufw allow 8000/tcp

# Kiểm tra IP PC để cấu hình cho app
ip -4 addr show | grep -oP '(?<=inet )192\.[0-9.]+'
```

---

## Bước 3 — Thiết lập adb reverse (chỉ cho USB)

### Cách tự động (khuyên dùng)

Mỗi lần cắm lại USB, chỉ cần chạy **một lệnh duy nhất** từ Windows PowerShell:

```powershell
cd \\wsl.localhost\Ubuntu-22.04\home\thepiece\System\Artifact-Pose-System

powershell -ExecutionPolicy Bypass -File scripts\attach_android_usb.ps1
```

Script sẽ tự:
1. Tìm điện thoại Android trong danh sách usbipd (theo VID hoặc tên)
2. `usbipd bind` + `usbipd attach --wsl`
3. Chạy `adb reverse tcp:8000 tcp:8000` trong WSL

> Lần đầu chạy sẽ hiện UAC prompt (cần Admin cho bước `bind`). Các lần sau không cần.

Hoặc nếu USB đã attach rồi, chỉ cần chạy trong WSL:

```bash
./scripts/wsl_adb_setup.sh
```

---

### Cách thủ công (nếu script không chạy được)

```powershell
# 1. Tìm BUSID của điện thoại
usbipd list

# 2. Bind (cần Admin, chỉ cần 1 lần cho mỗi thiết bị)
usbipd bind --busid 1-4

# 3. Attach vào WSL
usbipd attach --wsl --busid 1-4
```

Sau đó trong WSL:
```bash
adb devices
adb reverse tcp:8000 tcp:8000
```

---

> ⚠️ **Phải chạy lại sau mỗi lần:**
> - Cắm lại dây USB
> - Khởi động lại điện thoại
> - `adb kill-server` / `adb start-server`

Kiểm tra tunnel còn hoạt động:
```bash
adb reverse --list
# → 8000 tcp:8000  (tunnel đang active)
```

---

## Bước 4 — Build & Deploy Flutter App

```bash
cd /home/thepiece/System/Artifact-Pose-System/client/artifact_app
flutter pub get
```

### Cách A: USB + adb reverse (127.0.0.1)

```bash
# Debug mode (nhanh, dùng để test)
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000

rm -rf .dart_tool
rm -rf build
flutter clean
flutter pub get

# Release APK (cài thủ công)
flutter build apk --release --dart-define=API_BASE_URL=http://127.0.0.1:8000
adb install build/app/outputs/flutter-apk/app-release.apk

adb install -r build/app/outputs/flutter-apk/app-release.apk cài đè
//cài lại
adb uninstall com.pbl5.artifactapp
adb install build/app/outputs/flutter-apk/app-release.apk
```

### Cách B: WiFi LAN (thay IP thực tế của PC)

```bash
# Xem IP WiFi của PC
ip -4 addr show | grep -oP '(?<=inet )192\.[0-9.]+'

# Debug mode
flutter run --dart-define=API_BASE_URL=http://192.168.x.y:8000

# Release APK
flutter build apk --release --dart-define=API_BASE_URL=http://192.168.x.y:8000
adb install build/app/outputs/flutter-apk/app-release.apk
```

> Hoặc sửa `_pcIp` trong `api_config.dart` thành IP thực và build không cần `--dart-define`.

---

## Bước 5 — Kiểm tra thiết bị IoT (Raspberry Pi) đã đăng ký

Raspberry Pi tự đăng ký khi khởi động bằng cách gọi `POST /api/v1/devices/get_device_id`. Thiết bị `dev-bbb742d369` đã được đăng ký sẵn trong DB.

Kiểm tra:
```bash
docker exec artifact_postgres psql -U artifact -d artifact_auth \
  -c "SELECT device_id, device_code, status FROM iot_devices;"
```

Kết quả mong đợi:
```
 device_id |  device_code   | status
-----------+----------------+---------
 bbb742    | dev-bbb742d369 | offline
```

Khi Pi kết nối và gửi tín hiệu MQTT, status tự chuyển thành `online`.

---

## Bước 6 — Test trên giao diện app

### Tài khoản mặc định

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `123456` |

---

### 6.1 Đăng nhập

1. Mở app → màn hình **Đăng nhập**
2. Nhập `admin` / `123456` → **Đăng nhập**
3. ✅ Chuyển vào **Admin Dashboard**

---

### 6.2 Quản lý Hiện vật (Artifacts)

1. Vào tab **Hiện vật**
2. Nhấn **+** → điền Tên, Mô tả, Địa điểm → **Lưu**
3. ✅ Hiện vật xuất hiện trong danh sách

**Chi tiết hiện vật:**
- Nhấn vào hiện vật → xem thông tin và lịch sử kiểm tra
- Nhấn **Kiểm tra qua thiết bị IoT** để bắt đầu quy trình IoT 3 bước

---

### 6.3 Quy trình Kiểm tra IoT (3 bước)

Truy cập bằng 2 cách:
- Tab **Thiết bị** → chọn thiết bị → màn hình workflow
- Chi tiết hiện vật → **Kiểm tra qua thiết bị IoT**

#### Bước 1 — Khởi tạo Golden Pose
1. Chọn thiết bị `dev-bbb742d369` từ dropdown (nếu chưa chọn sẵn)
2. Chọn hiện vật cần kiểm tra
3. Nhập **Baseline (mm)** — khoảng cách giữa 2 camera stereo (mặc định: 100mm)
4. Nhấn **Bắt đầu Khởi tạo**
5. ✅ Raspberry Pi nhận lệnh qua MQTT, chụp ảnh stereo, lưu golden pose

#### Bước 2 — Căn chỉnh tư thế
1. Nhấn **Bắt đầu Căn chỉnh**
2. Pi bắt đầu vòng lặp chụp-tính-điều chỉnh
3. App tự refresh log ACK mỗi 3 giây để hiển thị kết quả từng bước
4. Khi tư thế đã khớp với golden pose → nhấn **Căn chỉnh xong**

#### Bước 3 — AI Kiểm tra hư hại
1. Nhấn **Kiểm tra AI**
2. Server dùng ảnh đã chụp từ Pi (không cần upload từ điện thoại)
3. ✅ Kết quả: điểm hư hại (0–10), trạng thái (good/warning/damaged), SSIM
4. Nhấn **Xem kết quả** để xem chi tiết

---

### 6.4 Quản lý Thiết bị (Devices)

- Vào tab **Thiết bị** → danh sách thiết bị đã đăng ký trong DB
- Nhấn vào thiết bị → màn hình workflow 3 bước
- Nhấn icon **ℹ️** → thông tin thiết bị và lịch sử ACK

> **Lưu ý:** Thiết bị tự đăng ký qua API khi Pi khởi động. App không có chức năng thêm/xóa thiết bị thủ công.

---

### 6.5 Quản lý Lịch kiểm tra (Schedules)

1. Vào tab **Lịch** → nhấn **+** → chọn hiện vật, ngày, giờ, operator → **Lưu**

---

### 6.6 Quản lý Người dùng (Users) — Admin

1. Vào **Admin Dashboard → Người dùng**
2. Nhấn **+** → điền username, password, full name, role: `operator`
3. Nhấn **Lưu**

---

## Bước 7 — Test API bằng Swagger UI

Mở trình duyệt trên máy tính:
```
http://127.0.0.1:8000/docs
```

| Nhóm | Endpoint quan trọng |
|---|---|
| Auth | `POST /api/v1/auth/login` |
| Devices | `GET /api/v1/devices` — danh sách thiết bị |
| Devices | `GET /api/v1/devices/{id}/acks` — lịch sử ACK |
| Workflows | `POST /workflows/{device_code}/start-initialization` |
| Workflows | `POST /workflows/{device_code}/start-alignment` |
| Artifacts | `POST /api/v1/artifacts/{id}/inspect-from-device` |

> **Lưu ý:** Các endpoint workflow dùng `device_code` (như `dev-bbb742d369`) làm path param, không phải `device_id` (6-char hex).

---

## Xử lý sự cố

### App không kết nối được server

```bash
# 1. Kiểm tra server đang chạy
curl http://127.0.0.1:8000/health

# 2. Kiểm tra tunnel USB còn active (chế độ adb reverse)
adb reverse --list
# Nếu không thấy tcp:8000:
adb reverse tcp:8000 tcp:8000

# 3. Chế độ WiFi: kiểm tra IP PC có đúng không
ip -4 addr show | grep inet
# Rebuild với IP mới nếu thay đổi
```

### Điện thoại hiện `unauthorized`

```bash
adb kill-server && adb start-server && adb devices
# Mở khóa điện thoại → chấp nhận hộp thoại USB Debugging
```

### Server lỗi khi khởi động

```bash
cd server
docker compose --env-file .env.docker logs server
docker compose --env-file .env.docker down
docker compose --env-file .env.docker up -d --build
```

### Thiết bị IoT không nhận lệnh

```bash
# Kiểm tra device đã có trong DB
docker exec artifact_postgres psql -U artifact -d artifact_auth \
  -c "SELECT device_id, device_code, status FROM iot_devices;"

# Kiểm tra MQTT kết nối
docker logs artifact_mosquitto

# Kiểm tra MQTT bridge trong server logs
cd server && docker compose --env-file .env.docker logs server | grep -i mqtt
```

### Reset toàn bộ database

```bash
cd server
docker compose --env-file .env.docker down -v   # ⚠️ xóa toàn bộ dữ liệu
docker compose --env-file .env.docker up -d --build
# Sau đó tạo lại admin:
docker exec -it artifact_server python tools/create_admin.py
# Và insert lại device:
docker exec artifact_postgres psql -U artifact -d artifact_auth \
  -c "INSERT INTO iot_devices VALUES ('bbb742','dev-bbb742d369','Raspberry Pi Camera','offline',NOW()) ON CONFLICT DO NOTHING;"
```

### Flutter build lỗi

```bash
cd client/artifact_app
flutter clean && flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

---

## Tóm tắt lệnh nhanh (chạy mỗi phiên làm việc)

```powershell
# === Windows PowerShell: attach USB + adb reverse (1 lệnh duy nhất) ===
powershell -ExecutionPolicy Bypass -File scripts\attach_android_usb.ps1
```

```bash
# === WSL Terminal 1: Khởi động server ===
cd /home/thepiece/System/Artifact-Pose-System/server
docker compose --env-file .env.docker up -d
curl http://127.0.0.1:8000/health     # xác nhận OK

# === WSL Terminal 2: Chạy app Flutter (USB mode) ===
cd /home/thepiece/System/Artifact-Pose-System/client/artifact_app
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000

# === Hoặc: WiFi mode (thay IP thực tế của PC) ===
flutter run --dart-define=API_BASE_URL=http://192.168.x.y:8000
```




## Trên server:

docker compose logs -f server


## Trên Pi:
cd embed/device_agent

PYTHONPATH=. python3 runtime/main_app.py

## Show màn hình điện thoại:
scrcpy

## Trên WSL - init:
curl -X POST http://localhost:8000/workflows/dev-bbb742d369/start-initialization \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"artifact_demo_001","baseline_mm":100.0,"steps_per_mm":860.0}'

## Dịch vật thể:
curl -X POST http://localhost:8000/workflows/dev-bbb742d369/start-alignment \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"artifact_demo_001"}'