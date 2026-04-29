class AppUser {
  final int id;
  final String username;
  final String role;

  const AppUser({
    required this.id,
    required this.username,
    required this.role,
  });

  bool get isAdmin => role == 'admin';

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: (json['id'] as num).toInt(),
      username: json['username'] as String,
      role: (json['role'] ?? 'user') as String,
    );
  }
}