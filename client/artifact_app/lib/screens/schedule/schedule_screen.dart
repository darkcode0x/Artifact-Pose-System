import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/schedule.dart';
import '../../providers/schedule_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import 'add_schedule_screen.dart';
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

  Future<void> _pickDate(BuildContext context, DateTime current) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 5),
    );
    if (picked != null && context.mounted) {
      context.read<ScheduleProvider>().selectDate(picked);
    }
  }

  Future<void> _openCreate(BuildContext context, DateTime initialDate) async {
    final created = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => AddScheduleScreen(initialDate: initialDate),
      ),
    );
    if (created == true && context.mounted) {
      // Make sure the just-created schedule shows up.
      context.read<ScheduleProvider>().refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ScheduleProvider>();
    final schedulesToday = provider.forSelectedDate();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Inspection Schedule'),
        actions: [
          IconButton(
            tooltip: 'Pick date',
            icon: const Icon(Icons.calendar_today),
            onPressed: () => _pickDate(context, provider.selectedDate),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => context.read<ScheduleProvider>().refresh(),
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              _DateSelector(
                selected: provider.selectedDate,
                onChanged: (d) =>
                    context.read<ScheduleProvider>().selectDate(d),
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
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('Add schedule'),
        onPressed: () => _openCreate(context, provider.selectedDate),
      ),
    );
  }
}

/// Horizontally scrollable strip of days centered on the currently selected
/// date, so the user can swipe back to past days as well as forward.
class _DateSelector extends StatefulWidget {
  final DateTime selected;
  final ValueChanged<DateTime> onChanged;

  const _DateSelector({required this.selected, required this.onChanged});

  @override
  State<_DateSelector> createState() => _DateSelectorState();
}

class _DateSelectorState extends State<_DateSelector> {
  static const int _daysBefore = 30;
  static const int _daysAfter = 30;
  static const double _itemWidth = 64;
  static const double _itemSpacing = 8;

  late final ScrollController _controller;
  late DateTime _anchor;

  @override
  void initState() {
    super.initState();
    _anchor = _dayOnly(widget.selected);
    _controller = ScrollController(
      initialScrollOffset: _offsetFor(_anchor, widget.selected),
    );
  }

  @override
  void didUpdateWidget(covariant _DateSelector oldWidget) {
    super.didUpdateWidget(oldWidget);
    final newSel = _dayOnly(widget.selected);
    final oldSel = _dayOnly(oldWidget.selected);
    if (newSel == oldSel) return;

    final inWindow = !newSel.isBefore(_startDate(_anchor)) &&
        !newSel.isAfter(_endDate(_anchor));
    if (!inWindow) {
      // User jumped far away (e.g. via the calendar picker). Re-anchor the
      // strip so the new date is centered.
      setState(() => _anchor = newSel);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!_controller.hasClients) return;
        _controller.jumpTo(_offsetFor(_anchor, newSel));
      });
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!_controller.hasClients) return;
        _controller.animateTo(
          _offsetFor(_anchor, newSel),
          duration: const Duration(milliseconds: 240),
          curve: Curves.easeOut,
        );
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  DateTime _dayOnly(DateTime d) => DateTime(d.year, d.month, d.day);
  DateTime _startDate(DateTime anchor) =>
      anchor.subtract(const Duration(days: _daysBefore));
  DateTime _endDate(DateTime anchor) =>
      anchor.add(const Duration(days: _daysAfter));

  double _offsetFor(DateTime anchor, DateTime target) {
    final start = _startDate(anchor);
    final index = target.difference(start).inDays;
    // Try to leave a few items visible before the selected one.
    final raw = (index - 2) * (_itemWidth + _itemSpacing);
    return raw < 0 ? 0 : raw;
  }

  @override
  Widget build(BuildContext context) {
    final start = _startDate(_anchor);
    final today = _dayOnly(DateTime.now());
    final total = _daysBefore + _daysAfter + 1;

    return SizedBox(
      height: 84,
      child: ListView.separated(
        controller: _controller,
        scrollDirection: Axis.horizontal,
        itemCount: total,
        separatorBuilder: (_, __) => const SizedBox(width: _itemSpacing),
        itemBuilder: (context, index) {
          final d = start.add(Duration(days: index));
          final isSelected = d == _dayOnly(widget.selected);
          final isToday = d == today;
          return InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => widget.onChanged(d),
            child: Container(
              width: _itemWidth,
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary : AppColors.surface,
                borderRadius: BorderRadius.circular(14),
                border: isToday && !isSelected
                    ? Border.all(color: AppColors.primary, width: 1.2)
                    : null,
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
