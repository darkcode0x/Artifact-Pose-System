import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../models/inspection.dart';
import '../../providers/artifact_provider.dart';
import '../../services/api_config.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../../widgets/status_badge.dart';
import '../capture/capture_screen.dart';
import '../inspect/result_screen.dart';

class ArtifactDetailScreen extends StatefulWidget {
  final Artifact artifact;

  const ArtifactDetailScreen({super.key, required this.artifact});

  @override
  State<ArtifactDetailScreen> createState() => _ArtifactDetailScreenState();
}

class _ArtifactDetailScreenState extends State<ArtifactDetailScreen> {
  bool _busy = false;
  late Artifact _artifact;

  @override
  void initState() {
    super.initState();
    _artifact = widget.artifact;
  }

  Future<void> _captureReference() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.camera,
      maxWidth: 1920,
      imageQuality: 92,
    );
    if (picked == null || !mounted) return;

    setState(() => _busy = true);
    final updated = await context
        .read<ArtifactProvider>()
        .uploadReference(_artifact.id, File(picked.path));
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (updated != null) _artifact = updated;
    });
    if (updated == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not upload reference image')),
      );
    }
  }

  Future<void> _runInspection() async {
    final inspection = await Navigator.push<Inspection?>(
      context,
      MaterialPageRoute(
        builder: (_) => CaptureScreen(artifact: _artifact),
      ),
    );
    if (inspection == null || !mounted) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ResultScreen(inspection: inspection),
      ),
    );
  }

  Future<void> _viewHistory() async {
    final inspections =
        await context.read<ArtifactProvider>().historyFor(_artifact.id);
    if (!mounted) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.background,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _HistorySheet(inspections: inspections),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_artifact.name),
        actions: [
          IconButton(
            tooltip: 'Inspection history',
            icon: const Icon(Icons.history),
            onPressed: _viewHistory,
          ),
        ],
      ),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Stack(
            children: [
              SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _ReferenceImage(artifact: _artifact),
                    const SizedBox(height: 18),
                    Text(
                      _artifact.name,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    StatusBadge(status: _artifact.status),
                    const SizedBox(height: 18),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          children: [
                            _InfoRow(
                              icon: Icons.description_outlined,
                              title: 'Description',
                              value: _artifact.description.isEmpty
                                  ? '—'
                                  : _artifact.description,
                            ),
                            const Divider(height: 22),
                            _InfoRow(
                              icon: Icons.place_outlined,
                              title: 'Location',
                              value: _artifact.location.isEmpty
                                  ? '—'
                                  : _artifact.location,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    if (!_artifact.hasImage)
                      _CallToAction(
                        icon: Icons.camera_alt_outlined,
                        label: 'Capture reference image',
                        onPressed: _captureReference,
                      )
                    else
                      _CallToAction(
                        icon: Icons.search,
                        label: 'Run inspection',
                        onPressed: _runInspection,
                      ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
              if (_busy)
                const Positioned.fill(
                  child: ColoredBox(
                    color: Color(0x66000000),
                    child: Center(
                      child: CircularProgressIndicator(color: Colors.white),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ReferenceImage extends StatelessWidget {
  final Artifact artifact;
  const _ReferenceImage({required this.artifact});

  @override
  Widget build(BuildContext context) {
    final url = ApiConfig.resolveAssetUrl(artifact.referenceImagePath);
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: artifact.hasImage && url.isNotEmpty
            ? Image.network(
                url,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _placeholder(broken: true),
              )
            : _placeholder(),
      ),
    );
  }

  Widget _placeholder({bool broken = false}) {
    return Container(
      color: AppColors.surfaceMuted,
      child: Center(
        child: Icon(
          broken
              ? Icons.broken_image_outlined
              : Icons.image_not_supported_outlined,
          size: 56,
          color: AppColors.textFaint,
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;

  const _InfoRow({
    required this.icon,
    required this.title,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppColors.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(color: AppColors.textMuted)),
            ],
          ),
        ),
      ],
    );
  }
}

class _CallToAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onPressed;

  const _CallToAction({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon),
        label: Text(label),
      ),
    );
  }
}

class _HistorySheet extends StatelessWidget {
  final List<Inspection> inspections;
  const _HistorySheet({required this.inspections});

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.6,
      maxChildSize: 0.9,
      minChildSize: 0.4,
      builder: (context, scroll) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.textFaint,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 12),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Inspection history',
                  style:
                      TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: inspections.isEmpty
                    ? const EmptyStateView(
                        icon: Icons.history_toggle_off,
                        title: 'No inspections yet',
                      )
                    : ListView.separated(
                        controller: scroll,
                        itemCount: inspections.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: 10),
                        itemBuilder: (context, index) =>
                            _HistoryItem(inspection: inspections[index]),
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _HistoryItem extends StatelessWidget {
  final Inspection inspection;
  const _HistoryItem({required this.inspection});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.network(
            ApiConfig.resolveAssetUrl(inspection.heatmapPath ??
                inspection.currentImagePath),
            width: 56,
            height: 56,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              width: 56,
              height: 56,
              color: AppColors.surfaceMuted,
              child: const Icon(Icons.image_outlined,
                  color: AppColors.textFaint),
            ),
          ),
        ),
        title: Text(
          'Damage ${inspection.damageScore}%',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          _formatDate(inspection.createdAt),
          style: const TextStyle(color: AppColors.textMuted),
        ),
        trailing: StatusBadge(status: inspection.status, compact: true),
        onTap: () {
          Navigator.pop(context);
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => Scaffold(
                appBar: AppBar(title: const Text('Inspection result')),
                body: SafeArea(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_formatDate(inspection.createdAt),
                            style: const TextStyle(color: AppColors.textMuted)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }
}
