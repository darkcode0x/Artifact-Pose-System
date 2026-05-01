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

  Future<User> get(String id) async { // Changed to String
    final body = await _api.get('/api/v1/users/$id');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> create({
    required String username,
    required String password,
    required UserRole role,
    String? fullName,
    int? age,
    String? email,
    String? phone,
  }) async {
    final body = await _api.post('/api/v1/users', body: {
      'username': username,
      'password': password,
      'role': role.wireValue,
      'full_name': fullName,
      'age': age,
      'email': email,
      'phone': phone,
    });
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> toggleActive(String id) async { // Changed to String
    final body = await _api.patch('/api/v1/users/$id/toggle-active');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<void> resetPassword(String id) async { // Changed to String
    await _api.post('/api/v1/users/$id/reset-password');
  }

  Future<void> changePassword({
    required String username,
    required String oldPassword,
    required String newPassword,
  }) async {
    await _api.post('/api/v1/users/change-password', body: {
      'username': username,
      'old_password': oldPassword,
      'new_password': newPassword,
    });
  }
}
