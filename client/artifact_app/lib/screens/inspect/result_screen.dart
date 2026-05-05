import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/inspection.dart';
import '../../services/api_config.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../../widgets/status_badge.dart';

class ResultScreen extends StatelessWidget {
  final Inspection inspection;

  const ResultScreen({super.key, required this.inspection});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Inspection Result')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              _buildImageComparison(),
              const SizedBox(height: 24),
              _buildDetailCard(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildImageComparison() {
    final heatUrl = inspection.heatmapPath != null
        ? ApiConfig.resolveAssetUrl(inspection.heatmapPath)
        : null;
    final detectUrl = inspection.annotatedImagePath != null
        ? ApiConfig.resolveAssetUrl(inspection.annotatedImagePath)
        : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Heatmap ────────────────────────────────────────────────────────
        const Text('Heatmap so sánh SSIM',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: heatUrl != null && heatUrl.isNotEmpty
                ? Image.network(
                    heatUrl,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _imagePlaceholder(Icons.broken_image),
                  )
                : _imagePlaceholder(Icons.analytics_outlined,
                    label: inspection.heatmapPath == null
                        ? 'Chưa có ảnh tham chiếu\n(Cần chạy khởi tạo Golden Pose trước)'
                        : 'Không tải được heatmap'),
          ),
        ),
        const SizedBox(height: 20),
        // ── AI Detection annotated image ────────────────────────────────────
        const Text('AI Detection — kết quả phát hiện hư hại',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: detectUrl != null && detectUrl.isNotEmpty
                ? Image.network(
                    detectUrl,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _imagePlaceholder(Icons.broken_image),
                  )
                : _imagePlaceholder(Icons.image_search_outlined,
                    label: 'Không có kết quả AI\n(Model chưa detect được gì)'),
          ),
        ),
      ],
    );
  }

  Widget _buildDetailCard(BuildContext context) {
    final detections = inspection.detections;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _dataRow('Status', StatusBadge(status: inspection.status)),
            const Divider(height: 32),
            _dataRow('Damage Score', Text('${inspection.damageScore}%',
                style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: inspection.damageScore > 15 ? Colors.red : Colors.green))),
            if (inspection.ssimScore != null) ...[
              const Divider(height: 32),
              _dataRow('SSIM Score', Text(inspection.ssimScore!, style: const TextStyle(fontWeight: FontWeight.w500))),
            ],
            const Divider(height: 32),
            _dataRow('Inspection Type', Text(inspection.inspectionType.label)),
            const Divider(height: 32),
            _dataRow('Date', Text(DateFormat('HH:mm dd/MM/yyyy').format(inspection.createdAt))),
            if (inspection.description.isNotEmpty) ...[
              const Divider(height: 32),
              _dataRow('Notes', Text(inspection.description, textAlign: TextAlign.right)),
            ],
            if (detections.isNotEmpty) ...[
              const Divider(height: 32),
              const Text('AI Detections', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(height: 10),
              ...detections.map((d) {
                final name = d['class_name']?.toString() ?? 'Unknown';
                final conf = ((d['confidence'] as num?)?.toDouble() ?? 0.0) * 100;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded, size: 18, color: Colors.orange),
                      const SizedBox(width: 8),
                      Expanded(child: Text(name, style: const TextStyle(fontWeight: FontWeight.w500))),
                      Text('${conf.toStringAsFixed(1)}%',
                          style: TextStyle(
                              color: conf > 70 ? Colors.red : Colors.orange,
                              fontWeight: FontWeight.bold)),
                    ],
                  ),
                );
              }),
            ] else ...[
              const Divider(height: 32),
              const Row(
                children: [
                  Icon(Icons.check_circle_outline, size: 18, color: Colors.green),
                  SizedBox(width: 8),
                  Text('No defects detected by AI', style: TextStyle(color: AppColors.textMuted)),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _dataRow(String label, Widget value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textMuted, fontWeight: FontWeight.w500)),
        Flexible(child: value),
      ],
    );
  }

  Widget _imagePlaceholder(IconData icon, {String? label}) {
    return Container(
      color: AppColors.surfaceMuted,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: AppColors.textFaint),
            if (label != null)
              Padding(
                padding: const EdgeInsets.only(top: 8, left: 16, right: 16),
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textFaint,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
