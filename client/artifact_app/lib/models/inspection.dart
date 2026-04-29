import 'artifact_status.dart';

enum InspectionType {
  scheduled, // Định kỳ
  sudden;    // Bất chợt

  String get label => this == scheduled ? 'Scheduled' : 'Sudden';
  
  static InspectionType fromWire(String? value) {
    if (value == 'scheduled') return InspectionType.scheduled;
    return InspectionType.sudden;
  }
}

class Inspection {
  final int id;
  final int artifactId;
  final int? scheduleId;
  final String? previousImagePath;
  final String currentImagePath;
  final String? heatmapPath;
  final int damageScore;
  final String? ssimScore;
  final ArtifactStatus status;
  final InspectionType inspectionType;
  final String description;
  final String? createdBy;
  final DateTime createdAt;

  Inspection({
    required this.id,
    required this.artifactId,
    this.scheduleId,
    this.previousImagePath,
    required this.currentImagePath,
    this.heatmapPath,
    required this.damageScore,
    this.ssimScore,
    required this.status,
    required this.inspectionType,
    required this.description,
    this.createdBy,
    required this.createdAt,
  });

  factory Inspection.fromJson(Map<String, dynamic> json) {
    return Inspection(
      id: json['id'] as int,
      artifactId: json['artifact_id'] as int,
      scheduleId: json['schedule_id'] as int?,
      previousImagePath: json['previous_image_path'] as String?,
      currentImagePath: json['current_image_path'] as String? ?? '',
      heatmapPath: json['heatmap_path'] as String?,
      damageScore: (json['damage_score'] as num?)?.toInt() ?? 0,
      ssimScore: json['ssim_score'] as String?,
      status: ArtifactStatus.fromWire(json['status'] as String?),
      inspectionType: InspectionType.fromWire(json['inspection_type'] as String?),
      description: json['description'] as String? ?? '',
      createdBy: json['created_by'] as String?,
      createdAt:
          DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
