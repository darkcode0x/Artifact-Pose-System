enum DeviceStatus {
  online,
  offline;

  static DeviceStatus fromWire(String? value) {
    if (value == 'online') return DeviceStatus.online;
    return DeviceStatus.offline;
  }
}

class IotDevice {
  final int deviceId;
  final String deviceCode;
  final String? description;
  final DeviceStatus status;
  final DateTime createdAt;
  final DateTime? lastActiveAt;

  IotDevice({
    required this.deviceId,
    required this.deviceCode,
    this.description,
    required this.status,
    required this.createdAt,
    this.lastActiveAt,
  });

  factory IotDevice.fromJson(Map<String, dynamic> json) {
    return IotDevice(
      deviceId: json['device_id'] as int,
      deviceCode: json['device_code'] as String,
      description: json['description'] as String?,
      status: DeviceStatus.fromWire(json['status'] as String?),
      createdAt: DateTime.parse(json['created_at'] as String),
      lastActiveAt: json['last_active_at'] != null 
          ? DateTime.parse(json['last_active_at'] as String)
          : null,
    );
  }
}
