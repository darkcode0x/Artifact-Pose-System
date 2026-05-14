import 'package:flutter/material.dart';

import '../../models/iot_device.dart';
import '../../services/api_client.dart';
import '../../services/device_service.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class DeviceDetailScreen extends StatefulWidget {
  final IotDevice device;
  final DeviceService service;

  const DeviceDetailScreen({
    super.key,
    required this.device,
    required this.service,
  });

  @override
  State<DeviceDetailScreen> createState() => _DeviceDetailScreenState();
}

class _DeviceDetailScreenState extends State<DeviceDetailScreen> {
  late IotDevice _currentDevice;
  List<Map<String, dynamic>> _acks = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _currentDevice = widget.device;
    _refresh();
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // Use deviceCode (MQTT identifier: dev-bbb742d369) not DB hex device_id
      final acks =
          await widget.service.acks(_currentDevice.deviceCode, limit: 20);
      if (mounted) setState(() => _acks = acks);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_currentDevice.deviceCode),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
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
                      _infoRow(
                        'Status',
                        _currentDevice.status.name.toUpperCase(),
                        color: _currentDevice.isOnline
                            ? Colors.green
                            : Colors.grey,
                      ),
                      _infoRow('Device Code', _currentDevice.deviceCode),
                      _infoRow('Description',
                          _currentDevice.description ?? 'No description'),
                      _infoRow('System ID', _currentDevice.deviceId),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Recent Activity',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              const SizedBox(height: 8),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (!_loading && _error != null)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              if (!_loading && _error == null && _acks.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'No activity logs yet.',
                    style: TextStyle(color: AppColors.textMuted),
                  ),
                ),
              ..._acks.map((a) => Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      dense: true,
                      title: Text(a['action']?.toString() ??
                          a['task_id']?.toString() ??
                          'ack'),
                      subtitle: Text(a['timestamp']?.toString() ?? ''),
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
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: TextStyle(fontWeight: FontWeight.bold, color: color),
            ),
          ),
        ],
      ),
    );
  }
}
