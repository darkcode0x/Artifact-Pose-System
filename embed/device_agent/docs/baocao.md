# BÁO CÁO TUẦN TIẾP THEO - PHẦN CỨNG IOT NODE

## 1. Mục tiêu tuần
Trong tuần tiếp theo, trọng tâm công việc vẫn là hoàn thiện khối IoT Node theo hướng giao tiếp ổn định với hệ thống backend. Sau khi đã có nền tảng phần cứng và test run cơ bản ở tuần trước, công việc tập trung vào:
- Chuẩn hóa luồng giao tiếp giữa Mobile, Backend, MQTT Broker và Raspberry Pi Node.
- Vẽ sơ đồ giao tiếp IoT để đồng bộ nhận thức kiến trúc giữa các thành viên.
- Code nhẹ phần giao tiếp sử dụng MQTT trên edge node để nhận lệnh và phản hồi trạng thái.

## 2. Công việc đã thực hiện
### 2.1 Vẽ sơ đồ giao tiếp IoT
- Đã hoàn thành sơ đồ kiến trúc giao tiếp tổng thể giữa các thành phần:
  - Control side: Mobile Application, Backend API Server.
  - Connectivity: MQTT Broker.
  - Embedded side: Raspberry Pi Node (Command Parser, Device Identity, Task ID TTL Cache, Control Engine, Camera Capture + Upload).
- Sơ đồ thể hiện rõ các kênh giao tiếp chính:
  - Mobile <-> Backend: HTTPS/WebSocket (UI, gửi lệnh, cập nhật trạng thái).
  - Backend <-> Broker: publish command, subscribe ACK/status.
  - Broker <-> Raspberry Pi: command và ACK/status qua MQTT.
  - Raspberry Pi -> Backend: upload inspection (ảnh + metadata) qua HTTPS.
### 2.2 Triển khai code nhẹ phần giao tiếp MQTT
- Đã triển khai luồng xử lý cơ bản trên IoT Node theo mô hình push:
  - Raspberry Pi subscribe command topic theo device_id.
  - Nhận message command, parse thông tin và dispatch xử lý.
  - Xử lý dedup task bằng Task ID TTL Cache để tránh xử lý trùng do QoS1 có thể deliver lại.
  - Publish ACK/status về broker để backend tổng hợp trạng thái.
- Đã tách rõ vai trò:
  - Backend lo nghiệp vụ và điều phối.
  - Edge node thực thi lệnh điều khiển, chụp ảnh và upload kết quả.
- Đã bố trí biến cấu hình qua file .env để dễ đổi môi trường và triển khai.

## 3. Kết quả đạt được
- Đã có tài liệu sơ đồ giao tiếp IoT rõ ràng, phục vụ review kỹ thuật và onboarding.
- Đã có phiên bản giao tiếp MQTT tối giản nhưng đủ dùng cho chu trình command -> execute -> ack/status.
- Luồng dữ liệu từ edge node lên backend được giữ đơn giản và dễ theo dõi (MQTT cho command/state, HTTPS cho upload inspection).
- Nền tảng hiện tại sẵn sàng cho việc nâng cấp tiếp theo (tối ưu retry, monitoring và hardening).

## 4. So sánh và lý do chọn MQTT thay vì WebSocket
### 4.1 Tiêu chí đánh giá
Các tiêu chí được xem xét cho bài toán edge embedded:
- Độ nhẹ và ổn định trên thiết bị tài nguyên hạn chế.
- Độ phù hợp với mô hình pub/sub nhiều thành phần.
- Cơ chế đảm bảo giao nhận message.
- Khả năng tách rời producer/consumer và mở rộng hệ thống.
- Độ phức tạp khi vận hành và bảo trì.

### 4.2 So sánh tóm tắt
| Tiêu chí | MQTT | WebSocket |
|---|---|---|
| Mô hình giao tiếp | Pub/Sub thông qua broker, rất phù hợp command fan-out và status aggregation | Kết nối 2 chiều trực tiếp client-server |
| Overhead | Nhẹ, header nhỏ, tối ưu cho IoT | Nhẹ hơn HTTP polling nhưng không tối ưu bằng MQTT cho telem/command nhỏ |
| Độ tin cậy message | Hỗ trợ QoS 0/1/2, có retained/last-will | Không có cơ chế QoS mặc định, cần tự build ack/retry |
| Khả năng mở rộng | Dễ mở rộng nhiều node thông qua topic | Mở rộng được nhưng thường cần tự quản lý routing và phân luồng |
| Độ phù hợp với edge node | Cao (thiết bị nhúng, mạng có lúc không ổn định) | Tốt cho realtime UI, kém tối ưu hơn cho fleet device IoT |
| Vận hành hệ thống | Cần broker nhưng dễ chuẩn hóa luồng pub/sub | Đơn giản khi ít kết nối, phức tạp dần khi cần routing và reliability |

### 4.3 Kết luận lựa chọn
Lựa chọn MQTT cho khối IoT Node là phù hợp hơn trong giai đoạn này vì:
- Bài toán cần mô hình command/status bất đồng bộ và dễ mở rộng theo số lượng thiết bị.
- Cần có cơ chế reliability có sẵn (QoS) thay vì tự xây dựng trên WebSocket.
- Cần tối ưu tài nguyên cho edge node và giữ code giao tiếp gọn nhẹ.

WebSocket vẫn phù hợp cho lớp HMI (Mobile/Web dashboard) cần cập nhật trạng thái realtime đến người vận hành. Vì vậy, hệ thống hiện tại sử dụng kết hợp:
- MQTT cho backend <-> edge node.
- HTTPS/WebSocket cho mobile app <-> backend.

## 5. Khó khăn và cách xử lý trong tuần
- Khó khăn chính là giữ sơ đồ dễ đọc khi có nhiều luồng giao tiếp hai chiều.
- Cách xử lý:
  - Chuẩn hóa lại bố cục theo 3 lớp (Control, Connectivity, Embedded).
  - Định danh rõ từng luồng command, ack/status, upload.
  - Tách luồng MQTT và HTTPS để tránh nhầm lẫn trách nhiệm kênh truyền.

## 6. Kế hoạch tuần tiếp theo
- Tích hợp thêm log/metric cho luồng MQTT (latency command -> ack, tỉ lệ duplicate, retry count).
- Hoàn thiện rule timeout và retry cho task edge để tăng độ bền vận hành.
- Bổ sung test kịch bản mất kết nối tạm thời (broker/network) và đánh giá hành vi phục hồi.
- Hoàn thiện tài liệu hóa để chuẩn bị cho giai đoạn demo hệ thống tổng.
