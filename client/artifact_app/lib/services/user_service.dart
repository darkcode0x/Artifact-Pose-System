import '../models/user.dart';
import 'api_client.dart';

class UserService {
  final ApiClient _api;

  UserService(this._api);

  Future<AppUser> me() async {
    final body = await _api.get('/api/v1/users/me');
    return AppUser.fromJson(body as Map<String, dynamic>);
  }

  Future<List<AppUser>> list() async {
    final body = await _api.get('/api/v1/users');
    if (body is! List) return const [];
    return body
        .whereType<Map<String, dynamic>>()
        .map(AppUser.fromJson)
        .toList();
  }

  Future<AppUser> create({
    required String username,
    required String password,
    String role = 'user',
  }) async {
    final body = await _api.post('/api/v1/users', body: {
      'username': username,
      'password': password,
      'role': role,
    });
    return AppUser.fromJson(body as Map<String, dynamic>);
  }

  Future<AppUser> update(
    int id, {
    String? password,
    String? role,
  }) async {
    final patch = <String, dynamic>{};
    if (password != null && password.isNotEmpty) patch['password'] = password;
    if (role != null) patch['role'] = role;

    final body = await _api.patch('/api/v1/users/$id', body: patch);
    return AppUser.fromJson(body as Map<String, dynamic>);
  }

  Future<void> delete(int id) async {
    await _api.delete('/api/v1/users/$id');
  }

  Future<AppUser> register({
    required String username,
    required String password,
  }) async {
    final body = await _api.post('/api/v1/auth/register', body: {
      'username': username,
      'password': password,
    });
    return AppUser.fromJson(body as Map<String, dynamic>);
  }
}