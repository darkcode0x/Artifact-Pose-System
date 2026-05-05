import 'dart:convert';
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
  final String id; // VARCHAR(6)
  final String artifactId; // VARCHAR(6)
  final String? scheduleId; // VARCHAR(6)
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
  final String? detectionsJson;

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
    this.detectionsJson,
  });

  factory Inspection.fromJson(Map<String, dynamic> json) {
    return Inspection(
      id: json['id']?.toString() ?? '',
      artifactId: json['artifact_id']?.toString() ?? '',
      scheduleId: json['schedule_id']?.toString(),
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
      detectionsJson: json['detections_json'] as String?,
    );
  }

  /// Path to the AI-annotated image (bounding boxes drawn by YOLO).
  /// Parsed from the new detections_json format.
  String? get annotatedImagePath {
    if (detectionsJson == null || detectionsJson!.isEmpty) return null;
    try {
      final parsed = jsonDecode(detectionsJson!);
      if (parsed is Map) return parsed['annotated_path'] as String?;
    } catch (_) {}
    return null;
  }

  /// Parse YOLO detections from detectionsJson.
  /// Returns flat list of detection maps with class_name, confidence, bbox_xyxy.
  List<Map<String, dynamic>> get detections {
    if (detectionsJson == null || detectionsJson!.isEmpty) return [];
    try {
      final parsed = jsonDecode(detectionsJson!) as dynamic;
      // New format: {"annotated_path": "...", "results": [...]}
      final rawList = (parsed is Map ? parsed['results'] : parsed) as List<dynamic>? ?? [];
      final all = <Map<String, dynamic>>[];
      for (final item in rawList) {
        final dets = (item as Map<String, dynamic>)['detections'] as List<dynamic>? ?? [];
        for (final d in dets) {
          all.add(Map<String, dynamic>.from(d as Map));
        }
      }
      return all;
    } catch (_) {
      return [];
    }
  }
}
