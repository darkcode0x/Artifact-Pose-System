import '../models/user.dart';
import 'api_client.dart';

class UserService {
  final ApiClient _api;

  UserService(this._api);

  Future<List<User>> list() async {
    final body = await _api.get('/api/v1/users');
    if (body is! List) return [];
    return body.map((json) => User.fromJson(json as Map<String, dynamic>)).toList();
  }

  Future<User> get(int id) async {
    final body = await _api.get('/api/v1/users/$id');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> create({
    required String username,
    required String password,
    required UserRole role,
  }) async {
    final body = await _api.post('/api/v1/users', body: {
      'username': username,
      'password': password,
      'role': role.wireValue,
    });
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> toggleActive(int id) async {
    final body = await _api.patch('/api/v1/users/$id/toggle-active');
    return User.fromJson(body as Map<String, dynamic>);
  }
}
