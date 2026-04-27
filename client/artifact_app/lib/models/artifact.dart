import 'artifact_status.dart';

class Artifact {
  final int id;
  final String name;
  final String description;
  final String location;
  final ArtifactStatus status;
  final bool hasImage;
  final String? referenceImagePath;
  final DateTime createdAt;
  final DateTime updatedAt;

  Artifact({
    required this.id,
    required this.name,
    required this.description,
    required this.location,
    required this.status,
    required this.hasImage,
    required this.referenceImagePath,
    required this.createdAt,
    required this.updatedAt,
  });

  Artifact copyWith({
    String? name,
    String? description,
    String? location,
    ArtifactStatus? status,
    bool? hasImage,
    String? referenceImagePath,
    DateTime? updatedAt,
  }) {
    return Artifact(
      id: id,
      name: name ?? this.name,
      description: description ?? this.description,
      location: location ?? this.location,
      status: status ?? this.status,
      hasImage: hasImage ?? this.hasImage,
      referenceImagePath: referenceImagePath ?? this.referenceImagePath,
      createdAt: createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  factory Artifact.fromJson(Map<String, dynamic> json) {
    return Artifact(
      id: json['id'] as int,
      name: json['name'] as String? ?? '',
      description: json['description'] as String? ?? '',
      location: json['location'] as String? ?? '',
      status: ArtifactStatus.fromWire(json['status'] as String?),
      hasImage: json['has_image'] as bool? ?? false,
      referenceImagePath: json['reference_image_path'] as String?,
      createdAt:
          DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
      updatedAt:
          DateTime.tryParse(json['updated_at'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
