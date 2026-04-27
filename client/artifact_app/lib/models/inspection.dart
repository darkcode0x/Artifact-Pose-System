import 'artifact_status.dart';

class Inspection {
  final int id;
  final int artifactId;
  final String? previousImagePath;
  final String currentImagePath;
  final String? heatmapPath;
  final int damageScore;
  final String? ssimScore;
  final ArtifactStatus status;
  final String description;
  final String? createdBy;
  final DateTime createdAt;

  Inspection({
    required this.id,
    required this.artifactId,
    required this.previousImagePath,
    required this.currentImagePath,
    required this.heatmapPath,
    required this.damageScore,
    required this.ssimScore,
    required this.status,
    required this.description,
    required this.createdBy,
    required this.createdAt,
  });

  factory Inspection.fromJson(Map<String, dynamic> json) {
    return Inspection(
      id: json['id'] as int,
      artifactId: json['artifact_id'] as int,
      previousImagePath: json['previous_image_path'] as String?,
      currentImagePath: json['current_image_path'] as String? ?? '',
      heatmapPath: json['heatmap_path'] as String?,
      damageScore: (json['damage_score'] as num?)?.toInt() ?? 0,
      ssimScore: json['ssim_score'] as String?,
      status: ArtifactStatus.fromWire(json['status'] as String?),
      description: json['description'] as String? ?? '',
      createdBy: json['created_by'] as String?,
      createdAt:
          DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
