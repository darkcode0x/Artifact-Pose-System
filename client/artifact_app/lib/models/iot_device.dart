/// Lightweight model that mirrors what the backend actually returns from
/// `GET /devices` and `GET /devices/{id}/status`. The backend keeps device
/// state in memory (not in DB), so most fields are best-effort.
class IotDevice {
  final String deviceId;
  final String machineHash;
  final Map<String, dynamic> status;

  const IotDevice({
    required this.deviceId,
    required this.machineHash,
    this.status = const {},
  });

  /// True if the in-memory command service has any liveness signal for this
  /// device (last seen / pending acks). False otherwise.
  bool get isOnline {
    if (status.isEmpty) return false;
    final lastSeen = status['last_seen'] ?? status['last_active_at'];
    if (lastSeen != null) return true;
    return status['online'] == true;
  }

  String? get lastSeenIso {
    final v = status['last_seen'] ?? status['last_active_at'];
    return v is String ? v : null;
  }

  factory IotDevice.fromJson(Map<String, dynamic> json) {
    final rawStatus = json['status'];
    return IotDevice(
      deviceId: json['device_id'] as String,
      machineHash: (json['machine_hash'] as String?) ?? '',
      status: rawStatus is Map<String, dynamic>
          ? rawStatus
          : const <String, dynamic>{},
    );
  }
}
