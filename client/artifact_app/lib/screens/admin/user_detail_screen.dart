import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../models/user.dart';
import '../../services/api_client.dart';
import '../../theme.dart';

class UserDetailScreen extends StatefulWidget {
  final User user;

  const UserDetailScreen({super.key, required this.user});

  @override
  State<UserDetailScreen> createState() => _UserDetailScreenState();
}

class _UserDetailScreenState extends State<UserDetailScreen> {
  late User _currentUser;
  bool _isBusy = false;

  @override
  void initState() {
    super.initState();
    _currentUser = widget.user;
  }

  Future<void> _toggleStatus() async {
    setState(() => _isBusy = true);
    try {
      final api = context.read<ApiClient>();
      final response = await api.patch('/api/v1/users/${_currentUser.userId}/toggle-active');
      if (response is Map<String, dynamic>) {
        setState(() => _currentUser = User.fromJson(response));
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Status updated')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }

  Future<void> _resetPassword() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reset Password'),
        content: const Text('Are you sure you want to reset this user\'s password to "111111"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Reset')),
        ],
      ),
    );

    if (confirm == true) {
      setState(() => _isBusy = true);
      try {
        final api = context.read<ApiClient>();
        await api.post('/api/v1/users/${_currentUser.userId}/reset-password');
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Password reset to 111111 successful')));
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      } finally {
        if (mounted) setState(() => _isBusy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final DateFormat formatter = DateFormat('yyyy-MM-dd HH:mm:ss');
    final roleName = _currentUser.role.name.toUpperCase();

    return Scaffold(
      appBar: AppBar(title: const Text('User Details')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: CircleAvatar(
                radius: 50,
                backgroundColor: _currentUser.role == UserRole.admin ? Colors.orange : AppColors.primary,
                child: const Icon(Icons.person, size: 50, color: Colors.white),
              ),
            ),
            const SizedBox(height: 24),
            _infoTile(Icons.person_outline, 'Username', _currentUser.username),
            _infoTile(Icons.badge_outlined, 'Role', roleName),
            _infoTile(Icons.toggle_on_outlined, 'Status', _currentUser.isActive ? 'Active' : 'Inactive', color: _currentUser.isActive ? Colors.green : Colors.grey),
            _infoTile(Icons.calendar_today_outlined, 'Created At', formatter.format(_currentUser.createdAt)),
            const SizedBox(height: 32),
            
            // Nút Khóa/Mở khóa
            if (_currentUser.role != UserRole.admin)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isBusy ? null : _toggleStatus,
                  icon: Icon(_currentUser.isActive ? Icons.block : Icons.check_circle_outline),
                  label: Text(_currentUser.isActive ? 'Deactivate User' : 'Activate User'),
                  style: ElevatedButton.styleFrom(backgroundColor: _currentUser.isActive ? Colors.red : Colors.green, foregroundColor: Colors.white),
                ),
              ),
            
            const SizedBox(height: 12),
            
            // Nút Reset Password
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isBusy ? null : _resetPassword,
                icon: const Icon(Icons.lock_reset),
                label: const Text('Reset Password (111111)'),
                style: OutlinedButton.styleFrom(foregroundColor: AppColors.primary),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoTile(IconData icon, String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        children: [
          Icon(icon, color: AppColors.primary),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12)),
              Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
            ],
          ),
        ],
      ),
    );
  }
}
