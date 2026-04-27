import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../services/api_client.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class DeviceControlScreen extends StatefulWidget {
  const DeviceControlScreen({super.key});

  @override
  State<DeviceControlScreen> createState() => _DeviceControlScreenState();
}

class _DeviceControlScreenState extends State<DeviceControlScreen> {
  static const _defaultDeviceId = 'dev-bbb742d369';
  static const _defaultArtifactId = 'artifact_demo_001';

  final _deviceIdCtrl = TextEditingController(text: _defaultDeviceId);
  final _artifactIdCtrl = TextEditingController(text: _defaultArtifactId);
  final _baselineCtrl = TextEditingController(text: '100');

  String? _statusText;
  bool _loading = false;
  bool? _mqttConnected;

  @override
  void initState() {
    super.initState();
    _checkMqtt();
  }

  @override
  void dispose() {
    _deviceIdCtrl.dispose();
    _artifactIdCtrl.dispose();
    _baselineCtrl.dispose();
    super.dispose();
  }

  ApiClient get _api => context.read<ApiClient>();

  Future<void> _checkMqtt() async {
    try {
      final res = await _api.mqttHealth();
      // Response: {"state": {"connected": true, ...}, ...}
      final state = res['state'];
      final connected = state is Map
          ? state['connected'] == true
          : res['mqtt_connected'] == true;
      if (mounted) setState(() => _mqttConnected = connected);
    } catch (_) {
      if (mounted) setState(() => _mqttConnected = false);
    }
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() action) async {
    setState(() {
      _loading = true;
      _statusText = null;
    });
    try {
      final res = await action();
      final ok = res['ok'] == true;
      final mode = res['mode'] ?? '';
      final taskId = res['task_id'] ?? '';
      final published = res['published'] == true;
      setState(() => _statusText = ok
          ? '✓ Command sent\nMode: $mode\nPublished: $published\nTask: $taskId'
          : 'Error: ${res['detail'] ?? res.toString()}');
    } catch (e) {
      setState(() => _statusText = 'Error: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _checkStatus() async {
    setState(() {
      _loading = true;
      _statusText = null;
    });
    try {
      final res = await _api.deviceStatus(_deviceIdCtrl.text.trim());
      setState(() => _statusText = _formatStatus(res));
    } catch (e) {
      setState(() => _statusText = 'Error: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _formatStatus(Map<String, dynamic> s) {
    final buf = StringBuffer();
    buf.writeln('Device: ${s['device_id'] ?? '-'}');
    buf.writeln('Online: ${s['online'] ?? '-'}');
    buf.writeln('Last seen: ${s['last_seen'] ?? '-'}');
    if (s['last_ack'] != null) buf.writeln('Last ack: ${s['last_ack']}');
    return buf.toString().trim();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Device Control'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh MQTT status',
            onPressed: _checkMqtt,
          ),
        ],
      ),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              // ── MQTT status badge ──────────────────────────────────────
              _MqttBadge(connected: _mqttConnected),
              const SizedBox(height: 20),

              // ── Config fields ──────────────────────────────────────────
              Text('Device Settings',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 10),
              TextField(
                controller: _deviceIdCtrl,
                decoration: const InputDecoration(
                  labelText: 'Device ID',
                  hintText: 'dev-bbb742d369',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _artifactIdCtrl,
                decoration: const InputDecoration(
                  labelText: 'Artifact ID',
                  hintText: 'artifact_demo_001',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _baselineCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Stereo baseline (mm)',
                  hintText: '100',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 24),

              // ── Actions ────────────────────────────────────────────────
              Text('Workflow Commands',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),

              _CommandButton(
                icon: Icons.grid_on,
                label: 'Start Stereo Initialization',
                subtitle: 'Pi chụp cặp ảnh stereo → tạo golden pose',
                color: AppColors.primary,
                loading: _loading,
                onPressed: () => _run(() => _api.startInitialization(
                      deviceId: _deviceIdCtrl.text.trim(),
                      artifactId: _artifactIdCtrl.text.trim(),
                      baselineMm: double.tryParse(_baselineCtrl.text) ?? 100.0,
                    )),
              ),
              const SizedBox(height: 10),

              _CommandButton(
                icon: Icons.align_horizontal_center,
                label: 'Start Alignment',
                subtitle: 'Bắt đầu vòng căn chỉnh tự động',
                color: Colors.teal,
                loading: _loading,
                onPressed: () => _run(() => _api.startAlignment(
                      deviceId: _deviceIdCtrl.text.trim(),
                      artifactId: _artifactIdCtrl.text.trim(),
                    )),
              ),
              const SizedBox(height: 10),

              _CommandButton(
                icon: Icons.camera_alt,
                label: 'Request Capture',
                subtitle: 'Chụp ảnh alignment đơn lẻ',
                color: Colors.indigo,
                loading: _loading,
                onPressed: () => _run(() => _api.captureRequest(
                      deviceId: _deviceIdCtrl.text.trim(),
                      artifactId: _artifactIdCtrl.text.trim(),
                    )),
              ),
              const SizedBox(height: 10),

              _CommandButton(
                icon: Icons.info_outline,
                label: 'Check Device Status',
                subtitle: 'Xem trạng thái Pi',
                color: Colors.grey.shade700,
                loading: _loading,
                onPressed: _checkStatus,
              ),
              const SizedBox(height: 20),

              // ── Result panel ───────────────────────────────────────────
              if (_loading)
                const Center(child: CircularProgressIndicator()),
              if (!_loading && _statusText != null)
                Card(
                  color: _statusText!.startsWith('Error')
                      ? Colors.red.shade50
                      : Colors.green.shade50,
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Text(
                      _statusText!,
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: _statusText!.startsWith('Error')
                            ? Colors.red.shade800
                            : Colors.green.shade800,
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 20),

              // ── Note about golden pose ─────────────────────────────────
              Card(
                color: Colors.amber.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        const Icon(Icons.warning_amber, color: Colors.orange),
                        const SizedBox(width: 8),
                        Text('Stereo Initialization Note',
                            style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.orange.shade800)),
                      ]),
                      const SizedBox(height: 8),
                      const Text(
                        'Trước khi chạy Stereo Initialization, phải đặt '
                        'ChArUco diamond marker (4×4 ArUco) trước vật thể. '
                        'File marker để in: diamond_marker_print.png trong server/data/',
                        style: TextStyle(fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Widgets ────────────────────────────────────────────────────────────────

class _MqttBadge extends StatelessWidget {
  final bool? connected;
  const _MqttBadge({required this.connected});

  @override
  Widget build(BuildContext context) {
    if (connected == null) {
      return const Row(children: [
        SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2)),
        SizedBox(width: 8),
        Text('Checking MQTT…'),
      ]);
    }
    final ok = connected!;
    return Row(children: [
      Icon(ok ? Icons.wifi : Icons.wifi_off,
          color: ok ? Colors.green : Colors.red, size: 20),
      const SizedBox(width: 8),
      Text(
        ok ? 'MQTT connected' : 'MQTT disconnected',
        style: TextStyle(
          color: ok ? Colors.green.shade700 : Colors.red.shade700,
          fontWeight: FontWeight.w600,
        ),
      ),
    ]);
  }
}

class _CommandButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final Color color;
  final bool loading;
  final VoidCallback onPressed;

  const _CommandButton({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.color,
    required this.loading,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: color,
        foregroundColor: Colors.white,
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      onPressed: loading ? null : onPressed,
      child: Row(children: [
        Icon(icon, size: 22),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 14)),
              Text(subtitle,
                  style:
                      const TextStyle(fontSize: 12, color: Colors.white70)),
            ],
          ),
        ),
      ]),
    );
  }
}
