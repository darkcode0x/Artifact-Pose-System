import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/schedule.dart';
import '../../providers/schedule_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'schedule_detail_screen.dart';

class ScheduleScreen extends StatefulWidget {
  const ScheduleScreen({super.key});

  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ScheduleProvider>().refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ScheduleProvider>();
    final schedulesToday = provider.forSelectedDate();

    return Scaffold(
      appBar: AppBar(title: const Text('Inspection Schedule')),
      body: RefreshIndicator(
        onRefresh: () => context.read<ScheduleProvider>().refresh(),
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              _DateSelector(
                selected: provider.selectedDate,
                onChanged: (d) => context
                    .read<ScheduleProvider>()
                    .selectDate(d),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: schedulesToday.isEmpty
                    ? const EmptyStateView(
                        icon: Icons.event_busy_outlined,
                        title: 'No inspection scheduled',
                      )
                    : ListView.separated(
                        itemCount: schedulesToday.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: 12),
                        itemBuilder: (context, index) =>
                            _ScheduleItem(schedule: schedulesToday[index]),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DateSelector extends StatelessWidget {
  final DateTime selected;
  final ValueChanged<DateTime> onChanged;

  const _DateSelector({required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final today = DateTime.now();
    final start = DateTime(today.year, today.month, today.day);
    final days = List<DateTime>.generate(
      14,
      (i) => start.add(Duration(days: i)),
    );

    return SizedBox(
      height: 84,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: days.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final d = days[index];
          final isSelected = d.year == selected.year &&
              d.month == selected.month &&
              d.day == selected.day;
          return InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => onChanged(d),
            child: Container(
              width: 64,
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary : AppColors.surface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    DateFormat('E').format(d),
                    style: TextStyle(
                      color: isSelected
                          ? Colors.white70
                          : AppColors.textMuted,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${d.day}',
                    style: TextStyle(
                      color: isSelected ? Colors.white : Colors.black87,
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ScheduleItem extends StatelessWidget {
  final Schedule schedule;
  const _ScheduleItem({required this.schedule});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: AppColors.primary.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.event_note, color: AppColors.primary),
        ),
        title: Text(
          schedule.artifactName ?? 'Artifact #${schedule.artifactId}',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          '${schedule.scheduledTime} • ${schedule.operatorUsername.isEmpty ? 'Unassigned' : schedule.operatorUsername}',
        ),
        trailing: schedule.completed
            ? const Icon(Icons.check_circle,
                color: AppColors.statusGood)
            : const Icon(Icons.chevron_right,
                color: AppColors.textMuted),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ScheduleDetailScreen(schedule: schedule),
          ),
        ),
      ),
    );
  }
}
