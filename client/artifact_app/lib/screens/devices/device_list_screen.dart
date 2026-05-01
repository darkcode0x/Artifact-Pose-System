import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/iot_device.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_client.dart';
import '../../services/device_service.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'device_detail_screen.dart';

class DeviceListScreen extends StatefulWidget {
  const DeviceListScreen({super.key});

  @override
  State<DeviceListScreen> createState() => _DeviceListScreenState();
}

class _DeviceListScreenState extends State<DeviceListScreen> {
  late DeviceService _service;
  late Future<List<IotDevice>> _devicesFuture;

  @override
  void initState() {
    super.initState();
    _service = DeviceService(context.read<ApiClient>());
    _loadDevices();
  }

  void _loadDevices() {
    setState(() {
      _devicesFuture = _service.list();
    });
  }

  Future<void> _refresh() async {
    _loadDevices();
    await _devicesFuture;
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
              decoration: const InputDecoration(
                labelText: 'Device Code (Unique)',
                hintText: 'e.g. pi-cam-01',
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: descController,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Add')),
        ],
      ),
    );

    if (confirm != true) return;
    final code = codeController.text.trim();
    if (code.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Device code is required')),
        );
      }
      return;
    }
    try {
      await _service.create(code, description: descController.text.trim());
      _refresh();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    // Both Admin and Operator can add devices.
    final canAdd = auth.isAdmin || auth.role == 'operator';

    return Scaffold(
      appBar: AppBar(
        title: const Text('IoT Devices'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: FutureBuilder<List<IotDevice>>(
            future: _devicesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return ErrorStateView(
                  message: 'Could not load devices: ${snapshot.error}',
                  onRetry: _refresh,
                );
              }
              final devices = snapshot.data ?? const [];
              if (devices.isEmpty) {
                return ListView(
                  children: const [
                    SizedBox(height: 80),
                    EmptyStateView(
                      icon: Icons.devices_other_outlined,
                      title: 'No devices registered',
                      subtitle:
                          'Tap "Add Device" to register a new IoT device.',
                    ),
                  ],
                );
              }
              return ListView.separated(
                itemCount: devices.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, i) => _DeviceCard(
                  device: devices[i],
                  onTap: () async {
                    await Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DeviceDetailScreen(
                          device: devices[i],
                          service: _service,
                        ),
                      ),
                    );
                    _refresh();
                  },
                ),
              );
            },
          ),
        ),
      ),
      floatingActionButton: canAdd
          ? FloatingActionButton.extended(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              onPressed: _addDevice,
              label: const Text('Add Device'),
              icon: const Icon(Icons.add),
            )
          : null,
    );
  }
}

class _DeviceCard extends StatelessWidget {
  final IotDevice device;
  final VoidCallback onTap;

  const _DeviceCard({required this.device, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: device.isOnline
              ? Colors.green.withOpacity(0.1)
              : Colors.grey.withOpacity(0.1),
          child: Icon(
            Icons.router,
            color: device.isOnline ? Colors.green : Colors.grey,
          ),
        ),
        title: Text(
          device.deviceCode,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text('Status: ${device.status.name.toUpperCase()}'),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
