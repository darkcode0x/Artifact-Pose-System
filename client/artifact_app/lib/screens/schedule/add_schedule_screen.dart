import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../providers/artifact_provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/schedule_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class AddScheduleScreen extends StatefulWidget {
  final DateTime initialDate;

  const AddScheduleScreen({super.key, required this.initialDate});

  @override
  State<AddScheduleScreen> createState() => _AddScheduleScreenState();
}

class _AddScheduleScreenState extends State<AddScheduleScreen> {
  final _formKey = GlobalKey<FormState>();
  final _operatorController = TextEditingController();
  final _notesController = TextEditingController();

  Artifact? _selectedArtifact;
  late DateTime _date;
  TimeOfDay _time = const TimeOfDay(hour: 9, minute: 0);
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _date = DateTime(
      widget.initialDate.year,
      widget.initialDate.month,
      widget.initialDate.day,
    );
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final artifactProvider = context.read<ArtifactProvider>();
      if (artifactProvider.artifacts.isEmpty) {
        artifactProvider.refresh();
      }
      // Default operator to the currently logged-in user.
      final me = context.read<AuthProvider>().username;
      if (me != null && me.isNotEmpty && _operatorController.text.isEmpty) {
        _operatorController.text = me;
      }
    });
  }

  @override
  void dispose() {
    _operatorController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 5),
    );
    if (picked != null) {
      setState(() => _date = picked);
    }
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time,
    );
    if (picked != null) {
      setState(() => _time = picked);
    }
  }

  String _formatTime(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  Future<void> _submit() async {
    if (_selectedArtifact == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an artifact')),
      );
      return;
    }
    if (!_formKey.currentState!.validate()) return;

    setState(() => _submitting = true);
    final created = await context.read<ScheduleProvider>().create(
          artifactId: _selectedArtifact!.id,
          date: _date,
          time: _formatTime(_time),
          operatorUsername: _operatorController.text.trim(),
          notes: _notesController.text.trim(),
        );
    if (!mounted) return;
    setState(() => _submitting = false);

    if (created != null) {
      Navigator.pop(context, true);
    } else {
      final err = context.read<ScheduleProvider>().error ??
          'Could not create schedule';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final artifacts = context.watch<ArtifactProvider>().artifacts;
    final loadingArtifacts = context.watch<ArtifactProvider>().loading;

    return Scaffold(
      appBar: AppBar(title: const Text('Add schedule')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: ListView(
              children: [
                if (loadingArtifacts && artifacts.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else
                  DropdownButtonFormField<Artifact>(
                    value: _selectedArtifact,
                    isExpanded: true,
                    items: artifacts
                        .map(
                          (a) => DropdownMenuItem<Artifact>(
                            value: a,
                            child: Text(
                              a.name.isEmpty ? 'Artifact #${a.id}' : a.name,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (a) => setState(() => _selectedArtifact = a),
                    decoration: const InputDecoration(
                      labelText: 'Artifact',
                      prefixIcon: Icon(Icons.inventory_2_outlined),
                    ),
                  ),
                const SizedBox(height: 14),
                _PickerTile(
                  icon: Icons.calendar_today,
                  label: 'Date',
                  value: DateFormat('EEE, dd MMM yyyy').format(_date),
                  onTap: _pickDate,
                ),
                const SizedBox(height: 14),
                _PickerTile(
                  icon: Icons.access_time,
                  label: 'Time',
                  value: _formatTime(_time),
                  onTap: _pickTime,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _operatorController,
                  decoration: const InputDecoration(
                    labelText: 'Operator username',
                    prefixIcon: Icon(Icons.person_outline),
                  ),
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _notesController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Notes (optional)',
                    prefixIcon: Icon(Icons.notes_outlined),
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  height: 50,
                  child: ElevatedButton.icon(
                    onPressed: _submitting ? null : _submit,
                    icon: _submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.check),
                    label: Text(_submitting ? 'Saving...' : 'Create schedule'),
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

class _PickerTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final VoidCallback onTap;

  const _PickerTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppColors.textMuted),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    value,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textMuted),
          ],
        ),
      ),
    );
  }
}
