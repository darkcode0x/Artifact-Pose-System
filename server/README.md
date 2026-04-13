# IoT Artifact Server (Python FastAPI)

Server nay duoc viet de ket noi voi device_agent va mobile thong qua REST API, dong thoi bridge MQTT de push command den Raspberry Pi.

## Muc tieu

- Tuong thich endpoint hien co cua device_agent:
  - `POST /devices/get_device_id`
  - `POST /devices/{device_id}/move`
  - `POST /inspections/upload`
- Ho tro queue command va publish command qua MQTT
- Ho tro module nap model AI (onnx/torch/ultralytics)
- Tich hop truc tiep Artifact Pose module trong server de can chinh pose bang G2O
- Cau truc code de de mo rong va quan ly

## Kien truc thu muc

```text
server/
  app/
    api/
      routes/
        health.py
        devices.py
        inspections.py
        models.py
        pose.py
    core/
      config.py
    schemas/
      devices.py
      inspection.py
      models.py
      pose.py
    services/
      state.py
      device_registry.py
      command_service.py
      mqtt_bridge.py
      inspection_service.py
      model_service.py
      pose_service.py
    modules/
      artifact_pose/
        common.py
        correction.py
        initialize.py
    main.py
  data/
    camera_params_4k.yaml
  .env.example
  requirements.txt
  run.py
```

## Thu vien chon

- FastAPI: phu hop REST API, co docs tu dong (`/docs`), de tich hop mobile
- Pydantic: validate input/output ro rang
- paho-mqtt: bridge command/status/ack voi device_agent
- OpenCV + NumPy: xu ly anh va pose
- G2O (qua `pose_solver_cpp`): toi uu hybrid pose de tang do chinh xac

## Cai dat

```bash
cd server
pip install -r requirements.txt
```

Neu can AI backend thuc:

```bash
pip install onnxruntime
pip install torch
pip install ultralytics
```

## Deploy local voi Docker (server + PostgreSQL + MQTT)

File da duoc them:

- `server/Dockerfile`
- `server/docker-compose.yml`
- `server/env.docker.example`

Chay stack local:

```bash
cd server
cp env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

Kiem tra nhanh:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/mqtt/health
```

Neu can reset data DB local:

```bash
cd server
docker compose down -v
docker compose --env-file .env.docker up -d --build
```

## Cau hinh

1. Tao file `.env` tu `.env.example`
2. Dieu chinh:

- MQTT host/port/user/password
- Camera params + golden pose neu muon override
- `AUTO_DISPATCH_POSE_COMMAND=true` de server tu day lenh hieu chinh theo ket qua G2O

Lens-based camera params (khuyen dung):

- Dat cac file vao `server/data/camera_params/`
- Dat ten theo mau: `camera_params_lens_1.5.yaml`, `camera_params_lens_1.6.yaml`, ...
- Moi lens buoc 0.1
- Set `ARTIFACT_LENS_POSITION=1.5` de server tu map den file tuong ung

Uu tien nap camera params:

1. `ARTIFACT_CAMERA_PARAMS` (chi dinh file cu the)
2. `ARTIFACT_LENS_POSITION` + `ARTIFACT_CAMERA_PARAMS_DIR`
3. Fallback `server/data/camera_params_4k.yaml`

Pose module da duoc nhung truc tiep trong `app/modules/artifact_pose`.

De kich hoat G2O hybrid toi uu, can co module native `pose_solver_cpp` trong Python environment cua server.
Neu chua co, he thong van chay o che do fallback OpenCV.

Linux/Ubuntu:

- Build module native se ra file `.so` (khong phai `.dll`/`.pyd`)
- Dat file `pose_solver_cpp*.so` trong `server/app/modules/artifact_pose/` hoac trong Python site-packages

## Chay server

```bash
cd server
uvicorn run:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI:

- `http://127.0.0.1:8000/docs`

Khi chay khong dung Docker va su dung PostgreSQL local, dat trong `.env`:

```env
AUTH_DATABASE_URL=postgresql+psycopg://artifact:artifact123@127.0.0.1:5432/artifact_auth
```

## Nhom endpoint

### Health

- `GET /health`
- `GET /mqtt/health`
- `GET /mqtt/events?limit=100`
- `GET /pose/health`

### Device + Command

- `POST /devices/get_device_id`
- `POST /devices/{device_id}/queue_move`
- `POST /devices/{device_id}/move`
- `GET /devices/{device_id}/status`
- `GET /devices/{device_id}/acks`

### Workflow (web/mobile-compatible)

- `POST /workflows/{device_id}/capture-request`
  - `job_type=alignment`: chup anh cho can chinh
  - `job_type=golden_sample`: chup mau goc
- `POST /workflows/{device_id}/start-alignment`
  - bat dau vong lap can chinh: chup -> pose -> move -> chup lai
- `GET /workflows/{device_id}/latest-capture-metadata`
  - lay metadata camera moi nhat (lens_position, gain, shutter, ...)

### Inspection

- `POST /inspections/upload` (multipart: `file`, `metadata`)

Neu bat `RUN_POSE_ON_UPLOAD=true`, server se tu dong goi pose correction sau khi nhan anh.

Neu bat them `AUTO_DISPATCH_POSE_COMMAND=true`, server se doi ket qua G2O (`motor_command`) thanh lenh `action=move` va day den device_agent qua MQTT (fallback HTTP queue neu MQTT loi).

Neu bat `RUN_AI_ON_UPLOAD=true`, metadata can co:

```json
{
  "model_name": "artifact_classifier",
  "ai_input": [[0.1, 0.2, 0.3]]
}
```

### Model AI

- `GET /models`
- `POST /models/sync` (quet va nap model tu `./model`)
- `POST /models/load`
- `DELETE /models/{name}`
- `POST /models/{name}/predict`

Server tu dong goi sync model khi startup:

- Quet `MODEL_DIR` (mac dinh `./model`)
- Tu nap cac file `.onnx`, `.pt`, `.pth`
- Neu model `.pt` la checkpoint Ultralytics, backend se tu chon `ultralytics`

### Pose

- `POST /pose/correct` (upload 1 anh)
- `POST /pose/initialize_golden` (upload left + right)

### Web Client

- Mo giao dien test workflow tai: `GET /web-client`

## Tich hop device_agent

- device_agent dang dung `SERVER_BASE_URL=http://127.0.0.1:8000`
- Vi tri khuyen nghi trong repo: `embed/device_agent`
- Cac endpoint can thiet da duoc giu nguyen de tranh sua client
- Luong command uu tien MQTT; neu MQTT loi se fallback qua HTTP queue

## Kiem tra nhanh luong API + MQTT

Smoke test tu dong (API + MQTT + ACK) bang 1 lenh:

```bash
SMOKE_PI_PASSWORD='Pi!@#123' python3 server/tools/smoke_test_api_mqtt_ack.py
```

Mac dinh script se SSH vao Raspberry (`pi@100.83.253.100`), bat agent tam thoi, publish command, doi ACK va tra ket qua pass/fail.

Co the bo qua buoc SSH neu agent da chay san:

```bash
python3 server/tools/smoke_test_api_mqtt_ack.py --no-remote-agent --device-id dev-xxxx
```

1. Tao/lay device id:

```bash
curl -X POST http://127.0.0.1:8000/devices/get_device_id \
  -H 'Content-Type: application/json' \
  -d '{"machine_hash":"md5-demo-001","preferred_device_id":"pi-demo"}'
```

2. Day lenh move:

```bash
curl -X POST http://127.0.0.1:8000/devices/pi-demo/queue_move \
  -H 'Content-Type: application/json' \
  -d '{"action":"move","yaw_delta":1.5,"pitch_delta":-1.0,"x_steps":10,"z_steps":0,"x_dir":1,"z_dir":1}'
```

3. Theo doi bridge MQTT:

```bash
curl http://127.0.0.1:8000/mqtt/health
curl 'http://127.0.0.1:8000/mqtt/events?limit=20'
curl http://127.0.0.1:8000/devices/pi-demo/acks
curl http://127.0.0.1:8000/devices/pi-demo/status
```

## Mo rong tiep

- Thay DeviceRegistry memory/file bang Redis/PostgreSQL
- Them auth JWT cho mobile
- Them hang doi async (Celery/RQ) cho AI/pose infer nang
- Them dashboard theo doi stream status/ack theo device
