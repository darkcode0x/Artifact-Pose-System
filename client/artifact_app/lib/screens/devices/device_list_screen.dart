import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/iot_device.dart';
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
  late Future<List<IotDevice>> _future;

  @override
  void initState() {
    super.initState();
    _service = DeviceService(context.read<ApiClient>());
    _future = _service.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _service.list());
    await _future;
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
            future: _future,
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
                      title: 'No devices registered yet',
                      subtitle:
                          'Devices register themselves via POST /devices/get_device_id',
                    ),
                  ],
                );
              }
              return ListView.separated(
                itemCount: devices.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, i) => _DeviceCard(
                  device: devices[i],
                  service: _service,
                  onTap: () => _openDetail(devices[i]),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Future<void> _openDetail(IotDevice device) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) =>
            DeviceDetailScreen(deviceId: device.deviceId, service: _service),
      ),
    );
    _refresh();
  }
}

class _DeviceCard extends StatelessWidget {
  final IotDevice device;
  final DeviceService service;
  final VoidCallback onTap;

  const _DeviceCard({
    required this.device,
    required this.service,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final online = device.isOnline;
    return Card(
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor:
              online ? AppColors.statusGood : AppColors.surfaceMuted,
          child: Icon(
            Icons.developer_board,
            color: online ? Colors.white : AppColors.textMuted,
          ),
        ),
        title: Text(
          device.deviceId,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          device.machineHash.isEmpty
              ? (online ? 'Online' : 'No recent activity')
              : 'machine: ${device.machineHash}',
        ),
        trailing: Icon(
          Icons.circle,
          size: 12,
          color: online ? AppColors.statusGood : AppColors.textFaint,
        ),
        onTap: onTap,
      ),
    );
  }
}
