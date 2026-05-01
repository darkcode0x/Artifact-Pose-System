import 'package:flutter/foundation.dart';

import '../models/user.dart';
import '../services/api_client.dart';
import '../services/user_service.dart';

class UserProvider with ChangeNotifier {
  final UserService _service;

  UserProvider(this._service);

  List<User> _users = [];
  bool _loading = false;
  String? _error;

  List<User> get users => List.unmodifiable(_users);
  int get userCount => _users.length;
  bool get loading => _loading;
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
      debugPrint('UserProvider ApiException: ${e.message}');
    } catch (e) {
      _error = 'Could not load users';
      debugPrint('UserProvider Error: $e');
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<User?> create({
    required String username,
    required String password,
    required UserRole role,
    String? fullName,
    int? age,
    String? email,
    String? phone,
  }) async {
    try {
      final created = await _service.create(
        username: username,
        password: password,
        role: role,
        fullName: fullName,
        age: age,
        email: email,
        phone: phone,
      );
      _users = [created, ..._users];
      notifyListeners();
      return created;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      rethrow;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<bool> remove(String id) async {
    try {
      await _service.delete(id);
      _users = _users.where((u) => u.userId != id).toList();
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      rethrow;
    }
  }

  Future<User?> update(
    String id, {
    UserRole? role,
    String? fullName,
    int? age,
    String? email,
    String? phone,
  }) async {
    try {
      final updated = await _service.update(
        id,
        role: role,
        fullName: fullName,
        age: age,
        email: email,
        phone: phone,
      );
      _users = _users.map((u) => u.userId == id ? updated : u).toList();
      notifyListeners();
      return updated;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      rethrow;
    }
  }

  Future<User?> toggleActive(String id) async {
    try {
      final updated = await _service.toggleActive(id);
      _users = _users.map((u) => u.userId == id ? updated : u).toList();
      notifyListeners();
      return updated;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      rethrow;
    }
  }
}
