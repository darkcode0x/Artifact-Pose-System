# Artifact Pose System

Artifact Pose System là hệ thống kiểm tra hiện vật bằng camera, Raspberry Pi và cơ cấu điều khiển. Hệ thống tạo tư thế chuẩn (golden pose) cho từng hiện vật, căn chỉnh camera/thiết bị về tư thế đó, sau đó chạy kiểm tra ảnh bằng SSIM và mô hình AI để phát hiện hư hại hoặc sai lệch.

## Thành Phần Chính

- `server/`: FastAPI server, REST API, xác thực JWT, PostgreSQL/SQLite, MQTT bridge, pose workflow và AI inspection.
- `client/artifact_app/`: ứng dụng Flutter cho Android, dùng bởi admin/operator để quản lý hiện vật, lịch kiểm tra, thiết bị và kết quả.
- `embed/device_agent/`: agent chạy trên Raspberry Pi, nhận lệnh MQTT, điều khiển camera/phần cứng và upload ảnh về server.
- `server/native/pose_solver_cpp/`: nhân C++ cho ORB, triangulation, pose solver và tính sai lệch 6-DoF.
- `ai_module/` và `model/`: mã thử nghiệm/tiền xử lý AI và nơi đặt model `.pt` khi chạy hệ thống.

## Luồng Hoạt Động

1. Người dùng tạo artifact và yêu cầu chụp ảnh tham chiếu.
2. Raspberry Pi chụp stereo pair, server khởi tạo golden pose và lưu baseline image.
3. Khi căn chỉnh, server yêu cầu Pi chụp ảnh hiện tại, chạy pose correction rồi gửi lệnh motor/servo qua MQTT.
4. Khi kiểm tra, server so sánh ảnh hiện tại với baseline, chạy AI nếu được bật, lưu kết quả vào database và trả về app.

## Database

Runtime chính dùng PostgreSQL trong Docker Compose qua `AUTH_DATABASE_URL`. Nếu không cấu hình biến này, server fallback sang SQLite tại `server/data/auth.db`.

File [artifact_db.sql](artifact_db.sql) là schema PostgreSQL tham chiếu cho các bảng `users`, `artifacts`, `images`, `image_comparisons`, `alerts`, `schedules` và `iot_devices`.

## Chạy Nhanh

```bash
cd server
cp env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

Server mặc định chạy ở `http://127.0.0.1:8000`. Ứng dụng Flutter nằm trong `client/artifact_app/`.

## Tài Liệu Chi Tiết

- Cài đặt, deploy PC/WSL2, Android, Raspberry Pi và các lệnh vận hành: [DEPLOY_INSTRUCTION.md](DEPLOY_INSTRUCTION.md)
- Kiến trúc, workflow, API, dữ liệu runtime và cách gỡ lỗi: [SYSTEM_INSTRUCTION.md](SYSTEM_INSTRUCTION.md)
