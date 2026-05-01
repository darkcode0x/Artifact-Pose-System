import 'artifact_status.dart';

class Artifact {
  final String id; // VARCHAR(6) from PostgreSQL
  final String name;
  final String? description;
  final String? location;
  final ArtifactStatus status;
  final int inspectionIntervalDays; // Thêm trường chu kỳ (ngày)
  final String? baselineImageId;
  final bool hasImage;
  final String? referenceImagePath;
  final DateTime createdAt;
  final DateTime updatedAt;

  Artifact({
    required this.id,
    required this.name,
    this.description,
    this.location,
    required this.status,
    required this.inspectionIntervalDays,
    this.baselineImageId,
    required this.hasImage,
    this.referenceImagePath,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Artifact.fromJson(Map<String, dynamic> json) {
    return Artifact(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? '',
      description: json['description'] as String?,
      location: json['location'] as String?,
      status: ArtifactStatus.fromWire(json['status'] as String?),
      inspectionIntervalDays: json['inspection_interval_days'] as int? ?? 0,
      baselineImageId: json['baseline_image_id']?.toString(),
      hasImage: json['has_image'] as bool? ?? false,
      referenceImagePath: json['reference_image_path'] as String?,
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at']?.toString() ?? '') ?? DateTime.now(),
    );
  }
}
