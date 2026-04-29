import '../models/user.dart';
import 'api_client.dart';

class UserService {
  final ApiClient _api;

  UserService(this._api);

  Future<User> me() async {
    final body = await _api.get('/api/v1/users/me');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<List<User>> list() async {
    final body = await _api.get('/api/v1/users');
    if (body is! List) return const [];
    return body
        .whereType<Map<String, dynamic>>()
        .map(User.fromJson)
        .toList();
  }

  Future<User> get(int id) async {
    final body = await _api.get('/api/v1/users/$id');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> create({
    required String username,
    required String password,
    UserRole role = UserRole.operator,
  }) async {
    final body = await _api.post('/api/v1/users', body: {
      'username': username,
      'password': password,
      'role': role.wireValue,
    });
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> update(
    int id, {
    String? password,
    UserRole? role,
  }) async {
    final patch = <String, dynamic>{};
    if (password != null && password.isNotEmpty) patch['password'] = password;
    if (role != null) patch['role'] = role.wireValue;

    final body = await _api.patch('/api/v1/users/$id', body: patch);
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<void> delete(int id) async {
    await _api.delete('/api/v1/users/$id');
  }

  Future<User> toggleActive(int id) async {
    final body = await _api.patch('/api/v1/users/$id/toggle-active');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> resetPassword(int id) async {
    final body = await _api.post('/api/v1/users/$id/reset-password');
    return User.fromJson(body as Map<String, dynamic>);
  }
}
