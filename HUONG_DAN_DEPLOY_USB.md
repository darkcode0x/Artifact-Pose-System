# Hướng dẫn Deploy & Test qua USB (không cần WiFi)

**Mục tiêu:** Chạy server trên máy tính, cài app Flutter lên điện thoại Android qua dây USB, điện thoại gọi API server thông qua `adb reverse`.

---

## Kiến trúc khi dùng USB

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
│    (được forward qua USB)    │
└──────────────────────────────┘
```

**Nguyên lý:** `adb reverse` tạo một tunnel từ `127.0.0.1:8000` trên điện thoại → `127.0.0.1:8000` trên máy tính. App Flutter dùng `API_BASE_URL=http://127.0.0.1:8000` sẽ tự động đi qua USB.

---

## Yêu cầu cài đặt trên máy tính

| Phần mềm | Kiểm tra |
|---|---|
| Docker + Docker Compose | `docker --version` |
| Flutter SDK ≥ 3.7 | `flutter --version` |
| Android SDK / ADB | `adb --version` |

---

## Bước 1 — Bật Developer Options trên điện thoại

1. Vào **Cài đặt → Giới thiệu điện thoại**
2. Nhấn **Số phiên bản** (Build number) **7 lần liên tiếp** → bật chế độ nhà phát triển
3. Vào **Cài đặt → Tùy chọn nhà phát triển**
4. Bật **USB Debugging** (Gỡ lỗi USB)
5. Cắm dây USB vào máy tính → điện thoại hiện hộp thoại, chọn **Cho phép**

---

## Bước 2 — Kiểm tra kết nối USB

```bash
adb devices
```

Kết quả mong đợi (thiết bị phải ở trạng thái `device`, không phải `unauthorized`):

```
List of devices attached
XXXXXXXXXXXXXXXX    device
```

> Nếu hiện `unauthorized`: mở khóa điện thoại, chấp nhận lại hộp thoại USB Debugging.

---

## Bước 3 — Khởi động Server (Docker)

```bash
cd /home/thepiece/System/Artifact-Pose-System/server
```

### Lần đầu (build image):

```bash
docker compose --env-file .env.docker up -d --build
```

### Các lần sau (đã build rồi):

```bash
docker compose --env-file .env.docker up -d
```

### Kiểm tra server đang chạy:

```bash
# Health check
curl http://127.0.0.1:8000/health

# Xem logs server (Ctrl+C để thoát)
docker compose --env-file .env.docker logs -f server
```

Kết quả `curl` mong đợi:
```json
{"status":"ok"}
```

### Kiểm tra tài khoản admin đã được tạo:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

---

## Bước 4 — Thiết lập adb reverse (tunnel USB)

```bash
adb reverse tcp:8000 tcp:8000
```

> Lệnh này phải chạy **sau mỗi lần cắm lại USB** hoặc khởi động lại điện thoại.

Kiểm tra tunnel hoạt động từ điện thoại (tùy chọn — nếu có adb shell):

```bash
adb shell curl -s http://127.0.0.1:8000/health
```

---

## Bước 5 — Build & Deploy Flutter App lên điện thoại

```bash
cd /home/thepiece/System/Artifact-Pose-System/client/artifact_app
```

### Install dependencies:

```bash
flutter pub get
```

### Build và cài thẳng lên điện thoại (debug mode, nhanh):

```bash
flutter run \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000 \
  -d $(adb devices | grep -v "List" | grep "device" | awk '{print $1}')
```

Hoặc chỉ định thiết bị thủ công:

```bash
# Xem danh sách thiết bị
flutter devices

# Chạy lên thiết bị cụ thể (thay DEVICE_ID bằng ID từ lệnh trên)
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000 -d DEVICE_ID
```

> `--dart-define=API_BASE_URL=http://127.0.0.1:8000` — bắt buộc để app dùng địa chỉ USB tunnel thay vì IP cứng trong code.

### Build APK release (cài thủ công):

```bash
flutter build apk \
  --release \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000

# Cài APK lên điện thoại
adb install build/app/outputs/flutter-apk/app-release.apk
```

---

## Bước 6 — Test đầy đủ trên giao diện

### Tài khoản mặc định

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `123456` |

---

### 6.1 Đăng nhập

1. Mở app → màn hình **Đăng nhập**
2. Nhập `admin` / `123456`
3. Nhấn **Đăng nhập**
4. ✅ Thành công: chuyển vào **Admin Dashboard**

---

### 6.2 Quản lý Hiện vật (Artifacts)

**Tạo hiện vật mới:**
1. Vào tab **Hiện vật** (Artifacts)
2. Nhấn nút **+** (thêm mới)
3. Điền Tên, Mô tả, Địa điểm
4. Nhấn **Lưu**
5. ✅ Hiện vật xuất hiện trong danh sách

**Chỉnh sửa hiện vật:**
1. Nhấn vào hiện vật → màn hình chi tiết
2. Nhấn icon **Chỉnh sửa**
3. Sửa thông tin → **Lưu**

**Xóa hiện vật:**
1. Vào chi tiết hiện vật
2. Nhấn **Xóa** → xác nhận

---

### 6.3 Upload ảnh tham chiếu (Baseline Image)

1. Vào chi tiết hiện vật
2. Nhấn **Upload ảnh tham chiếu**
3. Chọn ảnh từ thư viện / camera
4. ✅ Ảnh hiển thị trong màn hình chi tiết

---

### 6.4 Thực hiện kiểm tra (Inspection)

1. Vào chi tiết hiện vật (đã có ảnh tham chiếu)
2. Nhấn **Kiểm tra ngay** (Sudden Inspection)
3. Chụp / chọn ảnh hiện tại của hiện vật
4. Chờ server xử lý AI
5. ✅ Kết quả hiển thị: điểm hư hại, trạng thái (good/warning/damaged), ảnh heatmap

---

### 6.5 Quản lý Lịch kiểm tra (Schedules)

**Tạo lịch:**
1. Vào tab **Lịch** (Schedule)
2. Nhấn **+** → chọn hiện vật, ngày, giờ, operator
3. Nhấn **Lưu**

**Xem lịch:**
- Danh sách sắp xếp theo ngày
- Lọc theo ngày cụ thể

---

### 6.6 Cảnh báo (Alerts)

1. Vào tab **Cảnh báo**
2. ✅ Hiển thị các hiện vật có trạng thái `warning` hoặc `damaged`

---

### 6.7 Quản lý Thiết bị (Devices) — Admin

1. Vào **Admin Dashboard → Thiết bị**
2. Nhấn **+** thêm thiết bị mới (device_code, mô tả)
3. Xem danh sách thiết bị và trạng thái
4. Xóa thiết bị nếu cần

---

### 6.8 Quản lý Người dùng (Users) — Admin

**Tạo operator mới:**
1. Vào **Admin Dashboard → Người dùng**
2. Nhấn **+** → điền username, password, full name
3. Chọn role: `operator`
4. Nhấn **Lưu**

**Chỉnh sửa user:**
- Nhấn vào user → sửa thông tin, đổi password

**Vô hiệu hóa / Kích hoạt:**
- Toggle Active/Inactive trên màn hình chi tiết

**Reset mật khẩu:**
- Admin có thể reset password về `111111`

---

### 6.9 Hồ sơ cá nhân (Profile)

1. Vào **Profile** (góc trên phải)
2. Chỉnh sửa: Full name, Email, Phone, Age
3. Đổi mật khẩu: tab **Đổi mật khẩu** → nhập mật khẩu cũ + mới

---

## Bước 7 — Test API trực tiếp bằng Swagger UI

Mở trình duyệt trên **máy tính**:

```
http://127.0.0.1:8000/docs
```

Các endpoint chính:

| Nhóm | Endpoint | Mô tả |
|---|---|---|
| Auth | `POST /api/v1/auth/login` | Đăng nhập |
| Auth | `POST /api/v1/auth/register` | Đăng ký (operator) |
| Users | `GET /api/v1/users` | Danh sách users (admin) |
| Users | `GET /api/v1/users/me` | Thông tin bản thân |
| Users | `PATCH /api/v1/users/me` | Cập nhật profile |
| Users | `POST /api/v1/users/me/change-password` | Đổi mật khẩu |
| Artifacts | `GET /api/v1/artifacts` | Danh sách hiện vật |
| Artifacts | `POST /api/v1/artifacts` | Tạo hiện vật |
| Artifacts | `GET /api/v1/artifacts/{id}` | Chi tiết hiện vật |
| Artifacts | `GET /api/v1/artifacts/{id}/inspections` | Lịch sử kiểm tra |
| Inspections | `POST /inspections/upload` | Upload ảnh kiểm tra |
| Schedules | `GET /api/v1/schedules` | Danh sách lịch |
| Schedules | `POST /api/v1/schedules` | Tạo lịch |
| Devices | `GET /api/v1/devices` | Danh sách thiết bị |
| Devices | `POST /api/v1/devices` | Tạo thiết bị |
| Health | `GET /health` | Kiểm tra server |

**Cách dùng Swagger với auth:**
1. Gọi `POST /api/v1/auth/login` → copy `access_token`
2. Nhấn nút **Authorize** (🔒) góc trên phải
3. Nhập `Bearer <access_token>`
4. Test các endpoint cần auth

---

## Xử lý sự cố

### App không kết nối được server

```bash
# 1. Kiểm tra server đang chạy
curl http://127.0.0.1:8000/health

# 2. Kiểm tra tunnel USB còn active
adb reverse --list

# 3. Nếu không thấy tcp:8000, thiết lập lại
adb reverse tcp:8000 tcp:8000
```

### Điện thoại hiện `unauthorized`

```bash
# Reset kết nối ADB
adb kill-server
adb start-server
adb devices
# → mở khóa điện thoại, chấp nhận hộp thoại USB Debugging
```

### Server lỗi khi khởi động

```bash
cd server
# Xem log chi tiết
docker compose --env-file .env.docker logs server

# Khởi động lại stack
docker compose --env-file .env.docker down
docker compose --env-file .env.docker up -d --build
```

### Reset toàn bộ database

```bash
cd server
docker compose --env-file .env.docker down -v   # xóa cả volume
docker compose --env-file .env.docker up -d --build
```

> ⚠️ Lệnh này xóa toàn bộ dữ liệu PostgreSQL.

### Flutter build lỗi

```bash
cd client/artifact_app
flutter clean
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

---

## Tóm tắt lệnh nhanh (chạy mỗi phiên làm việc)

```bash
# Terminal 1 — Khởi động server
cd /home/thepiece/System/Artifact-Pose-System/server
docker compose --env-file .env.docker up -d
curl http://127.0.0.1:8000/health   # xác nhận server OK

# Terminal 2 — Thiết lập USB + chạy app
adb devices                          # xác nhận điện thoại kết nối
adb reverse tcp:8000 tcp:8000        # tạo tunnel USB
cd /home/thepiece/System/Artifact-Pose-System/client/artifact_app
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```
