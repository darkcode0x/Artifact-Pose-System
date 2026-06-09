import '../models/inspection.dart';
import 'api_client.dart';

class WorkflowService {
  final ApiClient _api;
  static const Duration _aiInspectionTimeout = Duration(minutes: 2);

  WorkflowService(this._api);

  Future<Map<String, dynamic>> triggerCapture({
    required String deviceId,
    required String artifactId, // Đảm bảo String
    required String jobType,
  }) async {
    final response = await _api.post(
      '/workflows/$deviceId/capture-request',
      body: {
        'artifact_id': artifactId,
        'job_type': jobType,
        'use_latest_metadata': true,
      },
    );
    return response as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getLatestMetadata(String deviceId) async {
    final response = await _api.get(
      '/workflows/$deviceId/latest-capture-metadata',
    );
    return response as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> startInitialization({
    required String deviceId,
    required String artifactId,
  }) async {
    return _api.startInitialization(deviceId: deviceId, artifactId: artifactId);
  }

  Future<Map<String, dynamic>> startAlignment({
    required String deviceId,
    required String artifactId,
  }) async {
    return _api.startAlignment(deviceId: deviceId, artifactId: artifactId);
  }

  Future<List<Map<String, dynamic>>> pollAcks(
    String deviceId, {
    int limit = 15,
  }) async {
    final body = await _api.get(
      '/api/v1/devices/$deviceId/acks',
      query: {'limit': limit},
    );
    if (body is Map<String, dynamic> && body['acks'] is List) {
      return (body['acks'] as List).whereType<Map<String, dynamic>>().toList();
    }
    return const [];
  }

  Future<Inspection> inspectFromDevice({
    required String deviceId,
    required String artifactId,
    String description = '',
    String? createdBy,
  }) async {
    final body = await _api.post(
      '/api/v1/artifacts/$artifactId/inspect-from-device',
      query: {
        'device_id': deviceId,
        if (description.isNotEmpty) 'description': description,
        if (createdBy != null) 'created_by': createdBy,
      },
      timeoutOverride: _aiInspectionTimeout,
    );
    return Inspection.fromJson(body as Map<String, dynamic>);
  }

  /// Kiem tra artifact da khoi tao golden pose chua.
  Future<bool> hasGoldenPose(String artifactId) async {
    try {
      final body = await _api.get('/pose/golden-pose/$artifactId/status');
      if (body is Map<String, dynamic>) {
        return body['has_golden_pose'] == true;
      }
    } catch (_) {}
    return false;
  }
}
