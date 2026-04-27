import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists the auth token + role across app launches.
class TokenStorage {
  static const _tokenKey = 'auth_token';
  static const _roleKey = 'auth_role';
  static const _usernameKey = 'auth_username';

  final FlutterSecureStorage _storage;

  TokenStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  Future<void> save({
    required String token,
    required String role,
    String? username,
  }) async {
    await _storage.write(key: _tokenKey, value: token);
    await _storage.write(key: _roleKey, value: role);
    if (username != null) {
      await _storage.write(key: _usernameKey, value: username);
    }
  }

  Future<String?> readToken() => _storage.read(key: _tokenKey);
  Future<String?> readRole() => _storage.read(key: _roleKey);
  Future<String?> readUsername() => _storage.read(key: _usernameKey);

  Future<void> clear() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _roleKey);
    await _storage.delete(key: _usernameKey);
  }
}
