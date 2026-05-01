import 'package:flutter/foundation.dart';
import '../models/user.dart';
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
  String? get error => _error;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _users = await _service.list();
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
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return null;
    }
  }
}
