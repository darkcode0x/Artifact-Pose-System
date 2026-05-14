import 'package:flutter/foundation.dart';

import '../models/user.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/token_storage.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthProvider with ChangeNotifier {
  final AuthService _authService;
  final TokenStorage _tokens;
  final ApiClient _api;

  AuthStatus _status = AuthStatus.unknown;
  String? _role;
  String? _username;
  User? _currentUser;

  AuthProvider({
    required AuthService authService,
    required TokenStorage tokens,
    required ApiClient api,
  })  : _authService = authService,
        _tokens = tokens,
        _api = api;

  AuthStatus get status => _status;
  String? get role => _role;
  String? get username => _username;
  User? get currentUser => _currentUser;
  bool get isAdmin => _role == 'admin';

  Future<void> bootstrap() async {
    final token = await _tokens.readToken();
    if (token != null && token.isNotEmpty) {
      _role = await _tokens.readRole();
      _username = await _tokens.readUsername();
      _status = AuthStatus.authenticated;
      await fetchFullProfile();
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
    await fetchFullProfile();
    notifyListeners();
  }

  Future<void> fetchFullProfile() async {
    if (_username == null) return;
    try {
      // Backend identifies user from JWT (Depends(get_current_user)).
      final res = await _api.get('/api/v1/users/me');
      _currentUser = User.fromJson(res as Map<String, dynamic>);
      notifyListeners();
    } catch (e) {
      debugPrint('Failed to fetch full profile: $e');
    }
  }

  Future<void> logout() async {
    await _authService.logout();
    _role = null;
    _username = null;
    _currentUser = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  void onSessionExpired() {
    if (_status != AuthStatus.unauthenticated) {
      _role = null;
      _username = null;
      _currentUser = null;
      _status = AuthStatus.unauthenticated;
      Future.microtask(notifyListeners);
    }
  }
}
