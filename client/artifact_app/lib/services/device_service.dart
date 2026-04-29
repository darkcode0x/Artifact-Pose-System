import '../models/iot_device.dart';
import 'api_client.dart';

class DeviceService {
  final ApiClient _api;

  DeviceService(this._api);

  /// Lists registered devices from the in-memory registry. Backend route:
  /// `GET /devices` -> `{ok, count, devices: [{device_id, machine_hash, status}]}`.
  Future<List<IotDevice>> list() async {
    final body = await _api.get('/devices');
    if (body is Map<String, dynamic>) {
      final raw = body['devices'];
      if (raw is List) {
        return raw
            .whereType<Map<String, dynamic>>()
            .map(IotDevice.fromJson)
            .toList();
      }
    }
    return const [];
  }

  /// Status for a single device: `GET /devices/{id}/status`.
  Future<IotDevice> getStatus(String deviceId) async {
    final body = await _api.get('/devices/$deviceId/status');
    if (body is! Map<String, dynamic>) {
      return IotDevice(deviceId: deviceId, machineHash: '');
    }
    return IotDevice(
      deviceId: (body['device_id'] as String?) ?? deviceId,
      machineHash: '',
      status: (body['status'] is Map<String, dynamic>)
          ? body['status'] as Map<String, dynamic>
          : const {},
    );
  }

  /// Recent ack history for a device: `GET /devices/{id}/acks`.
  Future<List<Map<String, dynamic>>> acks(String deviceId,
      {int limit = 20}) async {
    final body =
        await _api.get('/devices/$deviceId/acks', query: {'limit': limit});
    if (body is Map<String, dynamic> && body['acks'] is List) {
      return (body['acks'] as List).whereType<Map<String, dynamic>>().toList();
    }
    return const [];
  }

  /// Enqueue a move command for a device: `POST /devices/{id}/queue_move`.
  Future<Map<String, dynamic>?> sendMoveCommand(
      String deviceId, Map<String, dynamic> command) async {
    final body =
        await _api.post('/devices/$deviceId/queue_move', body: command);
    return body is Map<String, dynamic> ? body : null;
  }
}
