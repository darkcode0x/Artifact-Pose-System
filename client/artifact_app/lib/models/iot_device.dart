enum DeviceStatus {
  online,
  offline;

  static DeviceStatus fromWire(String? value) {
    if (value?.toLowerCase() == 'online') return DeviceStatus.online;
    return DeviceStatus.offline;
  }
}

class IotDevice {
  final String deviceId; // VARCHAR(6) from PostgreSQL
  final String deviceCode;
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
    return IotDevice(
      deviceId: json['device_id']?.toString() ?? '',
      deviceCode: (json['device_code'] ?? json['machine_hash'] ?? '') as String,
      description: json['description'] as String?,
      status: DeviceStatus.fromWire(json['status'] is String 
          ? json['status'] as String 
          : json['status']?['db_status'] as String?),
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ?? DateTime.now(),
      lastActiveAt: DateTime.tryParse(json['last_active_at']?.toString() ?? ''),
    );
  }
}
