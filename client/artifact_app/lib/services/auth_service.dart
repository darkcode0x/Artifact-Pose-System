import '../models/login_response.dart';
import 'api_client.dart';
import 'token_storage.dart';

class AuthService {
  final ApiClient _api;
  final TokenStorage _tokens;

  AuthService({required ApiClient api, required TokenStorage tokens})
      : _api = api,
        _tokens = tokens;

  Future<LoginResponse> login(String username, String password) async {
    final body = await _api.post(
      '/api/v1/auth/login',
      body: {'username': username, 'password': password},
    );
    if (body is! Map<String, dynamic>) {
      throw ApiException('Invalid login response format');
    }
    final result = LoginResponse.fromJson(body);
    await _tokens.save(
      token: result.accessToken,
      role: result.role,
      username: username,
    );
    return result;
  }

  Future<void> logout() => _tokens.clear();

  Future<bool> hasPersistedSession() async {
    final token = await _tokens.readToken();
    return token != null && token.isNotEmpty;
  }

  /// Register and immediately log in. Returns the new role.
  Future<LoginResponse> register(String username, String password) async {
    await _api.post(
      '/api/v1/auth/register',
      body: {'username': username, 'password': password},
    );
    return login(username, password);
  }
}
