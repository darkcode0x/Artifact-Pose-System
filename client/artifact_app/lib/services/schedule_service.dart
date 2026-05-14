import '../models/schedule.dart';
import 'api_client.dart';

class ScheduleService {
  final ApiClient _api;

  ScheduleService(this._api);

  Future<List<Schedule>> list({DateTime? date, String? operator}) async {
    final query = <String, dynamic>{};
    if (date != null) query['date'] = date.toIso8601String();
    if (operator != null && operator.isNotEmpty) query['operator'] = operator;

    final body = await _api.get(
      '/api/v1/schedules',
      query: query.isEmpty ? null : query,
    );
    if (body is! List) return const [];
    return body
        .whereType<Map<String, dynamic>>()
        .map(Schedule.fromJson)
        .toList();
  }

  Future<Schedule> create({
    required String artifactId, // Đảm bảo String
    required DateTime scheduledDate,
    String scheduledTime = '09:00',
    String operatorUsername = '',
    String notes = '',
  }) async {
    final body = await _api.post('/api/v1/schedules', body: {
      'artifact_id': artifactId,
      'scheduled_date': scheduledDate.toUtc().toIso8601String(),
      'scheduled_time': scheduledTime,
      'operator_username': operatorUsername,
      'notes': notes,
    });
    return Schedule.fromJson(body as Map<String, dynamic>);
  }

  Future<Schedule> markComplete(String id, bool completed) async { // Đảm bảo String
    final body = await _api.patch(
      '/api/v1/schedules/$id',
      body: {'completed': completed},
    );
    return Schedule.fromJson(body as Map<String, dynamic>);
  }

  Future<void> delete(String id) async { // Đảm bảo String
    await _api.delete('/api/v1/schedules/$id');
  }
}
