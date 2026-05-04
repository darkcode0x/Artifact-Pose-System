enum ArtifactStatus {
  good,
  needCheck,
  warning,
  damaged,
  maintenance,
  archived; // Không được trưng bày (Xóa logic)

  String get wireValue {
    switch (this) {
      case ArtifactStatus.good: return 'good';
      case ArtifactStatus.needCheck: return 'need_check';
      case ArtifactStatus.warning: return 'warning';
      case ArtifactStatus.damaged: return 'damaged';
      case ArtifactStatus.maintenance: return 'maintenance';
      case ArtifactStatus.archived: return 'archived';
    }
  }

  String get label {
    switch (this) {
      case ArtifactStatus.good: return 'Good';
      case ArtifactStatus.needCheck: return 'Need Check';
      case ArtifactStatus.warning: return 'Warning';
      case ArtifactStatus.damaged: return 'Damaged';
      case ArtifactStatus.maintenance: return 'Maintenance';
      case ArtifactStatus.archived: return 'Archived';
    }
  }

  bool get isAlert =>
      this == ArtifactStatus.needCheck ||
      this == ArtifactStatus.warning ||
      this == ArtifactStatus.damaged;

  static ArtifactStatus fromWire(String? raw) {
    switch ((raw ?? '').toLowerCase().trim()) {
      case 'good': return ArtifactStatus.good;
      case 'need_check': return ArtifactStatus.needCheck;
      case 'warning': return ArtifactStatus.warning;
      case 'damaged': return ArtifactStatus.damaged;
      case 'maintenance': return ArtifactStatus.maintenance;
      case 'archived': return ArtifactStatus.archived;
      default: return ArtifactStatus.good;
    }
  }
}
