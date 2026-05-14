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

class DeviceWorkflowScreen extends StatefulWidget {
  // When opened from DeviceListScreen, device is known.
  // When opened from ArtifactDetailScreen, device is null and must be selected.
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

// Persists alignment state across navigation pushes/pops.
class _PersistedWorkflowState {
  final _Phase phase;
  final List<Map<String, dynamic>> acks;
  final Map<String, dynamic>? latestDeviation;
  final Map<String, dynamic>? initResult;
  final Map<String, dynamic>? alignResult;
  final Inspection? inspectionResult;
  final String? selectedArtifactId;
  final String? selectedDeviceCode;
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
    this.alignmentStartTs,
  });
}

class _DeviceWorkflowScreenState extends State<DeviceWorkflowScreen> {
  // Static cache so state survives navigation away and back.
  static final Map<String, _PersistedWorkflowState> _stateCache = {};

  late WorkflowService _workflowService;
  late ArtifactService _artifactService;
  late DeviceService _deviceService;

  List<Artifact> _artifacts = [];
  Artifact? _selectedArtifact;

  // Baseline is always 100 mm — not editable by user.
  static const double _baselineMm = 100.0;

  // Device selection (used when widget.device is null)
  List<IotDevice> _devices = [];
  IotDevice? _selectedDevice;

  _Phase _phase = _Phase.idle;
  String? _errorMessage;

  Map<String, dynamic>? _initResult;
  Map<String, dynamic>? _alignResult;
  // ACKs for the *current* alignment session only (cleared on new start).
  List<Map<String, dynamic>> _acks = [];
  int? _alignmentStartTs;
  Map<String, dynamic>? _latestDeviation;
  Timer? _pollTimer;

  Inspection? _inspectionResult;

  // Golden pose status per artifact — loaded from server.
  bool _hasGoldenPose = false;

  // Trang thai online/offline moi nhat tu server (override widget.device.isOnline).
  // null = chua check lan nao, true/false = ket qua API moi nhat.
  bool? _liveDeviceOnline;

  // ID of cached selected artifact/device — resolved after fresh list is loaded.
  String? _restoredArtifactId;
  String? _restoredDeviceCode;

  IotDevice? get _effectiveDevice => widget.device ?? _selectedDevice;

  // Trang thai online hien thi: dung _liveDeviceOnline neu co, fallback ve model.
  bool get _isDeviceOnline =>
      _liveDeviceOnline ?? (_effectiveDevice?.isOnline ?? false);

  // True when at least one alignment_complete ACK has been received this session.
  bool get _alignmentCompletedThisSession =>
      _acks.any((ack) =>
          (ack['payload'] as Map<String, dynamic>?)?['action'] ==
          'alignment_complete');

  @override
  void initState() {
    super.initState();
    final api = context.read<ApiClient>();
    _workflowService = WorkflowService(api);
    _artifactService = ArtifactService(api);
    _deviceService = DeviceService(api);
    _loadArtifacts();
    if (widget.device == null) _loadDevices();
    _restoreState();
    // Check trang thai thiet bi ngay khi mo man hinh
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _refreshDeviceOnlineStatus(),
    );
  }

  void _restoreState() {
    // Use a stable key: artifact ID when opened from artifact detail,
    // device code when opened from device list.
    final key = widget.preselectedArtifactId ?? widget.device?.deviceCode ?? '';
    if (key.isEmpty) return;
    final cached = _stateCache[key];
    if (cached == null) return;
    // Don't restore a fully completed session — start fresh so the user
    // sees the golden-pose check and can begin a new workflow.
    if (cached.phase == _Phase.done) {
      _stateCache.remove(key);
      return;
    }
    // inspectRunning means the app was killed mid-inspection — outcome unknown;
    // roll back to alignDone so the user can re-inspect.
    _phase = cached.phase == _Phase.inspectRunning
        ? _Phase.alignDone
        : cached.phase;
    _acks = List.of(cached.acks);
    _latestDeviation = cached.latestDeviation;
    _initResult = cached.initResult;
    _alignResult = cached.alignResult;
    _inspectionResult = cached.inspectionResult;
    _alignmentStartTs = cached.alignmentStartTs;
    _restoredArtifactId = cached.selectedArtifactId;
    _restoredDeviceCode = cached.selectedDeviceCode;
    // selectedArtifact / selectedDevice resolved once load completes.
    if (_phase == _Phase.initRunning) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _startInitPoll());
    } else if (_phase == _Phase.alignRunning) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _startAlignPoll());
    }
  }

  void _persistState() {
    final key = widget.preselectedArtifactId ?? _effectiveDevice?.deviceCode ?? '';
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
      alignmentStartTs: _alignmentStartTs,
    );
  }

  @override
  void dispose() {
    _persistState();
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadDevices() async {
    try {
      final list = await _deviceService.list();
      if (!mounted) return;
      setState(() {
        _devices = list;
        if (_restoredDeviceCode != null) {
          try {
            _selectedDevice = list.firstWhere(
              (d) => d.deviceCode == _restoredDeviceCode,
            );
          } catch (_) {}
          _restoredDeviceCode = null;
        }
      });
    } catch (_) {}
  }

  Future<void> _loadArtifacts() async {
    try {
      final list = await _artifactService.list();
      if (!mounted) return;
      setState(() {
        _artifacts = list;
        // Restore cached selection or use preselected artifact id.
        final targetId = _restoredArtifactId ?? widget.preselectedArtifactId;
        if (targetId != null) {
          try {
            _selectedArtifact = list.firstWhere((a) => a.id == targetId);
          } catch (_) {}
        }
        _restoredArtifactId = null;
      });
      // Sau khi load xong, check golden pose cho artifact dang chon.
      if (_selectedArtifact != null) {
        await _checkGoldenPose(_selectedArtifact!.id);
      }
    } catch (_) {
      // silent fail — user will see empty dropdown
    }
  }

  Future<void> _checkGoldenPose(String artifactId) async {
    final has = await _workflowService.hasGoldenPose(artifactId);
    if (!mounted) return;
    setState(() => _hasGoldenPose = has);
  }

  Future<void> _refreshDeviceOnlineStatus() async {
    final deviceCode = _effectiveDevice?.deviceCode;
    if (deviceCode == null) return;
    try {
      final fresh = await _deviceService.getStatus(deviceCode);
      if (!mounted) return;
      setState(() => _liveDeviceOnline = fresh.isOnline);
    } catch (_) {
      // Neu API loi, giu nguyen trang thai cu
    }
  }

  // Timestamp khi bat dau init — dung de chi chap nhan ACK moi hon
  int? _initStartTs;

  void _startInitPoll() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      if (!mounted) return;
      final deviceId = _effectiveDevice?.deviceCode;
      if (deviceId == null) return;

      try {
        final acks = await _workflowService.pollAcks(deviceId, limit: 20);
        if (!mounted) return;

        // Tim ACK capture_stereo_pair ok moi hon thoi diem bat dau init
        final startTs = _initStartTs ?? 0;
        final completed = acks.any((ack) {
          final ts = (ack['received_ts_ms'] as int?) ??
              ((ack['payload'] as Map?))?['ts_ms'] as int? ??
              0;
          if (ts < startTs) return false;
          final payload = ack['payload'] as Map<String, dynamic>? ?? {};
          final action = payload['action']?.toString();
          final result = payload['result'] as Map<String, dynamic>? ?? {};
          return action == 'capture_stereo_pair' && result['status'] == 'ok';
        });

        if (completed) {
          _stopPoll();
          // Refresh artifact de cap nhat has_image
          final artifactId = _selectedArtifact?.id;
          if (artifactId != null) {
            try {
              final refreshed = await _artifactService.get(artifactId);
              if (mounted) setState(() => _selectedArtifact = refreshed);
            } catch (_) {}
            // Refresh golden pose status sau khi init xong.
            await _checkGoldenPose(artifactId);
          }
          if (mounted) {
            setState(() => _phase = _Phase.initDone);
          }
        }
      } catch (_) {}
    });
  }

  void _startAlignPoll() {
    _pollTimer?.cancel();
    var _pollCount = 0;
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      if (!mounted) return;
      final deviceId = _effectiveDevice?.deviceCode;
      if (deviceId == null) return;

      _pollCount++;

      // Poll ACKs
      try {
        final acks = await _workflowService.pollAcks(deviceId, limit: 20);
        if (!mounted) return;
        setState(() => _acks = acks.reversed.toList());
      } catch (_) {}

      // Poll latest pose deviation for live alignment display
      try {
        final meta = await _workflowService.getLatestMetadata(deviceId);
        final deviation = (meta['metadata'] as Map<String, dynamic>?)?['pose_deviation']
            as Map<String, dynamic>?;
        if (mounted && deviation != null) {
          setState(() => _latestDeviation = deviation);
        }
      } catch (_) {}

      // Refresh trang thai online moi 10 poll (~30s)
      if (_pollCount % 10 == 0) {
        _refreshDeviceOnlineStatus();
      }
    });
  }

  void _stopPoll() {
    _pollTimer?.cancel();
    _pollTimer = null;
    // Refresh trang thai thiet bi khi dung poll
    _refreshDeviceOnlineStatus();
  }

  Future<void> _runInitialization() async {
    final device = _effectiveDevice;
    if (device == null) {
      setState(() => _errorMessage = 'Please select a device first');
      return;
    }
    final artifact = _selectedArtifact;
    if (artifact == null) {
      setState(() => _errorMessage = 'Please select an artifact first');
      return;
    }
    setState(() {
      _phase = _Phase.initRunning;
      _errorMessage = null;
      _initResult = null;
      _initStartTs = DateTime.now().millisecondsSinceEpoch;
    });

    try {
      final result = await _workflowService.startInitialization(
        deviceId: _effectiveDevice!.deviceCode,
        artifactId: artifact.id,
        baselineMm: _baselineMm,
      );
      if (!mounted) return;
      final ok = result['ok'] == true;
      setState(() => _initResult = result);
      if (ok) {
        // Lenh da duoc gui den thiet bi — cho den khi nhan ACK capture_stereo_pair ok
        _startInitPoll();
      } else {
        setState(() {
          _phase = _Phase.idle;
          _errorMessage =
              'Initialization failed: ${result['publish_error'] ?? 'unknown error'}';
        });
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.idle;
        _errorMessage = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.idle;
        _errorMessage = e.toString();
      });
    }
  }

  Future<void> _runAlignment() async {
    final artifact = _selectedArtifact;
    if (artifact == null) return;
    final device = _effectiveDevice;
    if (device == null) return;

    setState(() {
      _phase = _Phase.alignRunning;
      _errorMessage = null;
      _alignResult = null;
      _acks = [];  // Clear ACKs for the new alignment session.
      _alignmentStartTs = DateTime.now().millisecondsSinceEpoch;
    });
    _startAlignPoll();

    try {
      final result = await _workflowService.startAlignment(
        deviceId: device.deviceCode,
        artifactId: artifact.id,
      );
      if (!mounted) return;
      final ok = result['ok'] == true;
      setState(() => _alignResult = result);
      if (!ok) {
        _stopPoll();
        if (!mounted) return;
        setState(() {
          _phase = _Phase.initDone;
          _errorMessage =
              'Alignment failed: ${result['publish_error'] ?? 'unknown error'}';
        });
      }
      // If ok=true, keep phase=alignRunning and keep polling.
      // Operator presses "Căn chỉnh xong" when satisfied.
    } on ApiException catch (e) {
      _stopPoll();
      if (!mounted) return;
      setState(() {
        _phase = _Phase.initDone;
        _errorMessage = e.message;
      });
    } catch (e) {
      _stopPoll();
      if (!mounted) return;
      setState(() {
        _phase = _Phase.initDone;
        _errorMessage = e.toString();
      });
    }
  }

  void _confirmAlignmentDone() {
    _stopPoll();
    setState(() => _phase = _Phase.alignDone);
  }

  /// Bỏ qua khởi tạo Golden Pose khi đã có sẵn, chuyển thẳng sang căn chỉnh.
  void _skipInitialization() {
    setState(() {
      _phase = _Phase.initDone;
      _errorMessage = null;
    });
  }

  Future<void> _runInspection() async {
    final artifact = _selectedArtifact;
    if (artifact == null) return;
    final device = _effectiveDevice;
    if (device == null) return;
    final auth = context.read<AuthProvider>();

    setState(() {
      _phase = _Phase.inspectRunning;
      _errorMessage = null;
      _inspectionResult = null;
    });

    try {
      final inspection = await _workflowService.inspectFromDevice(
        deviceId: device.deviceCode,
        artifactId: artifact.id,
        description: 'Workflow: ${device.deviceCode}',
        createdBy: auth.username,
      );
      if (!mounted) return;
      setState(() {
        _inspectionResult = inspection;
        _phase = _Phase.done;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.alignDone;
        _errorMessage = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.alignDone;
        _errorMessage = e.toString();
      });
    }
  }

  // ─── BUILD ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          _effectiveDevice != null
              ? 'Workflow: ${_effectiveDevice!.deviceCode}'
              : 'Workflow: Select Device',
        ),
        actions: [
          if (_effectiveDevice != null)
            _DeviceStatusBadge(
              device: _effectiveDevice!,
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

  // ─── Device + Artifact + baseline selector ───────────────────────────────

  Widget _buildSelectors() {
    final locked = _phase != _Phase.idle;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Workflow Configuration',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 10),
            // Device selector — only show when device not pre-provided
            if (widget.device == null) ...[
              DropdownButtonFormField<IotDevice>(
                value: _selectedDevice,
                isExpanded: true,
                decoration: const InputDecoration(
                  hintText: 'Select IoT device...',
                  prefixIcon: Icon(Icons.router_outlined),
                ),
                items: _devices
                    .map((d) => DropdownMenuItem(
                          value: d,
                          child: Row(
                            children: [
                              Icon(Icons.circle,
                                  size: 8,
                                  color: d.isOnline
                                      ? Colors.green
                                      : Colors.grey),
                              const SizedBox(width: 6),
                              Text(d.deviceCode,
                                  overflow: TextOverflow.ellipsis),
                            ],
                          ),
                        ))
                    .toList(),
                onChanged: locked
                    ? null
                    : (v) => setState(() => _selectedDevice = v),
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
              items: _artifacts
                  .map((a) => DropdownMenuItem(
                        value: a,
                        child: Text(a.name, overflow: TextOverflow.ellipsis),
                      ))
                  .toList(),
              onChanged: locked
                  ? null
                  : (v) {
                      setState(() {
                        _selectedArtifact = v;
                        _hasGoldenPose = false; // reset — se check ngay duoi
                      });
                      if (v != null) _checkGoldenPose((v as Artifact).id);
                    },
            ),
            if (locked)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Row(
                  children: [
                    const Icon(Icons.lock_outline,
                        size: 14, color: AppColors.textMuted),
                    const SizedBox(width: 4),
                    const Expanded(
                      child: Text(
                        'Workflow in progress — cannot change',
                        style: TextStyle(
                            fontSize: 11, color: AppColors.textMuted),
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        _stopPoll();
                        setState(() {
                          _phase = _Phase.idle;
                          _initResult = null;
                          _alignResult = null;
                          _acks = [];
                          _latestDeviation = null;
                          _inspectionResult = null;
                          _errorMessage = null;
                        });
                        // Refresh golden pose status sau reset — tranh hoi init lai
                        // khi golden pose van con tren server.
                        final artifactId = _selectedArtifact?.id;
                        if (artifactId != null) _checkGoldenPose(artifactId);
                      },
                      style: TextButton.styleFrom(
                        padding: EdgeInsets.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      child: const Text('Reset',
                          style:
                              TextStyle(fontSize: 11, color: Colors.red)),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  // ─── Old method removed (now using _buildSelectors) ─────────────────────

  // ─── Step 1 ───────────────────────────────────────────────────────────────

  Widget _buildStep1Card() {
    final isDone = _phase.index >= _Phase.initDone.index;
    final isRunning = _phase == _Phase.initRunning;
    final canStart = _phase == _Phase.idle;
    // Hien thi banner "Golden Pose da co" khi:
    // - phase == idle (chua bat dau session moi) VA golden pose ton tai, HOAC
    // - phase == initDone nhung init duoc skip (skipInitialization)
    // Dung de offer: Re-initialize | Start Alignment.
    final hasExistingGolden = _hasGoldenPose && canStart;

    return _StepCard(
      stepNumber: 1,
      title: 'Initialize Golden Pose (Stereo)',
      isDone: isDone,
      isActive: isRunning,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_initResult != null) ...[
            const SizedBox(height: 10),
            _ResultChips(result: _initResult!),
          ],
          if (hasExistingGolden) ...[  // ── Golden pose already exists ──
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.07),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.green.shade200),
              ),
              child: const Row(
                children: [
                  Icon(Icons.check_circle_outline,
                      size: 16, color: Colors.green),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Golden Pose already initialized for this artifact.',
                      style: TextStyle(fontSize: 12, color: Colors.green),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _runInitialization,
                    icon: const Icon(Icons.refresh, size: 16),
                    label: const Text('Re-initialize'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.orange,
                      side: const BorderSide(color: Colors.orange),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _skipInitialization,
                    icon: const Icon(Icons.skip_next),
                    label: const Text('Start Alignment'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ] else ...[            // ── No golden pose yet / running / done ──
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: canStart ? _runInitialization : null,
                icon: isRunning
                    ? const _SmallSpinner()
                    : const Icon(Icons.play_arrow),
                label: Text(
                  isRunning
                      ? 'Command sent — waiting for device...'
                      : isDone
                          ? 'Re-initialize'
                          : 'Start Initialization',
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor:
                      isDone ? Colors.grey.shade600 : AppColors.primary,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
            if (isRunning) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.blue.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: const Row(
                  children: [
                    SizedBox(
                      width: 13, height: 13,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Waiting for device to capture & upload stereo pair...',
                        style: TextStyle(fontSize: 12, color: Colors.blue),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  // ─── Step 2 ───────────────────────────────────────────────────────────────

  Widget _buildStep2Card() {
    final canStart = _phase == _Phase.initDone;
    final isRunning = _phase == _Phase.alignRunning;
    final isDone = _phase.index >= _Phase.alignDone.index;
    // Locked while Step 1 hasn't completed yet.
    final isLocked = _phase.index < _Phase.initDone.index;

    return _StepCard(
      stepNumber: 2,
      title: 'Pose Alignment',
      isDone: isDone,
      isActive: isRunning,
      trailing: _acks.isNotEmpty
          ? Text(
              '${_acks.length} ACK',
              style:
                  const TextStyle(fontSize: 12, color: AppColors.textMuted),
            )
          : null,
      child: Opacity(
        opacity: isLocked ? 0.4 : 1.0,
        child: IgnorePointer(
          ignoring: isLocked,
          child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_alignResult != null) ...[
            const SizedBox(height: 10),
            _ResultChips(result: _alignResult!),
          ],
          if (_latestDeviation != null && isRunning) ...[
            const SizedBox(height: 10),
            _DeviationTile(deviation: _latestDeviation!),
          ],
          if (_acks.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text(
              'Loop history (newest first):',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            ),
            const SizedBox(height: 6),
            ..._acks.take(8).map(_buildAckTile),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: canStart ? _runAlignment : null,
                  icon: const Icon(Icons.adjust),
                  label: const Text('Start Alignment'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
              if (isRunning || isDone) ...[
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    // Enable only after at least one alignment_complete ACK.
                    onPressed: (isRunning && _alignmentCompletedThisSession)
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
          if (isRunning)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                _alignmentCompletedThisSession
                    ? 'Alignment complete \u2014 press "Confirm Done" to proceed.'
                    : 'Device is auto-aligning in a loop. "Confirm Done" will be enabled once alignment succeeds.',
                style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
              ),
            ),
          if (isLocked)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.lock_outline, size: 15, color: Colors.grey),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Complete or skip Step 1 (Initialize Golden Pose) first.',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
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

  Widget _buildAckTile(Map<String, dynamic> ack) {
    // ACK structure from server: {topic, payload: {action, result, ts_ms, ...}, received_ts_ms}
    final payload = ack['payload'] as Map<String, dynamic>? ?? {};
    final action = payload['action']?.toString() ?? '?';
    final result = payload['result'] as Map<String, dynamic>? ?? {};
    final tsMs = ack['received_ts_ms'] as int? ?? payload['ts_ms'] as int?;
    final ts = tsMs != null ? DateTime.fromMillisecondsSinceEpoch(tsMs).toLocal() : null;

    const actionLabels = <String, String>{
      'capture': 'Capture',
      'move': 'Move',
      'alignment_complete': 'Alignment Complete ✓',
      'alignment_failed': 'Alignment Failed ✗',
      'capture_stereo_pair': 'Stereo Capture (Golden)',
      'noop': 'No-op',
    };
    final actionDisplay = actionLabels[action] ?? action;
    final statusStr = result['status']?.toString() ?? '';

    IconData statusIcon = Icons.info_outline;
    Color statusColor = AppColors.textMuted;
    if (statusStr == 'ok') {
      statusIcon = action == 'alignment_complete'
          ? Icons.check_circle
          : Icons.check_circle_outline;
      statusColor = action == 'alignment_complete' ? Colors.green : Colors.green.shade600;
    } else if (statusStr == 'error') {
      statusIcon = Icons.error_outline;
      statusColor = Colors.red;
    } else if (statusStr == 'ignored') {
      statusIcon = Icons.remove_circle_outline;
      statusColor = Colors.orange;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: action == 'alignment_complete'
            ? Colors.green.withOpacity(0.08)
            : AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(8),
        border: action == 'alignment_complete'
            ? Border.all(color: Colors.green.shade300, width: 1)
            : null,
      ),
      child: Row(
        children: [
          Icon(statusIcon, color: statusColor, size: 16),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              actionDisplay,
              style: TextStyle(
                fontSize: 12,
                fontWeight: action == 'alignment_complete'
                    ? FontWeight.bold
                    : FontWeight.normal,
                color: action == 'alignment_complete' ? Colors.green : null,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (ts != null)
            Text(
              '${ts.hour.toString().padLeft(2, '0')}:'
              '${ts.minute.toString().padLeft(2, '0')}:'
              '${ts.second.toString().padLeft(2, '0')}',
              style: const TextStyle(fontSize: 11, color: AppColors.textFaint),
            ),
        ],
      ),
    );
  }

  // ─── Step 3 ───────────────────────────────────────────────────────────────

  Widget _buildStep3Card() {
    final isRunning = _phase == _Phase.inspectRunning;
    final isDone = _phase == _Phase.done;

    return _StepCard(
      stepNumber: 3,
      title: 'AI Artifact Inspection',
      isDone: isDone,
      isActive: isRunning,
      accentColor: Colors.orange,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Uses the final aligned image to run AI analysis against the original reference.',
            style: TextStyle(fontSize: 13, color: AppColors.textMuted),
          ),
          if (_inspectionResult != null) ...[
            const SizedBox(height: 12),
            _InspectionSummary(inspection: _inspectionResult!),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: isRunning ? null : _runInspection,
                  icon: isRunning
                      ? const _SmallSpinner()
                      : const Icon(Icons.search),
                  label: Text(
                      isRunning ? 'Analyzing...' : 'Run AI Inspection'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orange,
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

// ─── Reusable widgets ────────────────────────────────────────────────────────

class _DeviationTile extends StatelessWidget {
  final Map<String, dynamic> deviation;
  const _DeviationTile({required this.deviation});

  String _fmt(dynamic v, String unit, {int decimals = 1}) {
    final d = (v as num?)?.toDouble() ?? 0.0;
    return '${d.toStringAsFixed(decimals)}$unit';
  }

  @override
  Widget build(BuildContext context) {
    final withinTol = deviation['within_tolerance'] == true;
    final dx = _fmt(deviation['delta_x'], 'mm');
    final dz = _fmt(deviation['delta_z'], 'mm');
    final transMag = _fmt(deviation['translation_mag'], 'mm');
    final dpan = _fmt(deviation['delta_pan'], '°');
    final dtilt = _fmt(deviation['delta_tilt'], '°');
    final rotMag = _fmt(deviation['rotation_mag'], '°');

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: withinTol ? Colors.green.withOpacity(0.07) : Colors.orange.withOpacity(0.07),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: withinTol ? Colors.green.shade300 : Colors.orange.shade300,
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                withinTol ? Icons.check_circle_outline : Icons.sync,
                size: 15,
                color: withinTol ? Colors.green : Colors.orange,
              ),
              const SizedBox(width: 5),
              Text(
                withinTol ? 'Within tolerance' : 'Aligning...',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: withinTol ? Colors.green : Colors.orange,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Position: Δx=$dx  Δz=$dz  (total: $transMag)',
            style: const TextStyle(fontSize: 11, fontFamily: 'monospace', letterSpacing: 0.3),
          ),
          Text(
            'Angle:  Δpan=$dpan  Δtilt=$dtilt  (total: $rotMag)',
            style: const TextStyle(fontSize: 11, fontFamily: 'monospace', letterSpacing: 0.3),
          ),
        ],
      ),
    );
  }
}

class _DeviceStatusBadge extends StatelessWidget {
  final IotDevice device;
  /// Neu duoc truyen vao, override device.isOnline (dung gia tri tu API moi nhat).
  final bool? isOnlineOverride;
  const _DeviceStatusBadge({required this.device, this.isOnlineOverride});

  @override
  Widget build(BuildContext context) {
    final online = isOnlineOverride ?? device.isOnline;
    return Container(
      margin: const EdgeInsets.only(right: 12, top: 10, bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: online ? Colors.green.shade100 : Colors.grey.shade200,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle,
              size: 8, color: online ? Colors.green : Colors.grey),
          const SizedBox(width: 4),
          Text(
            online ? 'Online' : 'Offline',
            style: TextStyle(
              color:
                  online ? Colors.green.shade700 : Colors.grey.shade600,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _StepCard extends StatelessWidget {
  final int stepNumber;
  final String title;
  final bool isDone;
  final bool isActive;
  final Color? accentColor;
  final Widget? trailing;
  final Widget child;

  const _StepCard({
    required this.stepNumber,
    required this.title,
    required this.isDone,
    required this.isActive,
    this.accentColor,
    this.trailing,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    final Color borderColor = isDone
        ? Colors.green.shade300
        : isActive
            ? Colors.blue.shade300
            : AppColors.surfaceMuted;

    final Color avatarColor = isDone
        ? Colors.green
        : isActive
            ? (accentColor ?? Colors.blue)
            : Colors.grey;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: borderColor, width: 1.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
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
                                  color: Colors.white, fontSize: 12),
                            ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 15),
                  ),
                ),
                if (trailing != null) trailing!,
              ],
            ),
            child,
          ],
        ),
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
              icon: Icons.settings_ethernet),
        if (taskId.isNotEmpty)
          _Chip(
            label: taskId.length > 22
                ? '${taskId.substring(0, 22)}…'
                : taskId,
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

  const _Chip({required this.label, required this.color, required this.icon});

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
                fontSize: 11, color: color, fontWeight: FontWeight.w600),
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
    final Color borderColor = hasAlert ? Colors.orange : Colors.green;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: borderColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borderColor.withOpacity(0.3)),
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
                color: inspection.status.isAlert ? Colors.orange : Colors.green,
              ),
              Text(
                inspection.status.label,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
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

  const _ErrorBanner({required this.message, required this.onDismiss});

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
            child: Text(message,
                style: const TextStyle(color: Colors.red)),
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
