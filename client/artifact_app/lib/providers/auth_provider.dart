import 'package:flutter/foundation.dart';

import '../services/auth_service.dart';
import '../services/token_storage.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthProvider with ChangeNotifier {
  final AuthService _authService;
  final TokenStorage _tokens;

  AuthStatus _status = AuthStatus.unknown;
  String? _role;
  String? _username;

  AuthProvider({required AuthService authService, required TokenStorage tokens})
      : _authService = authService,
        _tokens = tokens;

  AuthStatus get status => _status;
  String? get role => _role;
  String? get username => _username;
  bool get isAdmin => _role == 'admin';

  Future<void> bootstrap() async {
    final token = await _tokens.readToken();
    if (token != null && token.isNotEmpty) {
      _role = await _tokens.readRole();
      _username = await _tokens.readUsername();
      _status = AuthStatus.authenticated;
    } else {
      _status = AuthStatus.unauthenticated;
    }
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    final result = await _authService.login(username, password);
    _role = result.role;
    _username = username;
    _status = AuthStatus.authenticated;
    notifyListeners();
  }

  Future<void> logout() async {
    await _authService.logout();
    _role = null;
    _username = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  /// Called by ApiClient on 401 — clears local state without hitting server.
  void onSessionExpired() {
    if (_status != AuthStatus.unauthenticated) {
      _role = null;
      _username = null;
      _status = AuthStatus.unauthenticated;
      Future.microtask(notifyListeners);
    }
  }
}
