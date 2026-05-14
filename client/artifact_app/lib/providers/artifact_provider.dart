import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

import '../models/artifact.dart';
import '../models/artifact_status.dart';
import '../models/inspection.dart';
import '../services/api_client.dart';
import '../services/artifact_service.dart';
import '../services/workflow_service.dart';

class ArtifactProvider with ChangeNotifier {
  final ArtifactService _service;
  final WorkflowService _workflow;

  ArtifactProvider(this._service, this._workflow);

  List<Artifact> _artifacts = [];
  bool _loading = false;
  String? _error;

  List<Artifact> get artifacts => List.unmodifiable(_artifacts);
  List<Artifact> get alerts =>
      _artifacts.where((a) => a.status.isAlert).toList(growable: false);
  bool get loading => _loading;
  String? get error => _error;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _artifacts = await _service.list();
    } on ApiException catch (e) {
      _error = e.message;
    } catch (e) {
      _error = 'Could not load artifacts';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<Artifact?> create({
    required String name,
    required String description,
    required String location,
    int inspectionIntervalDays = 0, // Thêm tham số chu kỳ
    DateTime? scheduledDate,
    String? scheduledTime,
  }) async {
    _error = null;
    try {
      final created = await _service.create(
        name: name,
        description: description,
        location: location,
        inspectionIntervalDays: inspectionIntervalDays,
        scheduledDate: scheduledDate,
        scheduledTime: scheduledTime,
      );
      _artifacts = [created, ..._artifacts];
      notifyListeners();
      return created;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    } catch (e) {
      _error = 'Failed to create artifact';
      notifyListeners();
      return null;
    }
  }

  Future<Artifact?> updateDetails(
    String id, {
    String? name,
    String? description,
    String? location,
    ArtifactStatus? status,
    int? inspectionIntervalDays,
  }) async {
    _error = null;
    try {
      final updated = await _service.update(
        id,
        name: name,
        description: description,
        location: location,
        status: status,
        inspectionIntervalDays: inspectionIntervalDays,
      );
      _replace(updated);
      return updated;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<Artifact?> updateStatus(String id, ArtifactStatus status) async {
    _error = null;
    try {
      final updated = await _service.update(id, status: status);
      _replace(updated);
      return updated;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<bool> triggerRemoteCapture({
    required String deviceId,
    required String artifactId,
    required bool isReference,
  }) async {
    _error = null;
    try {
      final res = await _workflow.triggerCapture(
        deviceId: deviceId,
        artifactId: artifactId,
        jobType: isReference ? 'golden_sample' : 'alignment',
      );
      return res['ok'] == true;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return false;
    } catch (e) {
      _error = 'Failed to trigger device: $e';
      notifyListeners();
      return false;
    }
  }

  Future<void> delete(String id) async {
    _error = null;
    try {
      await _service.delete(id);
      _artifacts = _artifacts.where((a) => a.id != id).toList();
      notifyListeners();
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
    }
  }

  Future<Artifact?> uploadReference(String id, XFile file) async {
    _error = null;
    try {
      final updated = await _service.uploadReference(id, file);
      _replace(updated);
      return updated;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<Inspection?> inspect(
    String id, {
    required XFile image,
    String description = '',
    String? createdBy,
    String? scheduleId,
  }) async {
    _error = null;
    try {
      final result = await _service.inspect(
        id,
        image: image,
        description: description,
        createdBy: createdBy,
        scheduleId: scheduleId,
      );
      try {
        final refreshed = await _service.get(id);
        _replace(refreshed);
      } catch (_) {}
      return result;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<List<Inspection>> historyFor(String id) async {
    try {
      return await _service.inspections(id);
    } catch (_) {
      return const [];
    }
  }

  void _replace(Artifact updated) {
    _artifacts = _artifacts
        .map((a) => a.id == updated.id ? updated : a)
        .toList(growable: false);
    notifyListeners();
  }
}
