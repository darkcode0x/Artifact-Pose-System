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

  Future<User> get(String id) async {
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

  Future<User> update(
    String id, {
    String? password,
    UserRole? role,
    String? fullName,
    int? age,
    String? email,
    String? phone,
  }) async {
    final patch = <String, dynamic>{};
    if (password != null && password.isNotEmpty) patch['password'] = password;
    if (role != null) patch['role'] = role.wireValue;
    if (fullName != null) patch['full_name'] = fullName;
    if (age != null) patch['age'] = age;
    if (email != null) patch['email'] = email;
    if (phone != null) patch['phone'] = phone;

    final body = await _api.patch('/api/v1/users/$id', body: patch);
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> updateMe({
    String? fullName,
    int? age,
    String? email,
    String? phone,
    String? password,
  }) async {
    final patch = <String, dynamic>{};
    if (fullName != null) patch['full_name'] = fullName;
    if (age != null) patch['age'] = age;
    if (email != null) patch['email'] = email;
    if (phone != null) patch['phone'] = phone;
    if (password != null && password.isNotEmpty) patch['password'] = password;

    final body = await _api.patch('/api/v1/users/me', body: patch);
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<void> delete(String id) async {
    await _api.delete('/api/v1/users/$id');
  }

  Future<User> toggleActive(String id) async {
    final body = await _api.patch('/api/v1/users/$id/toggle-active');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<User> resetPassword(String id) async {
    final body = await _api.post('/api/v1/users/$id/reset-password');
    return User.fromJson(body as Map<String, dynamic>);
  }

  Future<void> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    await _api.post('/api/v1/users/me/change-password', body: {
      'old_password': oldPassword,
      'new_password': newPassword,
    });
  }
}
