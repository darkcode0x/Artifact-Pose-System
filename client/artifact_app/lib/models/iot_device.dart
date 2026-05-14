enum DeviceStatus {
  online,
  offline;

  static DeviceStatus fromWire(String? value) {
    if (value?.toLowerCase() == 'online') return DeviceStatus.online;
    return DeviceStatus.offline;
  }

  String get wireValue => name;
}

/// DB-backed IoT device record. Mirrors `iot_devices` Postgres table.
/// Backend may also include a `status` map with extra runtime info from
/// the in-memory command service (last_seen, pending acks, etc.).
class IotDevice {
  final String deviceId; // VARCHAR(6)
  final String deviceCode; // unique device code
  final String? description;
  final DeviceStatus status;
  final DateTime createdAt;
  final DateTime? lastActiveAt;

  const IotDevice({
    required this.deviceId,
    required this.deviceCode,
    this.description,
    required this.status,
    required this.createdAt,
    this.lastActiveAt,
  });

  bool get isOnline => status == DeviceStatus.online;

  factory IotDevice.fromJson(Map<String, dynamic> json) {
    // The list endpoint returns DeviceSummary which packs DB fields under
    // `status: {db_status, description, last_active_at}`. Single-device endpoints
    // (DB-backed) return rows directly.
    final rawStatus = json['status'];
    String? dbStatus;
    String? description;
    String? lastActiveStr;

    if (rawStatus is String) {
      dbStatus = rawStatus;
    } else if (rawStatus is Map<String, dynamic>) {
      dbStatus = rawStatus['db_status'] as String?;
      description = rawStatus['description'] as String?;
      lastActiveStr = rawStatus['last_active_at'] as String?;
    }

    return IotDevice(
      deviceId: json['device_id']?.toString() ?? '',
      deviceCode: (json['device_code'] ?? json['machine_hash'] ?? '') as String,
      description: (json['description'] as String?) ?? description,
      status: DeviceStatus.fromWire(dbStatus),
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.now(),
      lastActiveAt: DateTime.tryParse(
          (json['last_active_at'] ?? lastActiveStr)?.toString() ?? ''),
    );
  }
}
