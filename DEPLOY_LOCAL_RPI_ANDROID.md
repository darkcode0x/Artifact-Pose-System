# Deploy local server + PostgreSQL, Raspberry embed, Android emulator client

## 1) Kien truc muc tieu

- Server FastAPI: chay tren may local
- PostgreSQL: chay local (Docker)
- MQTT broker: chay local (Docker)
- Embed/device_agent: chay tren Raspberry Pi (qua Tailscale)
- Mobile app: chay tren Android emulator de test API

## 2) Cai Docker tren may local (Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Dang xuat dang nhap lai shell sau khi them user vao nhom docker.

## 3) Chay stack server + PostgreSQL + MQTT bang Docker

```bash
cd server
cp env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

Kiem tra:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/mqtt/health
```

## 4) Cau hinh Raspberry (embed/device_agent)

May local Tailscale IP hien tai: `100.90.229.25`

Trong file embed/device_agent/.env da dat:

- SERVER_BASE_URL=http://100.90.229.25:8000
- MQTT_HOST=100.90.229.25

Copy code len Raspberry va chay:

```bash
ssh pi@100.83.253.100
cd ~/Artifact-Pose-System/embed/device_agent
python3 -m venv .venv
source .venv/bin/activate
pip install requests paho-mqtt
python runtime/main_app.py
```

Neu chua clone repo tren Pi:

```bash
git clone <repo-url> ~/Artifact-Pose-System
```

## 5) Cai Android SDK + emulator

Cach de nhat: cai Android Studio, sau do tao AVD (Pixel + Android 14).

Neu da co Flutter:

```bash
flutter doctor -v
flutter doctor --android-licenses
```

## 6) Chay mobile app test API

```bash
cd client/artifact_app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Ghi chu:

- `10.0.2.2` la loopback tu Android emulator den host local.
- Co the dung Tailscale IP host local:

```bash
flutter run --dart-define=API_BASE_URL=http://100.90.229.25:8000
```

## 7) Smoke test API + MQTT

Tu dong test API + MQTT + ACK chi voi 1 lenh:

```bash
SMOKE_PI_PASSWORD='Pi!@#123' python3 server/tools/smoke_test_api_mqtt_ack.py
```

Script se:

- check `/health` va `/mqtt/health`
- SSH vao Raspberry, chay agent tam thoi
- tu tim `device_id` dang online
- day lenh `queue_move` qua MQTT
- cho ACK theo `task_id` va fail neu ACK khong `status=ok`

Tuy chon hay dung:

```bash
python3 server/tools/smoke_test_api_mqtt_ack.py --no-remote-agent --device-id dev-xxxx
python3 server/tools/smoke_test_api_mqtt_ack.py --base-url http://100.90.229.25:8000
```

Tao device id:

```bash
curl -X POST http://127.0.0.1:8000/devices/get_device_id \
  -H 'Content-Type: application/json' \
  -d '{"machine_hash":"md5-demo-001","preferred_device_id":"pi-demo"}'
```

Day lenh move:

```bash
curl -X POST http://127.0.0.1:8000/devices/pi-demo/queue_move \
  -H 'Content-Type: application/json' \
  -d '{"action":"move","yaw_delta":1.5,"pitch_delta":-1.0,"x_steps":10,"z_steps":0,"x_dir":1,"z_dir":1}'
```

Kiem tra MQTT event/ack/status:

```bash
curl http://127.0.0.1:8000/mqtt/health
curl 'http://127.0.0.1:8000/mqtt/events?limit=20'
curl http://127.0.0.1:8000/devices/pi-demo/acks
curl http://127.0.0.1:8000/devices/pi-demo/status
```

## 8) Tinh trang ket noi thuc te

- Tailscale co the ping toi Raspberry thanh cong.
- SSH toi Pi bang key khong thanh cong (Permission denied), can password hoac SSH key hop le de chay test tu xa truc tiep.
