# Hướng dẫn test & tinh chỉnh pipeline AI inspection

## 1. Chuẩn bị (chạy một lần duy nhất)

```bash
# Đảm bảo Docker server đang chạy
cd /home/thepiece/System/Artifact-Pose-System/server
docker compose up -d

# Copy test script vào container (cần làm lại mỗi khi sửa script)
docker cp tools/test_inspect_pipeline.py artifact_server:/app/tools/test_inspect_pipeline.py
```

---

## 2. Lệnh chạy cơ bản (mặc định)

```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --reference data/uploads/artifacts/f86cb2/golden_left_f86cb2_1778823519555.png \
  --current   data/uploads/artifacts/f86cb2/final_aligned_f86cb2_1778824053659.png \
  --model     /app/model/new-10-05-best.pt \
  --out       /tmp/inspect_out
```

Sau đó copy kết quả ra host để xem ảnh:

```bash
mkdir -p /tmp/inspect_out_local
docker cp artifact_server:/tmp/inspect_out/. /tmp/inspect_out_local/
```

Xem ảnh kết quả:
- `/tmp/inspect_out_local/detect_*.jpg`   — ảnh annotated với bounding boxes
- `/tmp/inspect_out_local/heatmap_*.jpg`  — heatmap vùng khác biệt (đỏ = khác nhiều)
- `/tmp/inspect_out_local/crop_*_N.jpg`   — từng vùng được cắt ra đưa vào YOLO
- `/tmp/inspect_out_local/report_*.json`  — toàn bộ số liệu

---

## 3. Các tham số có thể điều chỉnh

### `--conf` — Ngưỡng confidence YOLO
**Mặc định:** `0.05`  
Đây là **ngưỡng bạn tự đặt trong code** (`model_service.py`, không liên quan training).  
YOLO sẽ không trả về bất kỳ detection nào có score thấp hơn giá trị này.

| Giá trị | Hành vi |
|---------|---------|
| `0.05`  | Cực nhạy — thấy mọi thứ kể cả nhiễu |
| `0.15`  | Cân bằng — loại bỏ nhiễu nhẹ |
| `0.40`  | Chỉ lấy kết quả chắc chắn |
| `0.65`  | Chỉ HIGH severity |

**Ví dụ — xem mô hình cho burn_marks confidence bao nhiêu:**
```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --model /app/model/new-10-05-best.pt \
  --conf 0.01 \
  --out /tmp/inspect_conf001
```

---

### `--min-area` — Ngưỡng diện tích contour tối thiểu
**Mặc định:** `0.0001` (= 0.01% diện tích ảnh)  
Lọc bỏ các vùng nhiễu nhỏ sau bước SSIM diff. Tính theo tỷ lệ ảnh nên scale tự động với mọi độ phân giải.

| Giá trị | Ngưỡng thực trên ảnh 4K (8.3 MP) | Bắt được vòng tròn đường kính |
|---------|----------------------------------|-------------------------------|
| `0.0005`| 4147 px²  | ≥ 73 px |
| `0.0001`| 829 px²   | ≥ 33 px ← **hiện tại** |
| `0.00005`| 414 px²  | ≥ 23 px |
| `0.00001`| 82 px²   | ≥ 10 px (quá nhạy, nhiều nhiễu) |

**Ví dụ — muốn bắt vết nhỏ hơn nữa:**
```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --model /app/model/new-10-05-best.pt \
  --min-area 0.00005 \
  --out /tmp/inspect_minarea
```

**Lưu ý:** Nếu giảm quá thấp sẽ sinh ra nhiều crop, làm tăng thời gian chạy tuyến tính.  
Pipeline hiện giới hạn tối đa 20 crops để kiểm soát latency.

---

### `--damage-pct` — Ngưỡng % damage tổng thể để kích hoạt AI
**Mặc định:** `0.5` (%)  
Nếu tổng diện tích vùng khác biệt < 0.5% ảnh → bỏ qua bước crop/YOLO (coi là nhiễu ánh sáng/alignment).

| Giá trị | Khi nào dùng |
|---------|-------------|
| `0.1`   | Ảnh rất ổn định, muốn bắt thay đổi cực nhỏ |
| `0.5`   | Cân bằng ← **hiện tại** |
| `1.0`   | Chỉ trigger khi có hư hại rõ ràng |
| `2.0`   | Môi trường chụp không ổn định, nhiều nhiễu |

**Ví dụ:**
```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --model /app/model/new-10-05-best.pt \
  --damage-pct 0.2 \
  --out /tmp/inspect_dpct
```

---

### `--otsu-fallback` — Ngưỡng pixel fallback khi Otsu thấp
**Mặc định:** `60`  
Khi thuật toán Otsu tự động chọn ngưỡng < 30 (ảnh quá đồng nhất), dùng giá trị này thay thế.  
Giá trị thấp hơn = nhạy hơn với sự thay đổi nhỏ trong ảnh đồng nhất.

| Giá trị | Hành vi |
|---------|---------|
| `30`    | Rất nhạy — bắt biến đổi ánh sáng nhẹ |
| `60`    | Mặc định cân bằng |
| `100`   | Chỉ bắt thay đổi rõ rệt |

---

## 4. Quy trình tinh chỉnh gợi ý

### Bước 1 — Xem model thực sự thấy gì (không có ngưỡng)
```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --model /app/model/new-10-05-best.pt \
  --conf 0.01 \
  --out /tmp/inspect_step1
docker cp artifact_server:/tmp/inspect_step1/. /tmp/inspect_step1_local/
```
Đọc terminal output — xem tất cả `class_name` và `conf` được in ra.  
Quyết định ngưỡng conf phù hợp dựa trên những số thực tế này.

### Bước 2 — Tinh chỉnh độ nhạy vùng crop
```bash
# Nếu thấy vùng nhỏ quan trọng bị bỏ sót → giảm --min-area
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --model /app/model/new-10-05-best.pt \
  --conf 0.15 \
  --min-area 0.00005 \
  --out /tmp/inspect_step2
```

### Bước 3 — Xác định conf production
Sau khi biết confidence thực của từng loại hư hại, đặt conf đủ thấp để bắt được,  
nhưng không quá thấp gây ra false positive. Thường `0.15`–`0.25` là hợp lý.

```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py \
  --model /app/model/new-10-05-best.pt \
  --conf 0.20 \
  --min-area 0.0001 \
  --damage-pct 0.3 \
  --out /tmp/inspect_step3
```

### Bước 4 — Áp dụng lên production
Sau khi tìm được bộ tham số ưng ý, cập nhật vào:

| Tham số | File | Dòng |
|---------|------|------|
| `--conf` → `conf=` | `server/app/services/model_service.py` | ~80 |
| `--min-area` → `* 0.0001` | `server/app/services/inspection_service.py` | ~306 |
| `--damage-pct` → `>= 0.5` | `server/app/services/inspection_service.py` | ~322 |
| `--otsu-fallback` → `60` | `server/app/services/inspection_service.py` | ~296 |

Sau đó rebuild:
```bash
cd /home/thepiece/System/Artifact-Pose-System/server
docker compose down && docker compose up --build -d
```

---

## 5. Script chẩn đoán contours (xem tất cả vùng trước khi lọc)

Nếu muốn thấy đầy đủ contours và area trước khi min_area filter:

```bash
docker cp tools/diagnose_contours.py artifact_server:/app/tools/diagnose_contours.py
docker exec -w /app artifact_server python tools/diagnose_contours.py
```

Output sẽ in bảng từng contour với cột `old` (ngưỡng cũ) và `new` (ngưỡng hiện tại).

---

## 6. Xem help đầy đủ

```bash
docker exec -w /app artifact_server python tools/test_inspect_pipeline.py --help
```
