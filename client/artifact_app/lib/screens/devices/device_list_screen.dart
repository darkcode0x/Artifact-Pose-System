import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/iot_device.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_client.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'device_detail_screen.dart';

class DeviceListScreen extends StatefulWidget {
  const DeviceListScreen({super.key});

  @override
  State<DeviceListScreen> createState() => _DeviceListScreenState();
}

class _DeviceListScreenState extends State<DeviceListScreen> {
  late Future<List<IotDevice>> _devicesFuture;

  @override
  void initState() {
    super.initState();
    _loadDevices();
  }

  void _loadDevices() {
    final api = context.read<ApiClient>();
    setState(() {
      _devicesFuture = api.get('/api/v1/devices').then((dynamic body) {
        if (body is List) {
          return body.map((json) => IotDevice.fromJson(json as Map<String, dynamic>)).toList();
        }
        return <IotDevice>[];
      });
    });
  }

  Future<void> _addDevice() async {
    final codeController = TextEditingController();
    final descController = TextEditingController();

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add New Device'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: codeController,
              decoration: const InputDecoration(labelText: 'Device Code (Unique)', hintText: 'e.g. pi-cam-01'),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: descController,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Add')),
        ],
      ),
    );

    if (confirm == true && codeController.text.isNotEmpty) {
      try {
        final api = context.read<ApiClient>();
        await api.post('/api/v1/devices', body: {
          'device_code': codeController.text.trim(),
          'description': descController.text.trim(),
        });
        _loadDevices();
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    // Cả Admin và Operator đều có quyền thêm thiết bị (CRU)
    final canAdd = auth.isAdmin || auth.role == 'operator';

    return Scaffold(
      appBar: AppBar(
        title: const Text('IoT Devices'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadDevices),
        ],
      ),
      body: ResponsiveBody(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<List<IotDevice>>(
          future: _devicesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError) return Center(child: Text('Error: ${snapshot.error}'));
            
            final devices = snapshot.data ?? [];
            if (devices.isEmpty) return const Center(child: Text('No devices registered.'));

            return ListView.separated(
              itemCount: devices.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final device = devices[index];
                return Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: device.isOnline ? Colors.green.withOpacity(0.1) : Colors.grey.withOpacity(0.1),
                      child: Icon(Icons.router, color: device.isOnline ? Colors.green : Colors.grey),
                    ),
                    title: Text(device.deviceCode, style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text('Status: ${device.status.name.toUpperCase()}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => DeviceDetailScreen(device: device)),
                      );
                      _loadDevices();
                    },
                  ),
                );
              },
            );
          },
        ),
      ),
      floatingActionButton: canAdd ? FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        onPressed: _addDevice,
        label: const Text('Add Device'),
        icon: const Icon(Icons.add),
      ) : null,
    );
  }
}
