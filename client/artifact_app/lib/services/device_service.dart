import '../models/iot_device.dart';
import 'api_client.dart';

class DeviceService {
  final ApiClient _api;

  DeviceService(this._api);

  Future<List<IotDevice>> list() async {
    final body = await _api.get('/api/v1/devices');
    if (body is List) {
      return body.map((json) => IotDevice.fromJson(json as Map<String, dynamic>)).toList();
    }
    return const [];
  }

  Future<IotDevice> getStatus(String deviceId) async {
    final body = await _api.get('/api/v1/devices/$deviceId/status');
    return IotDevice.fromJson(body as Map<String, dynamic>);
  }

  Future<void> create(String deviceCode, String description) async {
    // Sửa: Gửi qua query parameter thay vì body để khớp với Backend
    await _api.post('/api/v1/devices', query: {
      'device_code': deviceCode,
      'description': description,
    });
  }

  Future<void> update(String deviceId, {String? description, String? status}) async {
    final query = <String, dynamic>{};
    if (description != null) query['description'] = description;
    if (status != null) query['status'] = status;

    // Sửa: Gửi qua query parameter thay vì body để khớp với Backend
    await _api.patch('/api/v1/devices/$deviceId', query: query);
  }

  Future<void> delete(String deviceId) async {
    await _api.delete('/api/v1/devices/$deviceId');
  }

  Future<List<Map<String, dynamic>>> acks(String deviceId, {int limit = 20}) async {
    final body = await _api.get('/api/v1/devices/$deviceId/acks', query: {'limit': limit});
    if (body is Map<String, dynamic> && body['acks'] is List) {
      return (body['acks'] as List).whereType<Map<String, dynamic>>().toList();
    }
    return const [];
  }

  Future<Map<String, dynamic>?> sendMoveCommand(String deviceId, Map<String, dynamic> command) async {
    final body = await _api.post('/api/v1/devices/$deviceId/queue_move', body: command);
    return body is Map<String, dynamic> ? body : null;
  }
}
