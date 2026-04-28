import 'dart:io';

import 'package:flutter/foundation.dart';

import '../models/artifact.dart';
import '../models/artifact_status.dart';
import '../models/inspection.dart';
import '../services/api_client.dart';
import '../services/artifact_service.dart';

class ArtifactProvider with ChangeNotifier {
  final ArtifactService _service;

  ArtifactProvider(this._service);

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
    DateTime? scheduledDate,
    String? scheduledTime,
  }) async {
    try {
      final created = await _service.create(
        name: name,
        description: description,
        location: location,
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
    }
  }

  Future<Artifact?> updateDetails(
    int id, {
    String? name,
    String? description,
    String? location,
    ArtifactStatus? status,
  }) async {
    try {
      final updated = await _service.update(
        id,
        name: name,
        description: description,
        location: location,
        status: status,
      );
      _replace(updated);
      return updated;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<Artifact?> updateStatus(int id, ArtifactStatus status) async {
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

  Future<void> delete(int id) async {
    try {
      await _service.delete(id);
      _artifacts = _artifacts.where((a) => a.id != id).toList();
      notifyListeners();
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      rethrow;
    }
  }

  Future<Artifact?> uploadReference(int id, File file) async {
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
    int id, {
    required File image,
    String description = '',
    String? createdBy,
  }) async {
    try {
      final result = await _service.inspect(
        id,
        image: image,
        description: description,
        createdBy: createdBy,
      );
      // Server may have escalated artifact status; refresh that one.
      try {
        final refreshed = await _service.get(id);
        _replace(refreshed);
      } catch (_) {/* ignore secondary fetch failure */}
      return result;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<List<Inspection>> historyFor(int id) async {
    try {
      return await _service.inspections(id);
    } on ApiException {
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
