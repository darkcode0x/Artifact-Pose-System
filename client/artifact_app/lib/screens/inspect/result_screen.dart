import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/inspection.dart';
import '../../services/api_config.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../../widgets/status_badge.dart';

// Damage class display names
const _clsLabel = {
  'material_loss': 'Material Loss',
  'peel': 'Peeling',
  'scratch': 'Scratch',
  'fold': 'Fold / Deformation',
  'writing_marks': 'Writing Marks',
  'dirt': 'Dirt',
  'staning': 'Staining',
  'burn_marks': 'Burn Marks',
};

class ResultScreen extends StatelessWidget {
  final Inspection inspection;

  const ResultScreen({super.key, required this.inspection});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Inspection Result'),
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.thermostat_outlined), text: 'SSIM Heatmap'),
              Tab(icon: Icon(Icons.manage_search_outlined), text: 'AI Detection'),
            ],
          ),
        ),
        body: SafeArea(
          child: ResponsiveBody(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                // ── Score header ─────────────────────────────────────────
                _ScoreHeader(inspection: inspection),
                // ── Tab content ──────────────────────────────────────────
                Expanded(
                  child: TabBarView(
                    children: [
                      _HeatmapTab(inspection: inspection),
                      _DetectTab(inspection: inspection),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────

class _ScoreHeader extends StatelessWidget {
  final Inspection inspection;
  const _ScoreHeader({required this.inspection});

  @override
  Widget build(BuildContext context) {
    final score = inspection.damageScore;
    final Color scoreColor = score < 5
        ? AppColors.statusGood
        : score < 15
            ? AppColors.statusNeedCheck
            : score < 35
                ? AppColors.statusWarning
                : AppColors.statusDamaged;

    // Convert SSIM string "0.9595" → "95.95% tương đồng"
    String ssimLabel = '';
    if (inspection.ssimScore != null) {
      final raw = double.tryParse(inspection.ssimScore!);
      if (raw != null) {
        ssimLabel = '${(raw * 100).toStringAsFixed(1)}% similarity';
      } else {
        ssimLabel = inspection.ssimScore!;
      }
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      color: scoreColor.withOpacity(0.08),
      child: Row(
        children: [
          // Damage score circle
          Container(
            width: 64, height: 64,
            decoration: BoxDecoration(
              color: scoreColor.withOpacity(0.15),
              shape: BoxShape.circle,
              border: Border.all(color: scoreColor, width: 2),
            ),
            child: Center(
              child: Text(
                '${score}%',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: scoreColor),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('Damage Level ', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                    StatusBadge(status: inspection.status, compact: true),
                  ],
                ),
                if (ssimLabel.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(ssimLabel, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                ],
                const SizedBox(height: 4),
                Text(
                  DateFormat('HH:mm — dd/MM/yyyy').format(inspection.createdAt),
                  style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────

class _HeatmapTab extends StatelessWidget {
  final Inspection inspection;
  const _HeatmapTab({required this.inspection});

  @override
  Widget build(BuildContext context) {
    final heatUrl = inspection.heatmapPath != null
        ? ApiConfig.resolveAssetUrl(inspection.heatmapPath)
        : null;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: AspectRatio(
            aspectRatio: 4 / 3,
            child: heatUrl != null && heatUrl.isNotEmpty
                ? Image.network(heatUrl, fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _imagePlaceholder(Icons.broken_image_outlined))
                : _imagePlaceholder(
                    Icons.analytics_outlined,
                    label: inspection.heatmapPath == null
                        ? 'No reference image\n(Run Golden Pose initialization first)'
                        : 'Could not load heatmap',
                  ),
          ),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: AppColors.surfaceMuted, borderRadius: BorderRadius.circular(12)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: AppColors.primary),
                  SizedBox(width: 6),
                  Text('SSIM Heatmap', style: TextStyle(fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 6),
              const Text(
                'The heatmap highlights regions that differ from the golden pose reference. '
                'Red/orange = high deviation. Blue/purple = closely matched.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
              if (inspection.description.isNotEmpty) ...[
                const Divider(height: 18),
                Text(inspection.description, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        _buildMetaCard(),
      ],
    );
  }

  Widget _buildMetaCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            _MetaRow(
              label: 'Inspection Type',
              value: inspection.inspectionType == InspectionType.scheduled ? 'Scheduled' : 'Ad-hoc',
              valueColor: inspection.inspectionType == InspectionType.scheduled ? Colors.blue : Colors.orange,
            ),
            const Divider(height: 22),
            _MetaRow(label: 'Date', value: DateFormat('HH:mm dd/MM/yyyy').format(inspection.createdAt)),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────

class _DetectTab extends StatelessWidget {
  final Inspection inspection;
  const _DetectTab({required this.inspection});

  @override
  Widget build(BuildContext context) {
    final detectUrl = inspection.annotatedImagePath != null
        ? ApiConfig.resolveAssetUrl(inspection.annotatedImagePath)
        : null;
    final detections = inspection.detections;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: AspectRatio(
            aspectRatio: 4 / 3,
            child: detectUrl != null && detectUrl.isNotEmpty
                ? Image.network(detectUrl, fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _imagePlaceholder(Icons.broken_image_outlined))
                : _imagePlaceholder(Icons.image_search_outlined,
                    label: 'No AI results\n(No damage detected by the model)'),
          ),
        ),
        const SizedBox(height: 16),
        if (detections.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.statusGood.withOpacity(0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.statusGood.withOpacity(0.3)),
            ),
            child: const Row(
              children: [
                Icon(Icons.check_circle_outline, color: AppColors.statusGood, size: 22),
                SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'No damage detected',
                    style: TextStyle(color: AppColors.statusGood, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          )
        else ...[
          Text(
            '${detections.length} damage region(s) detected',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
          ),
          const SizedBox(height: 10),
          ...detections.map((d) {
            final rawName = d['class_name']?.toString() ?? '';
            final name = _clsLabel[rawName] ?? rawName;
            final conf = ((d['confidence'] as num?)?.toDouble() ?? 0.0) * 100;
            final Color confColor = conf >= 65
                ? AppColors.statusDamaged
                : conf >= 40
                    ? AppColors.statusWarning
                    : AppColors.statusNeedCheck;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: confColor.withOpacity(0.07),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: confColor.withOpacity(0.25)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, size: 18, color: confColor),
                    const SizedBox(width: 10),
                    Expanded(child: Text(name.isNotEmpty ? name : 'Unknown',
                        style: const TextStyle(fontWeight: FontWeight.w500))),
                    Text('${conf.toStringAsFixed(1)}%',
                        style: TextStyle(color: confColor, fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
            );
          }),
        ],
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────

class _MetaRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  const _MetaRow({required this.label, required this.value, this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textMuted, fontWeight: FontWeight.w500)),
        Text(value, style: TextStyle(fontWeight: FontWeight.w600, color: valueColor)),
      ],
    );
  }
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
              child: Text(label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 12, color: AppColors.textFaint)),
            ),
        ],
      ),
    ),
  );
}
