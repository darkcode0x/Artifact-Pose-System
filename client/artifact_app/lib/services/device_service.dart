import '../models/iot_device.dart';
import 'api_client.dart';

class DeviceService {
  final ApiClient _api;

  DeviceService(this._api);

  /// `GET /api/v1/devices` — list all DB-backed devices.
  Future<List<IotDevice>> list() async {
    final body = await _api.get('/api/v1/devices');
    if (body is List) {
      return body
          .whereType<Map<String, dynamic>>()
          .map(IotDevice.fromJson)
          .toList();
    }
    return const [];
  }

  /// `GET /api/v1/devices/{id}/status` — runtime status (in-memory command service).
  /// Returns an [IotDevice] whose [IotDevice.isOnline] reflects the live MQTT
  /// heartbeat (same 2-minute window the list endpoint uses server-side).
  Future<IotDevice> getStatus(String deviceId) async {
    final body = await _api.get('/api/v1/devices/$deviceId/status');
    final map = body as Map<String, dynamic>;

    // Response shape: {ok, device_id, status: {topic, payload: {status: "online",...}, received_ts_ms}}
    // IotDevice.fromJson expects db_status inside the status map, which is NOT
    // present here — so we compute isOnline ourselves using the same 2-minute
    // heartbeat window the server uses for the list endpoint.
    const onlineWindowMs = 120000;
    bool isOnline = false;
    final statusData = map['status'];
    if (statusData is Map<String, dynamic>) {
      final payload = statusData['payload'];
      final receivedTs = statusData['received_ts_ms'];
      if (payload is Map<String, dynamic> &&
          payload['status'] == 'online' &&
          receivedTs is int) {
        final nowMs = DateTime.now().millisecondsSinceEpoch;
        if (nowMs - receivedTs < onlineWindowMs) isOnline = true;
      }
    }

    return IotDevice(
      deviceId: map['device_id']?.toString() ?? deviceId,
      deviceCode: deviceId,
      status: isOnline ? DeviceStatus.online : DeviceStatus.offline,
      createdAt: DateTime.now(),
    );
  }

  /// `POST /api/v1/devices` — admin/operator creates device. Backend uses query params.
  Future<void> create(String deviceCode, {String description = ''}) async {
    await _api.post('/api/v1/devices', query: {
      'device_code': deviceCode,
      'description': description,
    });
  }

  /// `PATCH /api/v1/devices/{id}` — update description/status. Query params.
  Future<void> update(String deviceId,
      {String? description, String? status}) async {
    final query = <String, dynamic>{};
    if (description != null) query['description'] = description;
    if (status != null) query['status'] = status;
    await _api.patch('/api/v1/devices/$deviceId', query: query);
  }

  /// `DELETE /api/v1/devices/{id}` — admin only.
  Future<void> delete(String deviceId) async {
    await _api.delete('/api/v1/devices/$deviceId');
  }

  /// `GET /api/v1/devices/{id}/acks` — recent ack history.
  Future<List<Map<String, dynamic>>> acks(String deviceId,
      {int limit = 20}) async {
    final body = await _api.get('/api/v1/devices/$deviceId/acks',
        query: {'limit': limit});
    if (body is Map<String, dynamic> && body['acks'] is List) {
      return (body['acks'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    return const [];
  }

  /// `POST /api/v1/devices/{id}/queue_move` — enqueue a movement command.
  Future<Map<String, dynamic>?> sendMoveCommand(
      String deviceId, Map<String, dynamic> command) async {
    final body = await _api
        .post('/api/v1/devices/$deviceId/queue_move', body: command);
    return body is Map<String, dynamic> ? body : null;
  }
}
