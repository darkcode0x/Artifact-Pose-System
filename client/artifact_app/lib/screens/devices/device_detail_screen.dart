import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/iot_device.dart';
import '../../services/device_service.dart';
import '../../providers/auth_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class DeviceDetailScreen extends StatefulWidget {
  final IotDevice device;
  const DeviceDetailScreen({super.key, required this.device});

  @override
  State<DeviceDetailScreen> createState() => _DeviceDetailScreenState();
}

class _DeviceDetailScreenState extends State<DeviceDetailScreen> {
  late IotDevice _currentDevice;
  List<Map<String, dynamic>> _acks = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _currentDevice = widget.device;
    _refresh();
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      final service = context.read<DeviceService>();
      final results = await service.acks(_currentDevice.deviceId, limit: 20);
      if (mounted) setState(() => _acks = results);
    } catch (e) {
      debugPrint('Error fetching acks: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _editDevice() async {
    final descController = TextEditingController(text: _currentDevice.description);
    final auth = context.read<AuthProvider>();
    String? selectedStatus = _currentDevice.status.name;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Chỉnh sửa thiết bị'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: descController,
              decoration: const InputDecoration(labelText: 'Mô tả'),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              value: selectedStatus,
              items: ['online', 'offline']
                  .map((s) => DropdownMenuItem(value: s, child: Text(s.toUpperCase())))
                  .toList(),
              onChanged: (v) => selectedStatus = v,
              decoration: const InputDecoration(labelText: 'Trạng thái'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Hủy')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Lưu')),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final service = context.read<DeviceService>();
        await service.update(
          _currentDevice.deviceId,
          description: descController.text.trim(),
          status: selectedStatus,
        );
        _refresh();
        if (mounted) {
           ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cập nhật thành công!')));
        }
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Lỗi: $e')));
      }
    }
  }

  Future<void> _deleteDevice() async {
    final auth = context.read<AuthProvider>();
    if (!auth.isAdmin) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Chỉ Admin mới có quyền xóa thiết bị')));
      return;
    }

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Xóa thiết bị'),
        content: Text('Bạn có chắc chắn muốn xóa thiết bị "${_currentDevice.deviceCode}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Hủy')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await context.read<DeviceService>().delete(_currentDevice.deviceId);
        if (mounted) Navigator.pop(context, true);
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Lỗi: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      appBar: AppBar(
        title: Text(_currentDevice.deviceCode),
        actions: [
          IconButton(
            tooltip: 'Chỉnh sửa',
            icon: const Icon(Icons.edit_outlined), 
            onPressed: _editDevice
          ),
          if (auth.isAdmin)
            IconButton(
              tooltip: 'Xóa',
              icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
              onPressed: _deleteDevice,
            ),
        ],
      ),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      _infoRow('Trạng thái', _currentDevice.status.name.toUpperCase(), color: _currentDevice.isOnline ? Colors.green : Colors.grey),
                      _infoRow('Mã thiết bị', _currentDevice.deviceCode),
                      _infoRow('Mô tả', _currentDevice.description ?? 'Không có mô tả'),
                      _infoRow('ID hệ thống', _currentDevice.deviceId),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              const Text('Hoạt động gần đây', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 8),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (!_loading && _acks.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Chưa có nhật ký hoạt động.', style: TextStyle(color: AppColors.textMuted)),
                ),
              ..._acks.map((a) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  dense: true,
                  title: Text(a['action'] ?? 'Yêu cầu chụp ảnh'),
                  subtitle: Text(a['timestamp'] ?? ''),
                  leading: const Icon(Icons.history, size: 20),
                ),
              )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textMuted)),
          Text(value, style: TextStyle(fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }
}
