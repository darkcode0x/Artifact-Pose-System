import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../models/artifact_status.dart';
import '../../providers/artifact_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../../widgets/status_badge.dart';
import '../artifact/artifact_detail_screen.dart';

class AlertScreen extends StatefulWidget {
  const AlertScreen({super.key});

  @override
  State<AlertScreen> createState() => _AlertScreenState();
}

class _AlertScreenState extends State<AlertScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ArtifactProvider>().refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ArtifactProvider>();
    final alerts = provider.alerts;

    return Scaffold(
      appBar: AppBar(title: const Text('Alerts')),
      body: RefreshIndicator(
        onRefresh: () => context.read<ArtifactProvider>().refresh(),
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: alerts.isEmpty
              ? const EmptyStateView(
                  icon: Icons.check_circle_outline,
                  title: 'All clear',
                  subtitle: 'No artifacts currently flagged.',
                )
              : ListView.separated(
                  itemCount: alerts.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) =>
                      _AlertCard(artifact: alerts[index]),
                ),
        ),
      ),
    );
  }
}

class _AlertCard extends StatelessWidget {
  final Artifact artifact;
  const _AlertCard({required this.artifact});

  Future<void> _resolve(BuildContext context) async {
    await context
        .read<ArtifactProvider>()
        .updateStatus(artifact.id, ArtifactStatus.good);
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${artifact.name} marked as good')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.warning_amber_outlined,
                    color: AppColors.statusWarning, size: 28),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    artifact.name,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                StatusBadge(status: artifact.status, compact: true),
              ],
            ),
            const SizedBox(height: 8),
            if (artifact.location != null && artifact.location!.isNotEmpty)
              Text('Location: ${artifact.location}',
                  style: const TextStyle(color: AppColors.textMuted)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                ElevatedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          ArtifactDetailScreen(artifact: artifact),
                    ),
                  ),
                  icon: const Icon(Icons.search),
                  label: const Text('Inspect'),
                ),
                OutlinedButton.icon(
                  onPressed: () => _resolve(context),
                  icon: const Icon(Icons.check),
                  label: const Text('Resolve'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
