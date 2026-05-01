import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../models/artifact_status.dart';
import '../../providers/artifact_provider.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/responsive_scaffold.dart';

class EditArtifactScreen extends StatefulWidget {
  final Artifact artifact;

  const EditArtifactScreen({super.key, required this.artifact});

  @override
  State<EditArtifactScreen> createState() => _EditArtifactScreenState();
}

class _EditArtifactScreenState extends State<EditArtifactScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameController;
  late TextEditingController _locationController;
  late TextEditingController _descriptionController;
  late TextEditingController _intervalController;
  
  late ArtifactStatus _status;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.artifact.name);
    _locationController = TextEditingController(text: widget.artifact.location);
    _descriptionController = TextEditingController(text: widget.artifact.description);
    _intervalController = TextEditingController(text: widget.artifact.inspectionIntervalDays.toString());
    _status = widget.artifact.status;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _locationController.dispose();
    _descriptionController.dispose();
    _intervalController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);
    
    final auth = context.read<AuthProvider>();
    final provider = context.read<ArtifactProvider>();
    
    final success = await provider.updateDetails(
      widget.artifact.id,
      name: _nameController.text.trim(),
      description: _descriptionController.text.trim(),
      location: _locationController.text.trim(),
      status: auth.isAdmin ? _status : null,
      inspectionIntervalDays: int.tryParse(_intervalController.text) ?? 0,
    );

    if (!mounted) return;
    setState(() => _isSaving = false);
    
    if (success != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Artifact updated successfully')),
      );
      Navigator.pop(context, true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(provider.error ?? 'Failed to update artifact')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final isAdmin = auth.isAdmin;

    return Scaffold(
      appBar: AppBar(title: const Text('Edit Artifact')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: ListView(
              children: [
                TextFormField(
                  controller: _nameController,
                  enabled: isAdmin,
                  decoration: InputDecoration(
                    labelText: 'Artifact name',
                    prefixIcon: const Icon(Icons.label_outline),
                    helperText: isAdmin ? null : 'Only admins can change the name',
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
                if (isAdmin) ...[
                  const SizedBox(height: 14),
                  DropdownButtonFormField<ArtifactStatus>(
                    value: _status,
                    items: ArtifactStatus.values.where((s) => s != ArtifactStatus.archived).map((s) {
                      return DropdownMenuItem(
                        value: s,
                        child: Text(s.label),
                      );
                    }).toList(),
                    onChanged: (v) {
                      if (v != null) setState(() => _status = v);
                    },
                    decoration: const InputDecoration(
                      labelText: 'Status (Admin Override)',
                      prefixIcon: Icon(Icons.flag_outlined),
                    ),
                  ),
                ],
                const SizedBox(height: 28),
                SizedBox(
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: _isBusy ? null : _save,
                    icon: _isBusy
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Icon(Icons.save),
                    label: const Text('Save changes'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  bool get _isBusy => _isSaving;
}
