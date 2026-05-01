enum UserRole {
  admin,
  operator;

  static UserRole fromWire(String? value) {
    final v = value?.toLowerCase();
    if (v == 'admin') return UserRole.admin;
    return UserRole.operator;
  }

  String get wireValue => name;
}

class User {
  final String userId; // VARCHAR(6) from PostgreSQL
  final String username;
  final UserRole role;
  final bool isActive;
  final DateTime createdAt;
  
  // Profile fields
  final String? fullName;
  final int? age;
  final String? email;
  final String? phone;

  User({
    required this.userId,
    required this.username,
    required this.role,
    required this.isActive,
    required this.createdAt,
    this.fullName,
    this.age,
    this.email,
    this.phone,
  });

  bool get isAdmin => role == UserRole.admin;

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userId: json['user_id']?.toString() ?? '',
      username: json['username'] as String? ?? '',
      role: UserRole.fromWire(json['role'] as String?),
      isActive: json['is_active'] as bool? ?? true,
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ?? DateTime.now(),
      fullName: json['full_name'] as String?,
      age: json['age'] is int ? json['age'] as int : int.tryParse(json['age']?.toString() ?? ''),
      email: json['email'] as String?,
      phone: json['phone'] as String?,
    );
  }
}
