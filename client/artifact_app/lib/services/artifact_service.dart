import 'dart:io';

import '../models/artifact.dart';
import '../models/artifact_status.dart';
import '../models/inspection.dart';
import 'api_client.dart';

class ArtifactService {
  final ApiClient _api;

  ArtifactService(this._api);

  Future<List<Artifact>> list({ArtifactStatus? status}) async {
    final body = await _api.get(
      '/api/v1/artifacts',
      query: status == null ? null : {'status': status.wireValue},
    );
    if (body is! List) return const [];
    return body
        .whereType<Map<String, dynamic>>()
        .map(Artifact.fromJson)
        .toList();
  }

  Future<List<Artifact>> alerts() async {
    final body = await _api.get('/api/v1/artifacts/alerts');
    if (body is! List) return const [];
    return body
        .whereType<Map<String, dynamic>>()
        .map(Artifact.fromJson)
        .toList();
  }

  Future<Artifact> get(int id) async {
    final body = await _api.get('/api/v1/artifacts/$id');
    return Artifact.fromJson(body as Map<String, dynamic>);
  }

  Future<Artifact> create({
    required String name,
    required String description,
    required String location,
    ArtifactStatus status = ArtifactStatus.good,
    DateTime? scheduledDate,
    String? scheduledTime,
  }) async {
    final body = await _api.post('/api/v1/artifacts', body: {
      'name': name,
      'description': description,
      'location': location,
      'status': status.wireValue,
      if (scheduledDate != null) 'scheduled_date': scheduledDate.toIso8601String(),
      if (scheduledTime != null) 'scheduled_time': scheduledTime,
    });
    return Artifact.fromJson(body as Map<String, dynamic>);
  }

  Future<Artifact> update(
    int id, {
    String? name,
    String? description,
    String? location,
    ArtifactStatus? status,
  }) async {
    final patch = <String, dynamic>{};
    if (name != null) patch['name'] = name;
    if (description != null) patch['description'] = description;
    if (location != null) patch['location'] = location;
    if (status != null) patch['status'] = status.wireValue;

    final body = await _api.patch('/api/v1/artifacts/$id', body: patch);
    return Artifact.fromJson(body as Map<String, dynamic>);
  }

  Future<void> delete(int id) async {
    await _api.delete('/api/v1/artifacts/$id');
  }

  Future<Artifact> uploadReference(int id, File image) async {
    final body = await _api.postMultipart(
      '/api/v1/artifacts/$id/reference',
      file: image,
    );
    return Artifact.fromJson(body as Map<String, dynamic>);
  }

  Future<Inspection> inspect(
    int id, {
    required File image,
    String description = '',
    String? createdBy,
  }) async {
    final fields = <String, String>{'description': description};
    if (createdBy != null) fields['created_by'] = createdBy;

    final body = await _api.postMultipart(
      '/api/v1/artifacts/$id/inspect',
      file: image,
      fields: fields,
    );
    return Inspection.fromJson(body as Map<String, dynamic>);
  }

  Future<List<Inspection>> inspections(int id, {int limit = 50}) async {
    final body = await _api.get(
      '/api/v1/artifacts/$id/inspections',
      query: {'limit': limit},
    );
    if (body is! Map<String, dynamic>) return const [];
    final items = body['items'];
    if (items is! List) return const [];
    return items
        .whereType<Map<String, dynamic>>()
        .map(Inspection.fromJson)
        .toList();
  }
}
