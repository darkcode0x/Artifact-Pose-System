import 'package:flutter/material.dart';

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
      appBar: AppBar(title: const Text('Inspection result')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              StatusBadge(status: inspection.status),
              const SizedBox(height: 16),
              _ScoreCard(inspection: inspection),
              const SizedBox(height: 16),
              if (inspection.previousImagePath != null) ...[
                const _SectionLabel('Reference'),
                _ImagePanel(url: inspection.previousImagePath!),
                const SizedBox(height: 16),
              ],
              const _SectionLabel('Captured image'),
              _ImagePanel(url: inspection.currentImagePath),
              const SizedBox(height: 16),
              if (inspection.heatmapPath != null) ...[
                const _SectionLabel('Damage heatmap'),
                _ImagePanel(url: inspection.heatmapPath!),
                const SizedBox(height: 16),
              ],
              if (inspection.description.isNotEmpty) ...[
                const _SectionLabel('Notes'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Text(inspection.description),
                  ),
                ),
                const SizedBox(height: 16),
              ],
              Text(
                'Inspected ${_formatDate(inspection.createdAt)}'
                '${inspection.createdBy != null ? ' by ${inspection.createdBy}' : ''}',
                style: const TextStyle(color: AppColors.textMuted),
              ),
              const SizedBox(height: 24),
              SizedBox(
                height: 50,
                child: ElevatedButton.icon(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.check),
                  label: const Text('Done'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }
}

class _ScoreCard extends StatelessWidget {
  final Inspection inspection;
  const _ScoreCard({required this.inspection});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: _Metric(
                label: 'Damage',
                value: '${inspection.damageScore}%',
                color: _scoreColor(inspection.damageScore),
              ),
            ),
            Container(width: 1, height: 40, color: AppColors.surfaceMuted),
            Expanded(
              child: _Metric(
                label: 'SSIM',
                value: inspection.ssimScore ?? '—',
                color: AppColors.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _scoreColor(int score) {
    if (score < 15) return AppColors.statusGood;
    if (score < 35) return AppColors.statusWarning;
    return AppColors.statusDamaged;
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _Metric({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: AppColors.textMuted)),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        text,
        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
      ),
    );
  }
}

class _ImagePanel extends StatelessWidget {
  final String url;
  const _ImagePanel({required this.url});

  @override
  Widget build(BuildContext context) {
    final resolved = ApiConfig.resolveAssetUrl(url);
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: AspectRatio(
        aspectRatio: 16 / 9,
        child: Image.network(
          resolved,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => Container(
            color: AppColors.surfaceMuted,
            child: const Center(
              child: Icon(Icons.broken_image_outlined,
                  color: AppColors.textFaint, size: 48),
            ),
          ),
          loadingBuilder: (_, child, progress) {
            if (progress == null) return child;
            return Container(
              color: AppColors.surfaceMuted,
              child: const Center(child: CircularProgressIndicator()),
            );
          },
        ),
      ),
    );
  }
}
