import 'artifact_status.dart';

class Artifact {
  final int id; // Ánh xạ từ artifact_id
  final String name;
  final String? description;
  final String? location;
  final ArtifactStatus status;
  final int? baselineImageId;
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
    this.baselineImageId,
    required this.hasImage,
    this.referenceImagePath,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Artifact.fromJson(Map<String, dynamic> json) {
    return Artifact(
      id: json['id'] as int,
      name: json['name'] as String,
      description: json['description'] as String?,
      location: json['location'] as String?,
      status: ArtifactStatus.fromWire(json['status'] as String?),
      baselineImageId: json['baseline_image_id'] as int?,
      hasImage: json['has_image'] as bool? ?? false,
      referenceImagePath: json['reference_image_path'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}
