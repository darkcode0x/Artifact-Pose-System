import 'package:flutter/material.dart';

import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'add_user_screen.dart';

class UserListScreen extends StatefulWidget {
  const UserListScreen({super.key});

  @override
  State<UserListScreen> createState() => _UserListScreenState();
}

class _UserListScreenState extends State<UserListScreen> {
  // NOTE: backend currently exposes no /users CRUD; this view is a placeholder.
  final List<Map<String, String>> users = const [
    {'username': 'admin', 'role': 'admin'},
    {'username': 'staff1', 'role': 'user'},
    {'username': 'staff2', 'role': 'user'},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('User Management')),
      body: ResponsiveBody(
        padding: const EdgeInsets.all(16),
        child: ListView.separated(
          itemCount: users.length,
          separatorBuilder: (_, __) => const SizedBox(height: 12),
          itemBuilder: (context, index) => _userCard(users[index]),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.person_add),
        label: const Text('Add user'),
        onPressed: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const AddUserScreen()),
        ),
      ),
    );
  }

  Widget _userCard(Map<String, String> user) {
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        leading: const CircleAvatar(
          backgroundColor: AppColors.primary,
          child: Icon(Icons.person, color: Colors.white),
        ),
        title: Text(
          user['username'] ?? '',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text('Role: ${user['role'] ?? ''}'),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}
