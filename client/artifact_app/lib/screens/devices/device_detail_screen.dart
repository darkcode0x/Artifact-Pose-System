import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/iot_device.dart';
import '../../services/device_service.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class DeviceDetailScreen extends StatefulWidget {
  final String deviceId;
  final DeviceService service;

  const DeviceDetailScreen({
    super.key,
    required this.deviceId,
    required this.service,
  });

  @override
  State<DeviceDetailScreen> createState() => _DeviceDetailScreenState();
}

class _DeviceDetailScreenState extends State<DeviceDetailScreen> {
  IotDevice? _device;
  List<Map<String, dynamic>> _acks = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        widget.service.getStatus(widget.deviceId),
        widget.service.acks(widget.deviceId, limit: 20),
      ]);
      if (!mounted) return;
      setState(() {
        _device = results[0] as IotDevice;
        _acks = results[1] as List<Map<String, dynamic>>;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _sendStop() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.service.sendMoveCommand(widget.deviceId, {'action': 'stop'});
      messenger
          .showSnackBar(const SnackBar(content: Text('Stop command queued')));
      _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.deviceId),
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
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? ErrorStateView(message: _error!, onRetry: _refresh)
                  : ListView(
                      children: [
                        _statusCard(),
                        const SizedBox(height: 16),
                        SizedBox(
                          height: 48,
                          child: OutlinedButton.icon(
                            onPressed: _sendStop,
                            icon: const Icon(Icons.stop_circle_outlined),
                            label: const Text('Send STOP command'),
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          'Recent acks',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        if (_acks.isEmpty)
                          const Padding(
                            padding: EdgeInsets.all(16),
                            child: Text(
                              'No acknowledgments yet.',
                              style: TextStyle(color: AppColors.textMuted),
                            ),
                          )
                        else
                          ..._acks.map((a) => _ackTile(a)),
                      ],
                    ),
        ),
      ),
    );
  }

  Widget _statusCard() {
    final device = _device;
    final status = device?.status ?? const <String, dynamic>{};
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.circle,
                  size: 14,
                  color: (device?.isOnline ?? false)
                      ? AppColors.statusGood
                      : AppColors.textFaint,
                ),
                const SizedBox(width: 8),
                Text(
                  (device?.isOnline ?? false) ? 'Active' : 'No signal',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (status.isEmpty)
              const Text(
                'No status payload from command service.',
                style: TextStyle(color: AppColors.textMuted),
              )
            else
              SelectableText(
                const JsonEncoder.withIndent('  ').convert(status),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
          ],
        ),
      ),
    );
  }

  Widget _ackTile(Map<String, dynamic> ack) {
    final ts = ack['timestamp'] ?? ack['received_at'];
    String timeLabel = '';
    if (ts is String) {
      final parsed = DateTime.tryParse(ts);
      if (parsed != null) {
        timeLabel = DateFormat('HH:mm:ss dd/MM').format(parsed.toLocal());
      } else {
        timeLabel = ts;
      }
    }
    final action = ack['action'] ?? ack['task_id'] ?? 'ack';
    return Card(
      child: ListTile(
        dense: true,
        title: Text('$action', style: const TextStyle(fontSize: 14)),
        subtitle: timeLabel.isEmpty ? null : Text(timeLabel),
      ),
    );
  }
}
