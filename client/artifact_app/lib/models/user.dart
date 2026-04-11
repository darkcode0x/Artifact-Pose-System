class LoginResponse {
  final String accessToken;
  final String role;

  LoginResponse({required this.accessToken, required this.role});

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      accessToken: json['access_token'],
      role: json['role'],
    );
  }
}
