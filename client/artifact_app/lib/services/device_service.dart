import '../models/iot_device.dart';
import 'api_client.dart';

class DeviceService {
  final ApiClient _api;

  DeviceService(this._api);

  Future<List<IotDevice>> list() async {
    final body = await _api.get('/api/v1/devices/status_all'); // Cần BE hỗ trợ route này hoặc lấy qua mqtt health
    // Giả sử có route list devices
    if (body is! List) return [];
    return body.map((json) => IotDevice.fromJson(json)).toList();
  }

  Future<IotDevice> getStatus(String deviceId) async {
    final body = await _api.get('/api/v1/devices/$deviceId/status');
    return IotDevice.fromJson(body);
  }

  Future<dynamic> sendMoveCommand(String deviceId, Map<String, dynamic> command) async {
    return await _api.post('/api/v1/devices/$deviceId/queue_move', body: command);
  }
}
