import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/user.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_client.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'change_password_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _ageController = TextEditingController();
  
  bool _isBusy = false;
  bool _isEditing = false;

  @override
  void initState() {
    super.initState();
    _fillData();
  }

  void _fillData() {
    final user = context.read<AuthProvider>().currentUser;
    if (user != null) {
      _nameController.text = user.fullName ?? '';
      _emailController.text = user.email ?? '';
      _phoneController.text = user.phone ?? '';
      _ageController.text = user.age?.toString() ?? '';
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _ageController.dispose();
    super.dispose();
  }

  Future<void> _updateProfile() async {
    setState(() => _isBusy = true);
    try {
      final api = context.read<ApiClient>();
      final auth = context.read<AuthProvider>();
      
      await api.patch('/api/v1/users/me', body: {
        'current_username': auth.username,
        'full_name': _nameController.text.trim(),
        'email': _emailController.text.trim(),
        'phone': _phoneController.text.trim(),
        'age': int.tryParse(_ageController.text) ?? 0,
      });
      
      await auth.fetchFullProfile(); 
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Thông tin cá nhân đã được cập nhật!')),
        );
        setState(() => _isEditing = false);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Lỗi: $e')));
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.currentUser;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Hồ sơ cá nhân'),
        actions: [
          IconButton(
            icon: Icon(_isEditing ? Icons.close : Icons.edit_outlined),
            onPressed: () => setState(() => _isEditing = !_isEditing),
          )
        ],
      ),
      body: ResponsiveBody(
        padding: const EdgeInsets.all(20),
        child: ListView(
          children: [
            Center(
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 50,
                    backgroundColor: AppColors.primary.withOpacity(0.1),
                    child: const Icon(Icons.person, size: 60, color: AppColors.primary),
                  ),
                  const SizedBox(height: 12),
                  Text(user?.fullName ?? auth.username ?? 'User', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                  Text(auth.role?.toUpperCase() ?? '', style: const TextStyle(color: AppColors.textMuted)),
                ],
              ),
            ),
            const SizedBox(height: 32),
            
            _sectionTitle('Thông tin chi tiết'),
            const SizedBox(height: 16),
            _infoField('Họ và Tên', _nameController, Icons.badge_outlined, enabled: _isEditing),
            _infoField('Email', _emailController, Icons.email_outlined, enabled: _isEditing),
            _infoField('Số điện thoại', _phoneController, Icons.phone_android_outlined, enabled: _isEditing),
            _infoField('Tuổi', _ageController, Icons.cake_outlined, isNumber: true, enabled: _isEditing),
            
            if (_isEditing) ...[
              const SizedBox(height: 12),
              SizedBox(
                height: 50,
                child: ElevatedButton.icon(
                  onPressed: _isBusy ? null : _updateProfile,
                  icon: const Icon(Icons.save),
                  label: const Text('Lưu thay đổi'),
                ),
              ),
            ],
            
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 24),
            _sectionTitle('Bảo mật'),
            const SizedBox(height: 16),
            Card(
              margin: EdgeInsets.zero,
              child: ListTile(
                leading: const Icon(Icons.lock_reset, color: AppColors.primary),
                title: const Text('Đổi mật khẩu'),
                subtitle: const Text('Cập nhật mật khẩu định kỳ để bảo vệ tài khoản'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const ChangePasswordScreen()),
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
            Card(
              margin: EdgeInsets.zero,
              child: ListTile(
                leading: const Icon(Icons.logout, color: Colors.red),
                title: const Text('Đăng xuất', style: TextStyle(color: Colors.red)),
                onTap: () => auth.logout(),
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String title) => Text(
    title, 
    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.primary)
  );

  Widget _infoField(String label, TextEditingController ctrl, IconData icon, {bool isPass = false, bool isNumber = false, bool enabled = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextField(
        controller: ctrl,
        obscureText: isPass,
        enabled: enabled,
        keyboardType: isNumber ? TextInputType.number : TextInputType.text,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          filled: !enabled,
          fillColor: enabled ? null : Colors.grey.withOpacity(0.05),
        ),
      ),
    );
  }
}
