import 'api_client.dart';

class WorkflowService {
  final ApiClient _api;

  WorkflowService(this._api);

  Future<Map<String, dynamic>> triggerCapture({
    required String deviceId,
    required String artifactId, // Đảm bảo String
    required String jobType,
  }) async {
    final response = await _api.post(
      '/api/v1/workflows/$deviceId/capture-request',
      body: {
        'artifact_id': artifactId,
        'job_type': jobType,
        'use_latest_metadata': true,
      },
    );
    return response as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getLatestMetadata(String deviceId) async {
    final response = await _api.get('/api/v1/workflows/$deviceId/latest-capture-metadata');
    return response as Map<String, dynamic>;
  }
}
