class ImageComparison {

  final int comparisonId;
  final int artifactId;

  final String previousImage;
  final String currentImage;
  final String heatmapPath;

  final double damageScore;

  final String status;
  final String description;

  final DateTime createdAt;

  ImageComparison({
    required this.comparisonId,
    required this.artifactId,
    required this.previousImage,
    required this.currentImage,
    required this.heatmapPath,
    required this.damageScore,
    required this.status,
    required this.description,
    required this.createdAt,
  });
}