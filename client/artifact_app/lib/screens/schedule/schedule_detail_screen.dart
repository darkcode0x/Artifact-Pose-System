import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/schedule.dart';
import '../../providers/schedule_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class ScheduleDetailScreen extends StatelessWidget {
  final Schedule schedule;

  const ScheduleDetailScreen({super.key, required this.schedule});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Schedule')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _Row(
                        label: 'Artifact',
                        value: schedule.artifactName ??
                            'Artifact #${schedule.artifactId}',
                      ),
                      const Divider(height: 28),
                      _Row(
                        label: 'Date',
                        value: DateFormat('EEE, dd MMM yyyy')
                            .format(schedule.scheduledDate.toLocal()),
                      ),
                      const Divider(height: 28),
                      _Row(label: 'Time', value: schedule.scheduledTime),
                      const Divider(height: 28),
                      _Row(
                        label: 'Operator',
                        value: schedule.operatorUsername.isEmpty
                            ? 'Unassigned'
                            : schedule.operatorUsername,
                      ),
                      if (schedule.notes.isNotEmpty) ...[
                        const Divider(height: 28),
                        _Row(label: 'Notes', value: schedule.notes),
                      ],
                      const Divider(height: 28),
                      _Row(
                        label: 'Status',
                        value:
                            schedule.completed ? 'Completed' : 'Scheduled',
                        color: schedule.completed
                            ? AppColors.statusGood
                            : AppColors.statusNeedCheck,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                height: 50,
                child: ElevatedButton.icon(
                  onPressed: () async {
                    await context
                        .read<ScheduleProvider>()
                        .markComplete(schedule.id, !schedule.completed);
                    if (context.mounted) Navigator.pop(context);
                  },
                  icon: Icon(schedule.completed
                      ? Icons.undo
                      : Icons.check_circle_outline),
                  label: Text(schedule.completed
                      ? 'Mark as scheduled'
                      : 'Mark as completed'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _Row({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textMuted,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            color: color ?? Colors.black87,
            fontWeight: color != null ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ],
    );
  }
}
