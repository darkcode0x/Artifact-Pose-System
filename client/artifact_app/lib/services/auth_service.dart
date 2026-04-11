import '../models/login_response.dart';

class AuthService {

  static Future<LoginResponse> login(
      String username, String password) async {

    await Future.delayed(const Duration(seconds: 1));

    if (username == "admin" && password == "123456") {
      return LoginResponse(
        accessToken: "fake_admin_token",
        role: "admin",
      );
    }

    if (username == "user" && password == "123456") {
      return LoginResponse(
        accessToken: "fake_user_token",
        role: "user",
      );
    }

    throw Exception("Invalid credentials");
  }
}