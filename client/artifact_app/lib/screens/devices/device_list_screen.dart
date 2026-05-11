import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/iot_device.dart';
import '../../services/api_client.dart';
import '../../services/device_service.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'device_detail_screen.dart';
import 'device_workflow_screen.dart';

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

  @override
  Widget build(BuildContext context) {
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
                      title: 'No devices yet',
                      subtitle:
                          'Devices register automatically when the Raspberry Pi connects.',
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
                        builder: (_) => DeviceWorkflowScreen(
                          device: devices[i],
                        ),
                      ),
                    );
                    _refresh();
                  },
                  onInfo: () async {
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
    );
  }
}

class _DeviceCard extends StatelessWidget {
  final IotDevice device;
  final VoidCallback onTap;
  final VoidCallback onInfo;

  const _DeviceCard({required this.device, required this.onTap, required this.onInfo});

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
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: 'Device details',
              icon: const Icon(Icons.info_outline, color: AppColors.textMuted),
              onPressed: onInfo,
            ),
            const Icon(Icons.play_circle_outline, color: AppColors.primary),
          ],
        ),
        onTap: onTap,
      ),
    );
  }
}
