import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/login_response.dart';
import 'api_config.dart';

class AuthService {

  static Future<LoginResponse> login(
      String username, String password) async {
    final response = await http.post(
      ApiConfig.uri('/api/v1/auth/login'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'username': username,
        'password': password,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Login failed: ${response.statusCode}');
    }

    final body = jsonDecode(response.body);
    if (body is! Map<String, dynamic>) {
      throw Exception('Invalid login response format');
    }

    return LoginResponse.fromJson(body);
  }
}
