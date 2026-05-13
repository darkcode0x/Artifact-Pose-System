import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/inspection.dart';
import '../../services/api_config.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../../widgets/status_badge.dart';

// English display names for YOLO classes
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

// ─── SSIM grade thresholds ────────────────────────────────────────────────────
// Formula: SSIM = 0.6 × SSIM_grayscale + 0.4 × mean(SSIM_R, SSIM_G, SSIM_B)
// Value range: 0 (completely different) → 1 (identical)
class _SsimGrade {
  final String label;      // Short grade label
  final String description; // Plain-language meaning
  final Color color;
  final IconData icon;

  const _SsimGrade(this.label, this.description, this.color, this.icon);

  static _SsimGrade from(double ssim) {
    if (ssim >= 0.95) return const _SsimGrade('Excellent', 'Artifact is well preserved — structural and color similarity is very high.', AppColors.statusGood, Icons.verified_outlined);
    if (ssim >= 0.85) return const _SsimGrade('Good',      'Minor variations detected — likely lighting or small surface changes.', Colors.lightGreen, Icons.thumb_up_outlined);
    if (ssim >= 0.70) return const _SsimGrade('Fair',      'Noticeable differences found — artifact may have surface wear or damage.', Colors.orange, Icons.warning_amber_outlined);
    if (ssim >= 0.50) return const _SsimGrade('Poor',      'Significant structural differences — damage or major condition change detected.', Colors.deepOrange, Icons.report_outlined);
    return const _SsimGrade('Critical', 'Severe degradation — artifact condition has changed drastically.', AppColors.statusDamaged, Icons.dangerous_outlined);
  }
}

// ─────────────────────────────────────────────────────────────────────────────

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
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: StatusBadge(status: inspection.status),
            ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.thermostat_outlined), text: 'SSIM Analysis'),
              Tab(icon: Icon(Icons.manage_search_outlined), text: 'AI Detection'),
            ],
          ),
        ),
        body: SafeArea(
          child: TabBarView(
            children: [
              _SsimTab(inspection: inspection),
              _DetectTab(inspection: inspection),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 1 — SSIM Analysis
// ═══════════════════════════════════════════════════════════════════════════════

class _SsimTab extends StatelessWidget {
  final Inspection inspection;
  const _SsimTab({required this.inspection});

  @override
  Widget build(BuildContext context) {
    final ssim = inspection.ssimValue;
    final damagePct = inspection.ssimDamagePct;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ── Overall grade card ─────────────────────────────────────────
        if (ssim != null) ...[
          _buildGradeCard(ssim, damagePct),
          const SizedBox(height: 16),
          _buildSsimBreakdown(ssim),
          const SizedBox(height: 16),
        ] else
          _buildNoReferenceCard(),

        // ── Heatmap image ─────────────────────────────────────────────
        _ImageCard(
          title: 'SSIM Heatmap',
          subtitle: 'Red/orange = high difference · Blue/purple = closely matched',
          icon: Icons.thermostat_outlined,
          url: inspection.heatmapPath != null
              ? ApiConfig.resolveAssetUrl(inspection.heatmapPath)
              : null,
          emptyLabel: inspection.heatmapPath == null
              ? 'No heatmap available\n(Initialize Golden Pose first)'
              : 'Could not load heatmap',
        ),
        const SizedBox(height: 16),

        // ── 3-image row: original / aligned / heatmap ─────────────────
        _buildThreeImageRow(context),
        const SizedBox(height: 16),

        // ── Algorithm explainer ───────────────────────────────────────
        _buildAlgorithmCard(),
        const SizedBox(height: 16),

        // ── Meta ──────────────────────────────────────────────────────
        _buildMetaCard(),
        const SizedBox(height: 24),
      ],
    );
  }

  // ── Overall grade ──────────────────────────────────────────────────────────
  Widget _buildGradeCard(double ssim, double? damagePct) {
    final grade = _SsimGrade.from(ssim);
    final pct = ssim * 100;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: grade.color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: grade.color.withOpacity(0.35), width: 1.5),
      ),
      child: Column(
        children: [
          Row(
            children: [
              // Big circular SSIM indicator
              SizedBox(
                width: 72,
                height: 72,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: ssim.clamp(0.0, 1.0),
                      strokeWidth: 6,
                      backgroundColor: grade.color.withOpacity(0.15),
                      valueColor: AlwaysStoppedAnimation<Color>(grade.color),
                    ),
                    Text(
                      '${pct.toStringAsFixed(1)}%',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: grade.color,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(grade.icon, size: 18, color: grade.color),
                        const SizedBox(width: 6),
                        Text(
                          'SSIM Grade: ${grade.label}',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: grade.color,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      grade.description,
                      style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (damagePct != null) ...[
            const SizedBox(height: 14),
            const Divider(height: 1),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _StatItem(
                  label: 'Similarity',
                  value: '${pct.toStringAsFixed(1)}%',
                  color: grade.color,
                  tooltip: 'How structurally similar the artifact is to the reference (higher = better)',
                ),
                _StatItem(
                  label: 'Deviation area',
                  value: '${damagePct.toStringAsFixed(1)}%',
                  color: damagePct > 10 ? Colors.orange : AppColors.statusGood,
                  tooltip: 'Percentage of visible area showing structural differences (lower = better)',
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  // ── Breakdown bars ─────────────────────────────────────────────────────────
  Widget _buildSsimBreakdown(double ssim) {
    final summary = inspection.ssimSummary;
    final grayVal = (summary?['ssim_gray'] as num?)?.toDouble();
    final colorVal = (summary?['ssim_color'] as num?)?.toDouble();

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.bar_chart, size: 16, color: AppColors.primary),
              SizedBox(width: 6),
              Text('Score Breakdown', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 12),
          _SsimBar(
            label: 'Overall (60% struct + 40% color)',
            value: ssim,
            color: _SsimGrade.from(ssim).color,
            bold: true,
          ),
          const SizedBox(height: 8),
          if (grayVal != null)
            _SsimBar(label: 'Structural / Grayscale', value: grayVal, color: Colors.blueGrey),
          if (grayVal != null) const SizedBox(height: 6),
          if (colorVal != null)
            _SsimBar(label: 'Color fidelity (RGB avg)', value: colorVal, color: Colors.purple),
          const SizedBox(height: 10),
          const Text(
            'Formula:  SSIM = 0.6 × SSIM\u2099\u1d44 + 0.4 × mean(SSIM\u1D63, SSIM\u1D4D, SSIM\u1D07)',
            style: TextStyle(fontSize: 11, color: AppColors.textFaint, fontFamily: 'monospace'),
          ),
        ],
      ),
    );
  }

  // ── No reference card ──────────────────────────────────────────────────────
  Widget _buildNoReferenceCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: const Row(
        children: [
          Icon(Icons.info_outline, color: AppColors.textMuted),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'SSIM analysis requires a Golden Pose reference image.\n'
              'Initialize Golden Pose first to enable structural comparison.',
              style: TextStyle(fontSize: 13, color: AppColors.textMuted),
            ),
          ),
        ],
      ),
    );
  }

  // ── Side-by-side mini images ───────────────────────────────────────────────
  Widget _buildThreeImageRow(BuildContext context) {
    final originalUrl = ApiConfig.resolveAssetUrl(inspection.currentImagePath);
    final alignedUrl  = inspection.alignedImagePath != null
        ? ApiConfig.resolveAssetUrl(inspection.alignedImagePath)
        : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.compare, size: 16, color: AppColors.primary),
            SizedBox(width: 6),
            Text('Image Comparison', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(child: _MiniImageTile(label: 'Original', url: originalUrl)),
            const SizedBox(width: 8),
            Expanded(
              child: _MiniImageTile(
                label: 'SIFT-Aligned',
                url: alignedUrl,
                emptyIcon: Icons.align_horizontal_center_outlined,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        const Text(
          'SIFT alignment corrects perspective/rotation before SSIM comparison.',
          style: TextStyle(fontSize: 11, color: AppColors.textFaint),
        ),
      ],
    );
  }

  // ── Algorithm explainer ────────────────────────────────────────────────────
  Widget _buildAlgorithmCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.science_outlined, size: 16, color: AppColors.primary),
              SizedBox(width: 6),
              Text('How SSIM Works', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ),
          SizedBox(height: 10),
          _BulletPoint(
            icon: Icons.adjust,
            title: 'SIFT Feature Alignment',
            body: 'The inspection image is first aligned to the reference using SIFT keypoint matching + RANSAC homography, correcting for camera angle and position changes.',
          ),
          SizedBox(height: 8),
          _BulletPoint(
            icon: Icons.grid_view_outlined,
            title: 'Structural Similarity (SSIM)',
            body: 'SSIM compares local patches of 7×7 pixels for luminance, contrast, and structure. Score = 0.6 × grayscale + 0.4 × average RGB channels.',
          ),
          SizedBox(height: 8),
          _BulletPoint(
            icon: Icons.thermostat_outlined,
            title: 'Difference Heatmap',
            body: 'The per-pixel SSIM difference map is rendered with JET colormap. Blue/purple = low difference. Yellow/red = high difference.',
          ),
          SizedBox(height: 8),
          _BulletPoint(
            icon: Icons.crop_free_outlined,
            title: 'Deviation Area %',
            body: 'Otsu adaptive thresholding finds significant-difference regions. Morphological filtering removes noise. The contour area is expressed as % of total valid pixels.',
          ),
        ],
      ),
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
            _MetaRow(
              label: 'Date',
              value: DateFormat('HH:mm dd/MM/yyyy').format(inspection.createdAt),
            ),
            if (inspection.description.isNotEmpty) ...[
              const Divider(height: 22),
              _MetaRow(label: 'Note', value: inspection.description),
            ],
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 2 — AI Detection
// ═══════════════════════════════════════════════════════════════════════════════

class _DetectTab extends StatelessWidget {
  final Inspection inspection;
  const _DetectTab({required this.inspection});

  @override
  Widget build(BuildContext context) {
    final detections = inspection.detections;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ── 3 images ──────────────────────────────────────────────────
        _ImageCard(
          title: 'Original Image',
          icon: Icons.photo_outlined,
          url: ApiConfig.resolveAssetUrl(inspection.currentImagePath),
        ),
        const SizedBox(height: 14),
        _ImageCard(
          title: 'AI Damage Detection',
          subtitle: 'Bounding boxes drawn by YOLO model. Label = class + confidence.',
          icon: Icons.manage_search_outlined,
          url: inspection.annotatedImagePath != null
              ? ApiConfig.resolveAssetUrl(inspection.annotatedImagePath)
              : null,
          emptyLabel: 'No annotated image — no detections from AI model.',
        ),
        const SizedBox(height: 14),
        _ImageCard(
          title: 'Pose-Aligned Image',
          subtitle: 'SIFT-corrected image used for SSIM comparison.',
          icon: Icons.compare_outlined,
          url: inspection.alignedImagePath != null
              ? ApiConfig.resolveAssetUrl(inspection.alignedImagePath)
              : null,
          emptyLabel: 'No aligned image — initialize Golden Pose first.',
        ),
        const SizedBox(height: 20),

        // ── Detection list ─────────────────────────────────────────────
        _buildDetectionList(detections),
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildDetectionList(List<Map<String, dynamic>> detections) {
    if (detections.isEmpty) {
      return Container(
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
              child: Text('No damage detected by AI model',
                  style: TextStyle(color: AppColors.statusGood, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${detections.length} damage region(s) detected',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
        const SizedBox(height: 10),
        ...detections.map((d) {
          final rawName = d['class_name']?.toString() ?? '';
          final name = _clsLabel[rawName] ?? rawName;
          final conf = ((d['confidence'] as num?)?.toDouble() ?? 0.0) * 100;
          final regionSsim = (d['region_ssim'] as num?)?.toDouble();
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
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(name.isNotEmpty ? name : 'Unknown',
                            style: const TextStyle(fontWeight: FontWeight.w500)),
                        if (regionSsim != null)
                          Text(
                            'Region SSIM: ${(regionSsim * 100).toStringAsFixed(1)}%',
                            style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                          ),
                      ],
                    ),
                  ),
                  Text('${conf.toStringAsFixed(1)}%',
                      style: TextStyle(color: confColor, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Shared / helper widgets
// ═══════════════════════════════════════════════════════════════════════════════

class _ImageCard extends StatelessWidget {
  final String title;
  final String? subtitle;
  final IconData icon;
  final String? url;
  final String? emptyLabel;

  const _ImageCard({
    required this.title,
    required this.icon,
    this.subtitle,
    this.url,
    this.emptyLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 15, color: AppColors.primary),
            const SizedBox(width: 6),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  if (subtitle != null)
                    Text(subtitle!,
                        style: const TextStyle(fontSize: 11, color: AppColors.textFaint)),
                ],
              ),
            ),
            const Icon(Icons.pinch_outlined, size: 13, color: AppColors.textFaint),
            const SizedBox(width: 3),
            const Text('zoom', style: TextStyle(fontSize: 10, color: AppColors.textFaint)),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Container(
            constraints: const BoxConstraints(minHeight: 180, maxHeight: 380),
            width: double.infinity,
            color: AppColors.surfaceMuted,
            child: url != null && url!.isNotEmpty
                ? _ZoomableNetworkImage(url: url!, title: title)
                : _imagePlaceholder(Icons.image_not_supported_outlined,
                    label: emptyLabel ?? 'Image unavailable'),
          ),
        ),
      ],
    );
  }
}

class _MiniImageTile extends StatelessWidget {
  final String label;
  final String? url;
  final IconData emptyIcon;

  const _MiniImageTile({
    required this.label,
    this.url,
    this.emptyIcon = Icons.image_not_supported_outlined,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(fontSize: 11, color: AppColors.textMuted,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: AspectRatio(
            aspectRatio: 4 / 3,
            child: url != null && url!.isNotEmpty
                ? GestureDetector(
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) =>
                            _FullScreenImagePage(url: url!, title: label),
                        fullscreenDialog: true,
                      ),
                    ),
                    child: Image.network(
                      url!,
                      fit: BoxFit.cover,
                      loadingBuilder: (_, child, progress) =>
                          progress == null
                              ? child
                              : const Center(
                                  child: CircularProgressIndicator()),
                      errorBuilder: (_, __, ___) => Container(
                        color: AppColors.surfaceMuted,
                        child: Center(
                            child: Icon(emptyIcon,
                                color: AppColors.textFaint, size: 30)),
                      ),
                    ),
                  )
                : Container(
                    color: AppColors.surfaceMuted,
                    child: Center(
                        child: Icon(emptyIcon,
                            color: AppColors.textFaint, size: 30)),
                  ),
          ),
        ),
      ],
    );
  }
}

class _ZoomableNetworkImage extends StatelessWidget {
  final String url;
  final String title;
  const _ZoomableNetworkImage({required this.url, this.title = 'Image'});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => _FullScreenImagePage(url: url, title: title),
          fullscreenDialog: true,
        ),
      ),
      child: Image.network(
        url,
        fit: BoxFit.contain,
        width: double.infinity,
        loadingBuilder: (_, child, progress) =>
            progress == null
                ? child
                : const Center(child: CircularProgressIndicator()),
        errorBuilder: (_, __, ___) =>
            _imagePlaceholder(Icons.broken_image_outlined),
      ),
    );
  }
}

class _FullScreenImagePage extends StatelessWidget {
  final String url;
  final String title;
  const _FullScreenImagePage({required this.url, required this.title});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(title,
            style: const TextStyle(fontSize: 14, color: Colors.white)),
        actions: [
          IconButton(
            icon: const Icon(Icons.close, color: Colors.white),
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
      body: Center(
        child: InteractiveViewer(
          minScale: 0.5,
          maxScale: 8.0,
          child: Image.network(
            url,
            fit: BoxFit.contain,
            loadingBuilder: (_, child, progress) =>
                progress == null
                    ? child
                    : const Center(
                        child: CircularProgressIndicator(color: Colors.white),
                      ),
            errorBuilder: (_, __, ___) => const Center(
              child: Icon(Icons.broken_image_outlined,
                  color: Colors.white54, size: 64),
            ),
          ),
        ),
      ),
    );
  }
}

class _SsimBar extends StatelessWidget {
  final String label;
  final double value;
  final Color color;
  final bool bold;

  const _SsimBar({
    required this.label,
    required this.value,
    required this.color,
    this.bold = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  color: AppColors.textMuted,
                  fontWeight: bold ? FontWeight.bold : FontWeight.normal,
                ),
              ),
            ),
            Text(
              '${(value * 100).toStringAsFixed(1)}%',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: value.clamp(0.0, 1.0),
            minHeight: bold ? 8 : 5,
            backgroundColor: color.withOpacity(0.15),
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
      ],
    );
  }
}

class _StatItem extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  final String tooltip;

  const _StatItem({
    required this.label,
    required this.value,
    required this.color,
    required this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Column(
        children: [
          Text(value,
              style: TextStyle(
                  fontSize: 22, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(height: 2),
          Text(label,
              style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
        ],
      ),
    );
  }
}

class _BulletPoint extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;
  const _BulletPoint({required this.icon, required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 14, color: AppColors.primary),
        const SizedBox(width: 8),
        Expanded(
          child: RichText(
            text: TextSpan(
              style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
              children: [
                TextSpan(
                    text: '$title:  ',
                    style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: AppColors.textBody)),
                TextSpan(text: body),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

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
        Text(label,
            style: const TextStyle(
                color: AppColors.textMuted, fontWeight: FontWeight.w500)),
        Flexible(
          child: Text(value,
              textAlign: TextAlign.end,
              style:
                  TextStyle(fontWeight: FontWeight.w600, color: valueColor)),
        ),
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
          Icon(icon, size: 40, color: AppColors.textFaint),
          if (label != null)
            Padding(
              padding: const EdgeInsets.only(top: 8, left: 16, right: 16),
              child: Text(label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 11, color: AppColors.textFaint)),
            ),
        ],
      ),
    ),
  );
}

