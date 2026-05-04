import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../models/artifact_status.dart';
import '../../models/inspection.dart';
import '../../providers/artifact_provider.dart';
import '../../services/api_config.dart';
import '../../services/token_storage.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../../widgets/status_badge.dart';
import '../capture/capture_screen.dart';
import '../inspect/result_screen.dart';
import 'edit_artifact_screen.dart';

class ArtifactDetailScreen extends StatelessWidget {
  final Artifact artifact;

  const ArtifactDetailScreen({super.key, required this.artifact});

  @override
  Widget build(BuildContext context) {
    return _ArtifactDetailContent(artifact: artifact);
  }
}

class _ArtifactDetailContent extends StatefulWidget {
  final Artifact artifact;
  const _ArtifactDetailContent({required this.artifact});

  @override
  State<_ArtifactDetailContent> createState() => _ArtifactDetailContentState();
}

class _ArtifactDetailContentState extends State<_ArtifactDetailContent> {
  bool _busy = false;
  late Artifact _artifact;
  String? _userRole;

  @override
  void initState() {
    super.initState();
    _artifact = widget.artifact;
    _loadRole();
  }

  Future<void> _loadRole() async {
    final role = await context.read<TokenStorage>().readRole();
    if (mounted) setState(() => _userRole = role);
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
    // Sửa lỗi: Truyền picked (XFile) trực tiếp
    final updated = await context
        .read<ArtifactProvider>()
        .uploadReference(_artifact.id, picked);
        
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (updated != null) _artifact = updated;
    });
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

  Future<void> _editArtifact() async {
    final updated = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => EditArtifactScreen(artifact: _artifact),
      ),
    );
    if (updated == true && mounted) {
      await context.read<ArtifactProvider>().refresh();
      final refreshed = context.read<ArtifactProvider>().artifacts.firstWhere((a) => a.id == _artifact.id);
      setState(() => _artifact = refreshed);
    }
  }

  Future<void> _archiveArtifact() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Archive Artifact'),
        content: Text('Are you sure you want to stop displaying "${_artifact.name}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.orange),
            child: const Text('Archive'),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      setState(() => _busy = true);
      try {
        await context.read<ArtifactProvider>().updateStatus(_artifact.id, ArtifactStatus.archived);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Artifact archived successfully')));
          Navigator.pop(context);
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${e.toString()}')));
        }
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = _userRole == 'admin';

    return Scaffold(
      appBar: AppBar(
        title: Text(_artifact.name),
        actions: [
          IconButton(
            tooltip: 'Edit artifact',
            icon: const Icon(Icons.edit_outlined),
            onPressed: _editArtifact,
          ),
          IconButton(
            tooltip: 'Inspection history',
            icon: const Icon(Icons.history),
            onPressed: _viewHistory,
          ),
          if (isAdmin)
            IconButton(
              tooltip: 'Archive artifact',
              icon: const Icon(Icons.archive_outlined, color: Colors.orangeAccent),
              onPressed: _archiveArtifact,
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
                              value: (_artifact.description != null && _artifact.description!.isNotEmpty)
                                  ? _artifact.description!
                                  : '—',
                            ),
                            const Divider(height: 22),
                            _InfoRow(
                              icon: Icons.place_outlined,
                              title: 'Location',
                              value: (_artifact.location != null && _artifact.location!.isNotEmpty)
                                  ? _artifact.location!
                                  : '—',
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    if (!_artifact.hasImage)
                      _CallToAction(
                        icon: Icons.settings_remote,
                        label: 'Trigger Device Camera (Reference)',
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
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _formatDate(inspection.createdAt),
              style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
            ),
            Text(
              'Type: ${inspection.inspectionType.label}',
              style: TextStyle(
                color: inspection.inspectionType == InspectionType.scheduled ? Colors.blue : Colors.orange,
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        trailing: StatusBadge(status: inspection.status, compact: true),
        onTap: () {
          Navigator.pop(context); // Close sheet
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ResultScreen(inspection: inspection),
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
