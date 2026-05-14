import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../models/artifact_status.dart';
import '../../models/inspection.dart';
import '../../models/iot_device.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_client.dart';
import '../../services/artifact_service.dart';
import '../../services/device_service.dart';
import '../../services/workflow_service.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../inspect/result_screen.dart';

enum _Phase {
  idle,
  initRunning,
  initDone,
  alignRunning,
  alignDone,
  inspectRunning,
  done,
}

enum _AlignmentFailAction { retry, continueAnyway }

class DeviceWorkflowScreen extends StatefulWidget {
  /// Opened from DeviceListScreen: [device] is already known.
  /// Opened from ArtifactDetailScreen: [device] is null and must be selected.
  final IotDevice? device;
  final String? preselectedArtifactId;

  const DeviceWorkflowScreen({
    super.key,
    this.device,
    this.preselectedArtifactId,
  });

  @override
  State<DeviceWorkflowScreen> createState() => _DeviceWorkflowScreenState();
}

class _PersistedWorkflowState {
  final _Phase phase;
  final List<Map<String, dynamic>> acks;
  final Map<String, dynamic>? latestDeviation;
  final Map<String, dynamic>? initResult;
  final Map<String, dynamic>? alignResult;
  final Inspection? inspectionResult;
  final String? selectedArtifactId;
  final String? selectedDeviceCode;
  final int? initStartTs;
  final int? alignmentStartTs;

  const _PersistedWorkflowState({
    required this.phase,
    required this.acks,
    this.latestDeviation,
    this.initResult,
    this.alignResult,
    this.inspectionResult,
    this.selectedArtifactId,
    this.selectedDeviceCode,
    this.initStartTs,
    this.alignmentStartTs,
  });
}

class _DeviceWorkflowScreenState extends State<DeviceWorkflowScreen> {
  static final Map<String, _PersistedWorkflowState> _stateCache = {};

  static const double _baselineMm = 100.0;
  static const Duration _pollInterval = Duration(seconds: 3);

  late final WorkflowService _workflowService;
  late final ArtifactService _artifactService;
  late final DeviceService _deviceService;

  List<Artifact> _artifacts = [];
  List<IotDevice> _devices = [];

  Artifact? _selectedArtifact;
  IotDevice? _selectedDevice;

  _Phase _phase = _Phase.idle;
  String? _errorMessage;

  Map<String, dynamic>? _initResult;
  Map<String, dynamic>? _alignResult;
  Map<String, dynamic>? _latestDeviation;
  Inspection? _inspectionResult;

  List<Map<String, dynamic>> _acks = [];
  Timer? _pollTimer;
  bool _pollInFlight = false;

  int? _initStartTs;
  int? _alignmentStartTs;
  (int, int)? _alignmentIteration; // (current, max) for live progress display

  bool _hasGoldenPose = false;
  bool _checkingGoldenPose = false;
  bool? _liveDeviceOnline;

  String? _restoredArtifactId;
  String? _restoredDeviceCode;

  IotDevice? get _effectiveDevice => widget.device ?? _selectedDevice;

  bool get _isDeviceOnline =>
      _liveDeviceOnline ?? (_effectiveDevice?.isOnline ?? false);

  bool get _hasRequiredSelection =>
      _effectiveDevice != null && _selectedArtifact != null;

  bool get _canSendDeviceCommand => _hasRequiredSelection && _isDeviceOnline;

  bool get _alignmentCompletedThisSession => _acks.any((ack) {
        final payload = _asStringMap(ack['payload']);
        return payload['action'] == 'alignment_complete';
      });

  bool get _alignmentFailedThisSession => _acks.any((ack) {
        final payload = _asStringMap(ack['payload']);
        return payload['action'] == 'alignment_failed';
      });

  String? get _alignmentFailReason {
    for (final ack in _acks) {
      final payload = _asStringMap(ack['payload']);
      if (payload['action'] == 'alignment_failed') {
        // Reason is echoed by Pi inside the 'result' sub-object.
        // Fallback to top-level 'reason' for safety.
        final result = _asStringMap(payload['result']);
        return (result['reason'] ?? payload['reason'])?.toString();
      }
    }
    return null;
  }

  String get _cacheKey =>
      widget.preselectedArtifactId ?? _effectiveDevice?.deviceCode ?? '';

  @override
  void initState() {
    super.initState();

    final api = context.read<ApiClient>();
    _workflowService = WorkflowService(api);
    _artifactService = ArtifactService(api);
    _deviceService = DeviceService(api);

    _restoreState();
    _loadArtifacts();
    if (widget.device == null) _loadDevices();

    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _refreshDeviceOnlineStatus(),
    );
  }

  @override
  void dispose() {
    _persistState();
    _stopPoll(refreshDevice: false);
    super.dispose();
  }

  void _restoreState() {
    final key = widget.preselectedArtifactId ?? widget.device?.deviceCode ?? '';
    if (key.isEmpty) return;

    final cached = _stateCache[key];
    if (cached == null) return;

    if (cached.phase == _Phase.done) {
      _stateCache.remove(key);
      return;
    }

    _phase = cached.phase == _Phase.inspectRunning
        ? _Phase.alignDone
        : cached.phase;
    _acks = List.of(cached.acks);
    _latestDeviation = cached.latestDeviation;
    _initResult = cached.initResult;
    _alignResult = cached.alignResult;
    _inspectionResult = cached.inspectionResult;
    _initStartTs = cached.initStartTs;
    _alignmentStartTs = cached.alignmentStartTs;
    _restoredArtifactId = cached.selectedArtifactId;
    _restoredDeviceCode = cached.selectedDeviceCode;

    if (_phase == _Phase.initRunning) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _startInitPoll());
    } else if (_phase == _Phase.alignRunning) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _startAlignPoll());
    }
  }

  void _persistState() {
    final key = _cacheKey;
    if (key.isEmpty) return;

    _stateCache[key] = _PersistedWorkflowState(
      phase: _phase,
      acks: List.of(_acks),
      latestDeviation: _latestDeviation,
      initResult: _initResult,
      alignResult: _alignResult,
      inspectionResult: _inspectionResult,
      selectedArtifactId: _selectedArtifact?.id,
      selectedDeviceCode: _selectedDevice?.deviceCode,
      initStartTs: _initStartTs,
      alignmentStartTs: _alignmentStartTs,
    );
  }

  Future<void> _loadDevices() async {
    try {
      final list = await _deviceService.list();
      if (!mounted) return;

      setState(() {
        _devices = list;
        if (_restoredDeviceCode != null) {
          _selectedDevice = _firstOrNull(
            list,
            (device) => device.deviceCode == _restoredDeviceCode,
          );
          _restoredDeviceCode = null;
        }
      });

      if (_selectedDevice != null) {
        unawaited(_refreshDeviceOnlineStatus());
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _devices = []);
    }
  }

  Future<void> _loadArtifacts() async {
    try {
      final list = await _artifactService.list();
      if (!mounted) return;

      setState(() {
        _artifacts = list;

        final targetId = _restoredArtifactId ?? widget.preselectedArtifactId;
        if (targetId != null) {
          _selectedArtifact = _firstOrNull(
            list,
            (artifact) => artifact.id == targetId,
          );
        }
        _restoredArtifactId = null;
      });

      final artifactId = _selectedArtifact?.id;
      if (artifactId != null) await _checkGoldenPose(artifactId);
    } catch (_) {
      if (!mounted) return;
      setState(() => _artifacts = []);
    }
  }

  Future<void> _checkGoldenPose(String artifactId) async {
    setState(() => _checkingGoldenPose = true);

    try {
      final has = await _workflowService.hasGoldenPose(artifactId);
      if (!mounted) return;
      setState(() => _hasGoldenPose = has);
    } catch (_) {
      if (!mounted) return;
      setState(() => _hasGoldenPose = false);
    } finally {
      if (mounted) setState(() => _checkingGoldenPose = false);
    }
  }

  Future<void> _refreshDeviceOnlineStatus() async {
    final deviceCode = _effectiveDevice?.deviceCode;
    if (deviceCode == null) return;

    try {
      final fresh = await _deviceService.getStatus(deviceCode);
      if (!mounted) return;

      if (_effectiveDevice?.deviceCode == deviceCode) {
        setState(() => _liveDeviceOnline = fresh.isOnline);
      }
    } catch (_) {
      // Keep the current status if the status API fails.
    }
  }

  Future<void> _runInitialization() async {
    final device = _effectiveDevice;
    final artifact = _selectedArtifact;

    if (!_validateCanSendCommand(device: device, artifact: artifact)) return;

    setState(() {
      _phase = _Phase.initRunning;
      _errorMessage = null;
      _initResult = null;
      _initStartTs = DateTime.now().millisecondsSinceEpoch;
    });
    _persistState();

    try {
      final result = await _workflowService.startInitialization(
        deviceId: device!.deviceCode,
        artifactId: artifact!.id,
        baselineMm: _baselineMm,
      );
      if (!mounted) return;

      setState(() => _initResult = result);

      if (result['ok'] == true) {
        _startInitPoll();
      } else {
        setState(() {
          _phase = _Phase.idle;
          _errorMessage =
              'Initialization failed: ${result['publish_error'] ?? 'unknown error'}';
        });
      }
      _persistState();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.idle;
        _errorMessage = e.message;
      });
      _persistState();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.idle;
        _errorMessage = e.toString();
      });
      _persistState();
    }
  }

  Future<void> _runAlignment() async {
    final device = _effectiveDevice;
    final artifact = _selectedArtifact;

    if (!_validateCanSendCommand(device: device, artifact: artifact)) return;

    setState(() {
      _phase = _Phase.alignRunning;
      _errorMessage = null;
      _alignResult = null;
      _latestDeviation = null;
      _acks = [];
      _alignmentStartTs = DateTime.now().millisecondsSinceEpoch;
      _alignmentIteration = null;
    });
    _persistState();
    _startAlignPoll();

    try {
      final result = await _workflowService.startAlignment(
        deviceId: device!.deviceCode,
        artifactId: artifact!.id,
      );
      if (!mounted) return;

      setState(() => _alignResult = result);

      if (result['ok'] != true) {
        _stopPoll();
        if (!mounted) return;
        setState(() {
          _phase = _Phase.initDone;
          _errorMessage =
              'Alignment failed: ${result['publish_error'] ?? 'unknown error'}';
        });
      }
      _persistState();
    } on ApiException catch (e) {
      _stopPoll();
      if (!mounted) return;
      setState(() {
        _phase = _Phase.initDone;
        _errorMessage = e.message;
      });
      _persistState();
    } catch (e) {
      _stopPoll();
      if (!mounted) return;
      setState(() {
        _phase = _Phase.initDone;
        _errorMessage = e.toString();
      });
      _persistState();
    }
  }

  void _confirmAlignmentDone() {
    _stopPoll();
    setState(() => _phase = _Phase.alignDone);
    _persistState();
  }

  void _skipInitialization() {
    setState(() {
      _phase = _Phase.initDone;
      _errorMessage = null;
    });
    _persistState();
  }

  Future<void> _runInspection() async {
    final device = _effectiveDevice;
    final artifact = _selectedArtifact;

    if (!_validateCanSendCommand(device: device, artifact: artifact)) return;

    final auth = context.read<AuthProvider>();

    setState(() {
      _phase = _Phase.inspectRunning;
      _errorMessage = null;
      _inspectionResult = null;
    });
    _persistState();

    try {
      final inspection = await _workflowService.inspectFromDevice(
        deviceId: device!.deviceCode,
        artifactId: artifact!.id,
        description: 'Workflow: ${device.deviceCode}',
        createdBy: auth.username,
      );
      if (!mounted) return;

      setState(() {
        _inspectionResult = inspection;
        _phase = _Phase.done;
      });
      _persistState();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.alignDone;
        _errorMessage = e.message;
      });
      _persistState();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.alignDone;
        _errorMessage = e.toString();
      });
      _persistState();
    }
  }

  bool _validateCanSendCommand({
    required IotDevice? device,
    required Artifact? artifact,
  }) {
    if (device == null) {
      setState(() => _errorMessage = 'Please select a device first.');
      return false;
    }
    if (artifact == null) {
      setState(() => _errorMessage = 'Please select an artifact first.');
      return false;
    }
    if (!_isDeviceOnline) {
      setState(() {
        _errorMessage =
            'Device ${device.deviceCode} is offline. Commands cannot be sent.';
      });
      return false;
    }
    return true;
  }

  void _resetWorkflow() {
    _stopPoll();
    setState(() {
      _phase = _Phase.idle;
      _errorMessage = null;
      _initResult = null;
      _alignResult = null;
      _latestDeviation = null;
      _inspectionResult = null;
      _acks = [];
      _initStartTs = null;
      _alignmentStartTs = null;
      _alignmentIteration = null;
    });

    final artifactId = _selectedArtifact?.id;
    if (artifactId != null) unawaited(_checkGoldenPose(artifactId));
    _persistState();
  }

  void _startInitPoll() {
    _pollTimer?.cancel();
    unawaited(_pollInitOnce());
    _pollTimer = Timer.periodic(
      _pollInterval,
      (_) => unawaited(_pollInitOnce()),
    );
  }

  Future<void> _pollInitOnce() async {
    if (_pollInFlight || !mounted) return;

    final deviceCode = _effectiveDevice?.deviceCode;
    if (deviceCode == null) return;

    _pollInFlight = true;
    try {
      final acks = await _workflowService.pollAcks(deviceCode, limit: 20);
      if (!mounted) return;

      final completed = acks.any(_isCurrentInitCompleteAck);
      if (!completed) return;

      _stopPoll();

      final artifactId = _selectedArtifact?.id;
      if (artifactId != null) {
        try {
          final refreshed = await _artifactService.get(artifactId);
          if (mounted) setState(() => _selectedArtifact = refreshed);
        } catch (_) {}

        await _checkGoldenPose(artifactId);
      }

      if (!mounted) return;
      setState(() => _phase = _Phase.initDone);
      _persistState();
    } catch (_) {
      // Temporary poll failure. Keep polling on the next tick.
    } finally {
      _pollInFlight = false;
    }
  }

  void _startAlignPoll() {
    _pollTimer?.cancel();
    var pollCount = 0;

    unawaited(_pollAlignmentOnce());
    _pollTimer = Timer.periodic(_pollInterval, (_) {
      pollCount++;
      unawaited(_pollAlignmentOnce());

      if (pollCount % 10 == 0) {
        unawaited(_refreshDeviceOnlineStatus());
      }
    });
  }

  Future<void> _pollAlignmentOnce() async {
    if (_pollInFlight || !mounted) return;

    final deviceCode = _effectiveDevice?.deviceCode;
    if (deviceCode == null) return;

    _pollInFlight = true;
    try {
      final acks = await _workflowService.pollAcks(deviceCode, limit: 30);
      if (!mounted) return;

      final currentAcks = acks.where(_isCurrentAlignmentAck).toList()
        ..sort((a, b) => _ackTimestampMs(b).compareTo(_ackTimestampMs(a)));

      setState(() => _acks = currentAcks);

      // Auto-stop polling when alignment failed (detected via ACK) and show user dialog.
      if (_alignmentFailedThisSession && _phase == _Phase.alignRunning) {
        _stopPoll(refreshDevice: false);
        final reason = _alignmentFailReason;
        WidgetsBinding.instance.addPostFrameCallback(
          (_) => _handleAlignmentFailed(reason),
        );
        _persistState();
        return;
      }

      try {
        final meta = await _workflowService.getLatestMetadata(deviceCode);
        final metadata = _asStringMap(meta['metadata']);

        // Metadata fallback: detect failure even if MQTT ACK was not received
        // (e.g. Pi offline or MQTT not available).
        final alignStatus = metadata['alignment_status']?.toString();
        if (alignStatus == 'failed' && _phase == _Phase.alignRunning) {
          _stopPoll(refreshDevice: false);
          final reason = metadata['alignment_fail_reason']?.toString();
          WidgetsBinding.instance.addPostFrameCallback(
            (_) => _handleAlignmentFailed(reason),
          );
          _persistState();
          return;
        }

        final deviation = _asStringMap(metadata['pose_deviation']);
        if (mounted && deviation.isNotEmpty) {
          setState(() => _latestDeviation = deviation);
        }

        // Show live iteration progress.
        final iter = metadata['alignment_iteration'];
        final maxIter = metadata['alignment_max_iterations'];
        if (mounted && iter != null) {
          final iterInt = (iter as num).toInt();
          final maxInt = maxIter != null ? (maxIter as num).toInt() : 20;
          setState(() => _alignmentIteration = (iterInt, maxInt));
        }
      } catch (_) {}

      _persistState();
    } catch (_) {
      // Temporary poll failure. Keep polling on the next tick.
    } finally {
      _pollInFlight = false;
    }
  }

  void _handleAlignmentFailed(String? reason) {
    if (!mounted || _phase != _Phase.alignRunning) return;
    showDialog<_AlignmentFailAction>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.orange),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'Camera Positioning Failed',
                style: TextStyle(fontSize: 16),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.orange.withOpacity(0.4)),
              ),
              child: Text(
                reason ?? 'The camera could not be precisely positioned.',
                style: const TextStyle(fontSize: 13),
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'The camera has been moved to the closest estimated position '
              'based on the Diamond ArUco reference marker.\n\n'
              'You can:\n'
              '• Check that the Diamond ArUco marker is visible and well-lit, then retry.\n'
              '• Or proceed with the current camera position — the inspection will still '    
              'run, and the similarity score (SSIM) will reflect any remaining offset.',
              style: TextStyle(fontSize: 12, color: Colors.black54),
            ),
          ],
        ),
        actions: [
          TextButton.icon(
            onPressed: () => Navigator.of(ctx).pop(_AlignmentFailAction.retry),
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Check & Retry'),
          ),
          ElevatedButton.icon(
            onPressed: () => Navigator.of(ctx).pop(_AlignmentFailAction.continueAnyway),
            icon: const Icon(Icons.arrow_forward, size: 16),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
              foregroundColor: Colors.white,
            ),
            label: const Text('Proceed to Inspection'),
          ),
        ],
      ),
    ).then((action) {
      if (!mounted) return;
      if (action == _AlignmentFailAction.continueAnyway) {
        setState(() {
          _phase = _Phase.alignDone;
          _errorMessage =
              'Camera positioning was not fully accurate. '
              'The inspection will proceed — the similarity score may reflect the offset.';
        });
      } else {
        // Retry: go back so the user can re-start alignment
        setState(() {
          _phase = _Phase.initDone;
          _alignmentStartTs = null;
          _acks = [];
          _latestDeviation = null;
          _alignmentIteration = null;
          _errorMessage =
              'Please verify the Diamond ArUco marker is clearly visible and well-lit, '
              'then press "Start Camera Alignment" again.';
        });
      }
      _persistState();
    });
  }

  void _stopPoll({bool refreshDevice = true}) {
    _pollTimer?.cancel();
    _pollTimer = null;
    _pollInFlight = false;

    if (refreshDevice && mounted) {
      unawaited(_refreshDeviceOnlineStatus());
    }
  }

  bool _isCurrentInitCompleteAck(Map<String, dynamic> ack) {
    final startTs = _initStartTs ?? 0;
    if (_ackTimestampMs(ack) < startTs) return false;

    final payload = _asStringMap(ack['payload']);
    final result = _asStringMap(payload['result']);

    return payload['action'] == 'capture_stereo_pair' &&
        result['status'] == 'ok';
  }

  bool _isCurrentAlignmentAck(Map<String, dynamic> ack) {
    final startTs = _alignmentStartTs;
    // If we don't know when this session started, don't show stale acks.
    if (startTs == null) return false;
    if (_ackTimestampMs(ack) < startTs) return false;

    // Also filter by artifact_id so acks from other artifacts are excluded.
    final artifactId = _selectedArtifact?.id;
    if (artifactId == null) return true;
    final payload = _asStringMap(ack['payload']);
    final payloadArtifactId = payload['artifact_id']?.toString();
    if (payloadArtifactId == null) return true; // no artifact_id field, keep
    return payloadArtifactId == artifactId;
  }

  static int _ackTimestampMs(Map<String, dynamic> ack) {
    final receivedTs = ack['received_ts_ms'];
    if (receivedTs is int) return receivedTs;
    if (receivedTs is num) return receivedTs.toInt();

    final payload = _asStringMap(ack['payload']);
    final payloadTs = payload['ts_ms'];
    if (payloadTs is int) return payloadTs;
    if (payloadTs is num) return payloadTs.toInt();

    return 0;
  }

  static Map<String, dynamic> _asStringMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, val) => MapEntry(key.toString(), val));
    }
    return <String, dynamic>{};
  }

  static T? _firstOrNull<T>(Iterable<T> items, bool Function(T item) test) {
    for (final item in items) {
      if (test(item)) return item;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final device = _effectiveDevice;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          device != null ? 'Workflow: ${device.deviceCode}' : 'Workflow',
        ),
        actions: [
          if (device != null)
            _DeviceStatusBadge(
              device: device,
              isOnlineOverride: _liveDeviceOnline,
            ),
        ],
      ),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              _buildSelectors(),
              const SizedBox(height: 16),
              if (_errorMessage != null) ...[
                _ErrorBanner(
                  message: _errorMessage!,
                  onDismiss: () => setState(() => _errorMessage = null),
                ),
                const SizedBox(height: 12),
              ],
              _buildOfflineBanner(),
              _buildStep1Card(),
              const SizedBox(height: 12),
              _buildStep2Card(),
              if (_phase.index >= _Phase.alignDone.index) ...[
                const SizedBox(height: 12),
                _buildStep3Card(),
              ],
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildOfflineBanner() {
    final device = _effectiveDevice;
    if (device == null || _isDeviceOnline || _phase != _Phase.idle) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: _InfoBanner(
        icon: Icons.wifi_off,
        color: Colors.orange,
        message:
            'Device ${device.deviceCode} is offline. Turn it on or check the connection before starting the workflow.',
      ),
    );
  }

  Widget _buildSelectors() {
    final locked = _phase != _Phase.idle;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Workflow Configuration',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
                if (_checkingGoldenPose)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            if (widget.device == null) ...[
              DropdownButtonFormField<IotDevice>(
                value: _selectedDevice,
                isExpanded: true,
                decoration: const InputDecoration(
                  hintText: 'Select IoT device...',
                  prefixIcon: Icon(Icons.router_outlined),
                ),
                items: _devices.map(_buildDeviceMenuItem).toList(),
                onChanged: locked
                    ? null
                    : (device) {
                        setState(() {
                          _selectedDevice = device;
                          _liveDeviceOnline = null;
                        });
                        unawaited(_refreshDeviceOnlineStatus());
                      },
              ),
              const SizedBox(height: 10),
            ],
            DropdownButtonFormField<Artifact>(
              value: _selectedArtifact,
              isExpanded: true,
              decoration: const InputDecoration(
                hintText: 'Select artifact to inspect...',
                prefixIcon: Icon(Icons.inventory_2_outlined),
              ),
              items: _artifacts.map(_buildArtifactMenuItem).toList(),
              onChanged: locked
                  ? null
                  : (artifact) {
                      setState(() {
                        _selectedArtifact = artifact;
                        _hasGoldenPose = false;
                      });
                      if (artifact != null) {
                        unawaited(_checkGoldenPose(artifact.id));
                      }
                    },
            ),
            if (locked) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(
                    Icons.lock_outline,
                    size: 14,
                    color: AppColors.textMuted,
                  ),
                  const SizedBox(width: 4),
                  const Expanded(
                    child: Text(
                      'Workflow in progress — configuration is locked.',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: _resetWorkflow,
                    style: TextButton.styleFrom(
                      padding: EdgeInsets.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: const Text(
                      'Reset',
                      style: TextStyle(fontSize: 11, color: Colors.red),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  DropdownMenuItem<IotDevice> _buildDeviceMenuItem(IotDevice device) {
    return DropdownMenuItem(
      value: device,
      child: Row(
        children: [
          Icon(
            Icons.circle,
            size: 8,
            color: device.isOnline ? Colors.green : Colors.grey,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              device.deviceCode,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  DropdownMenuItem<Artifact> _buildArtifactMenuItem(Artifact artifact) {
    return DropdownMenuItem(
      value: artifact,
      child: Text(
        artifact.name,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }

  Widget _buildStep1Card() {
    final isRunning = _phase == _Phase.initRunning;
    final isDone = _phase.index >= _Phase.initDone.index;
    final canStart = _phase == _Phase.idle && _canSendDeviceCommand;
    final canUseExistingGolden = _phase == _Phase.idle && _hasGoldenPose;

    return _StepCard(
      stepNumber: 1,
      title: 'Set Up Reference Image',
      subtitle:
          'Capture the artifact’s reference stereo pair. Required once per artifact or after repositioning.',
      isDone: isDone,
      isActive: isRunning,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_initResult != null) ...[
            _ResultChips(result: _initResult!),
            const SizedBox(height: 10),
          ],
          if (canUseExistingGolden) ...[
            const _InfoBanner(
              icon: Icons.check_circle_outline,
              color: Colors.green,
              message:
                  'Reference image already exists for this artifact. You can reuse it and skip to alignment.',
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: canStart ? _runInitialization : null,
                    icon: const Icon(Icons.refresh, size: 16),
                    label: const Text('Recapture Reference'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.orange,
                      side: const BorderSide(color: Colors.orange),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _canSendDeviceCommand ? _skipInitialization : null,
                    icon: const Icon(Icons.skip_next),
                    label: const Text('Use Existing Reference'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ] else ...[
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: canStart ? _runInitialization : null,
                icon: isRunning
                    ? const _SmallSpinner()
                    : isDone
                        ? const Icon(Icons.check)
                        : const Icon(Icons.play_arrow),
                label: Text(
                  isRunning
                      ? 'Capturing… waiting for device'
                      : isDone
                          ? 'Reference Captured'
                          : 'Capture Reference Image',
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor:
                      isDone ? Colors.green.shade600 : AppColors.primary,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
            if (isRunning) ...[
              const SizedBox(height: 8),
              const _InfoBanner(
                icon: Icons.sync,
                color: Colors.blue,
                message:
                    'Waiting for the device to capture and upload the stereo pair...',
                showSpinner: true,
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildStep2Card() {
    final isLocked = _phase.index < _Phase.initDone.index;
    final isRunning = _phase == _Phase.alignRunning;
    final isDone = _phase.index >= _Phase.alignDone.index;
    final canStart = _phase == _Phase.initDone && _canSendDeviceCommand;

    return _StepCard(
      stepNumber: 2,
      title: 'Camera Alignment',
      subtitle:
          'Automatically position the camera to match the reference angle using the Diamond ArUco marker.',
      isDone: isDone,
      isActive: isRunning,
      trailing: isRunning && _alignmentIteration != null
          ? Text(
              'Step ${_alignmentIteration!.$1} / ${_alignmentIteration!.$2}',
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textMuted,
                fontWeight: FontWeight.w600,
              ),
            )
          : _acks.isNotEmpty
              ? Text(
                  '${_acks.length} step(s)',
                  style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                )
              : null,
      child: Opacity(
        opacity: isLocked ? 0.45 : 1,
        child: IgnorePointer(
          ignoring: isLocked,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_alignResult != null) ...[
                _ResultChips(result: _alignResult!),
                const SizedBox(height: 10),
              ],
              if (_latestDeviation != null && isRunning) ...[
                _DeviationTile(deviation: _latestDeviation!),
                const SizedBox(height: 10),
              ],
              if (_acks.isNotEmpty) ...[
                const Text(
                  'Adjustment history:',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                ),
                const SizedBox(height: 6),
                ..._acks.take(8).map(_buildAckTile),
                const SizedBox(height: 8),
              ],
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: canStart ? _runAlignment : null,
                      icon: isDone
                          ? const Icon(Icons.check)
                          : const Icon(Icons.adjust),
                      label: Text(isDone ? 'Aligned' : 'Start Camera Alignment'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor:
                            isDone ? Colors.green.shade600 : AppColors.primary,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ),
                  if (isRunning) ...[
                    const SizedBox(width: 8),
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _alignmentCompletedThisSession
                            ? _confirmAlignmentDone
                            : null,
                        icon: const Icon(Icons.check_circle_outline),
                        label: const Text('Confirm Done'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.green,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              if (isRunning) ...[
                const SizedBox(height: 8),
                Text(
                  _alignmentCompletedThisSession
                      ? 'Camera is in position. Press "Confirm Done" to proceed to inspection.'
                      : 'The camera is being automatically repositioned. Please wait…',
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textMuted,
                  ),
                ),
              ],
              if (isLocked) ...[
                const SizedBox(height: 10),
                const _InfoBanner(
                  icon: Icons.lock_outline,
                  color: Colors.grey,
                  message:
                      'Complete Step 1 (or use an existing reference) to enable alignment.',
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAckTile(Map<String, dynamic> ack) {
    final payload = _asStringMap(ack['payload']);
    final action = payload['action']?.toString() ?? '?';
    final result = _asStringMap(payload['result']);
    final statusStr = result['status']?.toString() ?? '';
    final tsMs = _ackTimestampMs(ack);
    final ts = tsMs > 0 ? DateTime.fromMillisecondsSinceEpoch(tsMs).toLocal() : null;

    const actionLabels = <String, String>{
      'capture': 'Capture',
      'move': 'Move',
      'alignment_complete': 'Alignment Complete',
      'alignment_failed': 'Alignment Failed',
      'capture_stereo_pair': 'Stereo Capture',
      'noop': 'No-op',
    };

    final actionDisplay = actionLabels[action] ?? action;
    final isComplete = action == 'alignment_complete';
    final isError = statusStr == 'error' || action == 'alignment_failed';
    final isIgnored = statusStr == 'ignored';

    final IconData icon;
    final Color color;

    if (isComplete) {
      icon = Icons.check_circle;
      color = Colors.green;
    } else if (isError) {
      icon = Icons.error_outline;
      color = Colors.red;
    } else if (isIgnored) {
      icon = Icons.remove_circle_outline;
      color = Colors.orange;
    } else if (statusStr == 'ok') {
      icon = Icons.check_circle_outline;
      color = Colors.green.shade600;
    } else {
      icon = Icons.info_outline;
      color = AppColors.textMuted;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: isComplete
            ? Colors.green.withOpacity(0.08)
            : AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(8),
        border: isComplete
            ? Border.all(color: Colors.green.shade300, width: 1)
            : null,
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              actionDisplay,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isComplete ? FontWeight.bold : FontWeight.normal,
                color: isComplete ? Colors.green : null,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (statusStr.isNotEmpty && !isComplete) ...[
            const SizedBox(width: 8),
            Text(
              statusStr.toUpperCase(),
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: color,
              ),
            ),
          ],
          if (ts != null) ...[
            const SizedBox(width: 8),
            Text(
              '${ts.hour.toString().padLeft(2, '0')}:'
              '${ts.minute.toString().padLeft(2, '0')}:'
              '${ts.second.toString().padLeft(2, '0')}',
              style: const TextStyle(fontSize: 11, color: AppColors.textFaint),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStep3Card() {
    final isRunning = _phase == _Phase.inspectRunning;
    final isDone = _phase == _Phase.done;
    final canRun = _phase == _Phase.alignDone && _canSendDeviceCommand;

    return _StepCard(
      stepNumber: 3,
      title: 'AI Artifact Inspection',
      subtitle:
          'Run AI analysis on the final aligned image and compare it with the reference.',
      isDone: isDone,
      isActive: isRunning,
      accentColor: Colors.orange,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_inspectionResult != null) ...[
            _InspectionSummary(inspection: _inspectionResult!),
            const SizedBox(height: 12),
          ],
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: canRun ? _runInspection : null,
                  icon: isRunning
                      ? const _SmallSpinner()
                      : isDone
                          ? const Icon(Icons.check)
                          : const Icon(Icons.search),
                  label: Text(
                    isRunning
                        ? 'Analyzing...'
                        : isDone
                            ? 'Inspection Completed'
                            : 'Run AI Inspection',
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor:
                        isDone ? Colors.green.shade600 : Colors.orange,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
              if (_inspectionResult != null) ...[
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) =>
                            ResultScreen(inspection: _inspectionResult!),
                      ),
                    ),
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('View Result'),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _StepCard extends StatelessWidget {
  final int stepNumber;
  final String title;
  final String? subtitle;
  final bool isDone;
  final bool isActive;
  final Color? accentColor;
  final Widget? trailing;
  final Widget child;

  const _StepCard({
    required this.stepNumber,
    required this.title,
    this.subtitle,
    required this.isDone,
    required this.isActive,
    this.accentColor,
    this.trailing,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = isDone
        ? Colors.green.shade300
        : isActive
            ? (accentColor ?? Colors.blue).withOpacity(0.75)
            : AppColors.surfaceMuted;

    final avatarColor = isDone
        ? Colors.green
        : isActive
            ? (accentColor ?? Colors.blue)
            : Colors.grey;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: borderColor, width: 1.4),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: avatarColor,
                  child: isDone
                      ? const Icon(Icons.check, size: 16, color: Colors.white)
                      : isActive
                          ? const _SmallSpinner()
                          : Text(
                              '$stepNumber',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                      if (subtitle != null) ...[
                        const SizedBox(height: 2),
                        Text(
                          subtitle!,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.textMuted,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (trailing != null) ...[
                  const SizedBox(width: 8),
                  trailing!,
                ],
              ],
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

class _InfoBanner extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String message;
  final bool showSpinner;

  const _InfoBanner({
    required this.icon,
    required this.color,
    required this.message,
    this.showSpinner = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Row(
        children: [
          if (showSpinner)
            SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2, color: color),
            )
          else
            Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(fontSize: 12, color: color),
            ),
          ),
        ],
      ),
    );
  }
}

class _DeviationTile extends StatelessWidget {
  final Map<String, dynamic> deviation;

  const _DeviationTile({required this.deviation});

  // Translation values from the C++ solver are in metres; display as mm.
  String _fmt(dynamic value, String unit, {int decimals = 1, double multiplier = 1.0}) {
    final number = ((value as num?)?.toDouble() ?? 0.0) * multiplier;
    return '${number.toStringAsFixed(decimals)}$unit';
  }

  @override
  Widget build(BuildContext context) {
    final withinTolerance = deviation['within_tolerance'] == true;
    final dx = _fmt(deviation['delta_x'], 'mm', multiplier: 1000.0);
    final dz = _fmt(deviation['delta_z'], 'mm', multiplier: 1000.0);
    final transMag = _fmt(deviation['translation_mag'], 'mm', multiplier: 1000.0);
    final dpan = _fmt(deviation['delta_pan'], '°');
    final dtilt = _fmt(deviation['delta_tilt'], '°');
    final rotMag = _fmt(deviation['rotation_mag'], '°');

    final color = withinTolerance ? Colors.green : Colors.orange;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                withinTolerance ? Icons.check_circle_outline : Icons.sync,
                size: 15,
                color: color,
              ),
              const SizedBox(width: 5),
              Text(
                withinTolerance ? 'Within tolerance' : 'Aligning...',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Position: Δx=$dx  Δz=$dz  total=$transMag',
            style: const TextStyle(
              fontSize: 11,
              fontFamily: 'monospace',
              letterSpacing: 0.3,
            ),
          ),
          Text(
            'Angle:    Δpan=$dpan  Δtilt=$dtilt  total=$rotMag',
            style: const TextStyle(
              fontSize: 11,
              fontFamily: 'monospace',
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}

class _DeviceStatusBadge extends StatelessWidget {
  final IotDevice device;
  final bool? isOnlineOverride;

  const _DeviceStatusBadge({
    required this.device,
    this.isOnlineOverride,
  });

  @override
  Widget build(BuildContext context) {
    final online = isOnlineOverride ?? device.isOnline;
    final color = online ? Colors.green : Colors.grey;

    return Container(
      margin: const EdgeInsets.only(right: 12, top: 10, bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle, size: 8, color: color),
          const SizedBox(width: 4),
          Text(
            online ? 'Online' : 'Offline',
            style: TextStyle(
              color: online ? Colors.green.shade700 : Colors.grey.shade600,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _SmallSpinner extends StatelessWidget {
  const _SmallSpinner();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      width: 14,
      height: 14,
      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
    );
  }
}

class _ResultChips extends StatelessWidget {
  final Map<String, dynamic> result;

  const _ResultChips({required this.result});

  @override
  Widget build(BuildContext context) {
    final ok = result['ok'] == true;
    final published = result['published'] == true;
    final mode = result['mode']?.toString() ?? '';
    final taskId = result['task_id']?.toString() ?? '';

    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        _Chip(
          label: ok ? 'Success' : 'Failed',
          color: ok ? Colors.green : Colors.red,
          icon: ok ? Icons.check_circle_outline : Icons.cancel_outlined,
        ),
        _Chip(
          label: published ? 'MQTT OK' : 'HTTP Fallback',
          color: published ? Colors.blue : Colors.orange,
          icon: published ? Icons.wifi : Icons.wifi_off,
        ),
        if (mode.isNotEmpty)
          _Chip(
            label: mode,
            color: Colors.grey.shade600,
            icon: Icons.settings_ethernet,
          ),
        if (taskId.isNotEmpty)
          _Chip(
            label: taskId.length > 22 ? '${taskId.substring(0, 22)}…' : taskId,
            color: Colors.grey.shade500,
            icon: Icons.tag,
          ),
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData icon;

  const _Chip({
    required this.label,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _InspectionSummary extends StatelessWidget {
  final Inspection inspection;

  const _InspectionSummary({required this.inspection});

  @override
  Widget build(BuildContext context) {
    final hasAlert = inspection.status.isAlert;
    final color = hasAlert ? Colors.orange : Colors.green;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          Column(
            children: [
              Icon(
                inspection.status == ArtifactStatus.good
                    ? Icons.check_circle
                    : Icons.warning_amber,
                size: 32,
                color: color,
              ),
              const SizedBox(height: 4),
              Text(
                inspection.status.label,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          Column(
            children: [
              Icon(
                inspection.detections.isEmpty
                    ? Icons.verified_outlined
                    : Icons.bug_report_outlined,
                size: 28,
                color: inspection.detections.isEmpty ? Colors.green : Colors.orange,
              ),
              const SizedBox(height: 4),
              Text(
                '${inspection.detections.length} region(s)',
                style: const TextStyle(fontSize: 11),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback onDismiss;

  const _ErrorBanner({
    required this.message,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.red.shade200),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: Colors.red),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: Colors.red),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 18, color: Colors.red),
            onPressed: onDismiss,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
        ],
      ),
    );
  }
}
