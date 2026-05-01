import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/artifact_status.dart';
import '../../providers/artifact_provider.dart';
import '../../widgets/responsive_scaffold.dart';

class AddArtifactScreen extends StatefulWidget {
  const AddArtifactScreen({super.key});

  @override
  State<AddArtifactScreen> createState() => _AddArtifactScreenState();
}

class _AddArtifactScreenState extends State<AddArtifactScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _locationController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _dateController = TextEditingController();
  final _timeController = TextEditingController();
  final _intervalController = TextEditingController(text: '0'); // Mặc định 0 (không nhắc lại)

  ArtifactStatus _status = ArtifactStatus.good;
  DateTime? _selectedDate;
  TimeOfDay _selectedTime = const TimeOfDay(hour: 9, minute: 0);
  bool _isSaving = false;

  @override
  void dispose() {
    _nameController.dispose();
    _locationController.dispose();
    _descriptionController.dispose();
    _dateController.dispose();
    _timeController.dispose();
    _intervalController.dispose();
    super.dispose();
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.now().add(const Duration(days: 1)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() {
        _selectedDate = picked;
        _dateController.text = DateFormat('yyyy-MM-dd').format(picked);
      });
    }
  }

  Future<void> _selectTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _selectedTime,
    );
    if (picked != null) {
      setState(() {
        _selectedTime = picked;
        _timeController.text = picked.format(context);
      });
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);
    
    String? timeStr;
    if (_selectedDate != null) {
      final hour = _selectedTime.hour.toString().padLeft(2, '0');
      final minute = _selectedTime.minute.toString().padLeft(2, '0');
      timeStr = "$hour:$minute";
    }

    final created = await context.read<ArtifactProvider>().create(
          name: _nameController.text.trim(),
          description: _descriptionController.text.trim(),
          location: _locationController.text.trim(),
          scheduledDate: _selectedDate,
          scheduledTime: timeStr,
          // Truyền thêm số ngày nhắc lại
          inspectionIntervalDays: int.tryParse(_intervalController.text) ?? 0,
        );
        
    if (!mounted) return;
    setState(() => _isSaving = false);
    if (created == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not create artifact')),
      );
      return;
    }
    Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add Artifact')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: ListView(
              children: [
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: 'Artifact name',
                    prefixIcon: Icon(Icons.label_outline),
                  ),
                  validator: (v) =>
                      (v == null || v.trim().isEmpty) ? 'Please enter a name' : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _descriptionController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    alignLabelWithHint: true,
                    prefixIcon: Icon(Icons.description_outlined),
                  ),
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _locationController,
                  decoration: const InputDecoration(
                    labelText: 'Location',
                    prefixIcon: Icon(Icons.place_outlined),
                  ),
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _intervalController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Recurring interval (Days)',
                    prefixIcon: Icon(Icons.repeat),
                    helperText: '0 = One-time only, >0 = Repeat every X days',
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<ArtifactStatus>(
                  value: _status,
                  items: const [
                    DropdownMenuItem(value: ArtifactStatus.good, child: Text('Good')),
                    DropdownMenuItem(value: ArtifactStatus.needCheck, child: Text('Need Check')),
                    DropdownMenuItem(value: ArtifactStatus.warning, child: Text('Warning')),
                  ],
                  onChanged: (v) {
                    if (v != null) setState(() => _status = v);
                  },
                  decoration: const InputDecoration(
                    labelText: 'Initial status',
                    prefixIcon: Icon(Icons.flag_outlined),
                  ),
                ),
                const Divider(height: 40),
                const Text(
                  'Initial Inspection Schedule',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _dateController,
                        readOnly: true,
                        onTap: _selectDate,
                        decoration: const InputDecoration(
                          labelText: 'Start Date',
                          prefixIcon: Icon(Icons.calendar_today),
                          hintText: 'Optional',
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _timeController,
                        readOnly: true,
                        onTap: _selectTime,
                        decoration: const InputDecoration(
                          labelText: 'Time',
                          prefixIcon: Icon(Icons.access_time),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 28),
                SizedBox(
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: _isSaving ? null : _save,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Icon(Icons.check),
                    label: const Text('Save artifact'),
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
