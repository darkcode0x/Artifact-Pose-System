import 'package:flutter/material.dart';
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

  ArtifactStatus _status = ArtifactStatus.good;
  bool _isSaving = false;

  @override
  void dispose() {
    _nameController.dispose();
    _locationController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);
    final created = await context.read<ArtifactProvider>().create(
          name: _nameController.text.trim(),
          description: _descriptionController.text.trim(),
          location: _locationController.text.trim(),
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
                DropdownButtonFormField<ArtifactStatus>(
                  value: _status,
                  items: const [
                    DropdownMenuItem(
                      value: ArtifactStatus.good,
                      child: Text('Good'),
                    ),
                    DropdownMenuItem(
                      value: ArtifactStatus.needCheck,
                      child: Text('Need Check'),
                    ),
                    DropdownMenuItem(
                      value: ArtifactStatus.warning,
                      child: Text('Warning'),
                    ),
                  ],
                  onChanged: (v) {
                    if (v != null) setState(() => _status = v);
                  },
                  decoration: const InputDecoration(
                    labelText: 'Initial status',
                    prefixIcon: Icon(Icons.flag_outlined),
                  ),
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
