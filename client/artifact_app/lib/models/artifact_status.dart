enum ArtifactStatus {
  good,
  needCheck,
  warning,
  damaged,
  maintenance;

  String get wireValue {
    switch (this) {
      case ArtifactStatus.good:
        return 'good';
      case ArtifactStatus.needCheck:
        return 'need_check';
      case ArtifactStatus.warning:
        return 'warning';
      case ArtifactStatus.damaged:
        return 'damaged';
      case ArtifactStatus.maintenance:
        return 'maintenance';
    }
  }

  String get label {
    switch (this) {
      case ArtifactStatus.good:
        return 'Good';
      case ArtifactStatus.needCheck:
        return 'Need Check';
      case ArtifactStatus.warning:
        return 'Warning';
      case ArtifactStatus.damaged:
        return 'Damaged';
      case ArtifactStatus.maintenance:
        return 'Maintenance';
    }
  }

  bool get isAlert =>
      this == ArtifactStatus.needCheck ||
      this == ArtifactStatus.warning ||
      this == ArtifactStatus.damaged;

  static ArtifactStatus fromWire(String? raw) {
    switch ((raw ?? '').toLowerCase().trim()) {
      case 'good':
        return ArtifactStatus.good;
      case 'need_check':
      case 'need check':
      case 'need inspection':
        return ArtifactStatus.needCheck;
      case 'warning':
        return ArtifactStatus.warning;
      case 'damaged':
        return ArtifactStatus.damaged;
      case 'maintenance':
        return ArtifactStatus.maintenance;
      default:
        return ArtifactStatus.good;
    }
  }
}
