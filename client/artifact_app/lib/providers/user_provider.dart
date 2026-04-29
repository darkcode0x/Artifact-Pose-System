import 'package:flutter/foundation.dart';

import '../models/user.dart';
import '../services/api_client.dart';
import '../services/user_service.dart';

class UserProvider with ChangeNotifier {
  final UserService _service;

  UserProvider(this._service);

  List<AppUser> _users = const [];
  bool _loading = false;
  String? _error;

  List<AppUser> get users => _users;
  bool get isLoading => _loading;
  String? get error => _error;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _users = await _service.list();
    } on ApiException catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load users';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<AppUser?> create({
    required String username,
    required String password,
    required String role,
  }) async {
    try {
      final created = await _service.create(
        username: username,
        password: password,
        role: role,
      );
      _users = [..._users, created];
      notifyListeners();
      return created;
    } on ApiException {
      rethrow;
    }
  }

  Future<bool> remove(int id) async {
    try {
      await _service.delete(id);
      _users = _users.where((u) => u.id != id).toList();
      notifyListeners();
      return true;
    } on ApiException {
      rethrow;
    }
  }

  Future<AppUser?> updateRole(int id, String role) async {
    try {
      final updated = await _service.update(id, role: role);
      _users = _users.map((u) => u.id == id ? updated : u).toList();
      notifyListeners();
      return updated;
    } on ApiException {
      rethrow;
    }
  }
}