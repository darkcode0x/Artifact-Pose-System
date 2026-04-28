enum UserRole {
  admin,
  operator;

  static UserRole fromWire(String? value) {
    if (value == 'admin') return UserRole.admin;
    return UserRole.operator;
  }

  String get wireValue => name;
}

class User {
  final int userId;
  final String username;
  final UserRole role;
  final bool isActive;
  final DateTime createdAt;

  User({
    required this.userId,
    required this.username,
    required this.role,
    required this.isActive,
    required this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userId: json['user_id'] as int,
      username: json['username'] as String,
      role: UserRole.fromWire(json['role'] as String?),
      isActive: json['is_active'] ?? true,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
