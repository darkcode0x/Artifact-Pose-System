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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Heatmap Analysis', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: inspection.heatmapPath != null
                ? Image.network(
                    ApiConfig.resolveAssetUrl(inspection.heatmapPath),
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _imagePlaceholder(Icons.broken_image),
                  )
                : _imagePlaceholder(Icons.analytics_outlined),
          ),
        ),
      ],
    );
  }

  Widget _buildDetailCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _dataRow('Status', StatusBadge(status: inspection.status)),
            const Divider(height: 32),
            _dataRow('Damage Score', Text('${inspection.damageScore}%', 
              style: TextStyle(
                fontSize: 20, 
                fontWeight: FontWeight.bold,
                color: inspection.damageScore > 15 ? Colors.red : Colors.green
              ))),
            const Divider(height: 32),
            _dataRow('Inspection Type', Text(inspection.inspectionType.label)),
            const Divider(height: 32),
            _dataRow('Date', Text(DateFormat('HH:mm dd/MM/yyyy').format(inspection.createdAt))),
            if (inspection.description.isNotEmpty) ...[
              const Divider(height: 32),
              _dataRow('Notes', Text(inspection.description, textAlign: TextAlign.right)),
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

  Widget _imagePlaceholder(IconData icon) {
    return Container(
      color: AppColors.surfaceMuted,
      child: Center(child: Icon(icon, size: 48, color: AppColors.textFaint)),
    );
  }
}
