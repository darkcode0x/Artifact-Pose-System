import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../models/artifact.dart';
import '../../models/inspection.dart';
import '../../providers/artifact_provider.dart';
import '../../providers/auth_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';

class CaptureScreen extends StatefulWidget {
  final Artifact artifact;

  const CaptureScreen({super.key, required this.artifact});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  File? _captured;
  bool _uploading = false;
  final _descriptionController = TextEditingController();

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _pickImage(ImageSource source) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: source,
      maxWidth: 1920,
      imageQuality: 92,
    );
    if (picked != null && mounted) {
      setState(() => _captured = File(picked.path));
    }
  }

  Future<void> _upload() async {
    if (_captured == null) return;
    setState(() => _uploading = true);

    final auth = context.read<AuthProvider>();
    final inspection = await context.read<ArtifactProvider>().inspect(
          widget.artifact.id,
          image: _captured!,
          description: _descriptionController.text.trim(),
          createdBy: auth.username,
        );

    if (!mounted) return;
    setState(() => _uploading = false);

    if (inspection == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Inspection failed; try again')),
      );
      return;
    }
    Navigator.pop<Inspection>(context, inspection);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Inspect: ${widget.artifact.name}')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(child: _preview()),
              const SizedBox(height: 12),
              TextField(
                controller: _descriptionController,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: 'Notes (optional)',
                  prefixIcon: Icon(Icons.notes_outlined),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _uploading
                          ? null
                          : () => _pickImage(ImageSource.gallery),
                      icon: const Icon(Icons.photo_library_outlined),
                      label: const Text('Gallery'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _uploading
                          ? null
                          : () => _pickImage(ImageSource.camera),
                      icon: const Icon(Icons.camera_alt_outlined),
                      label: const Text('Camera'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 52,
                child: ElevatedButton.icon(
                  onPressed:
                      _captured == null || _uploading ? null : _upload,
                  icon: _uploading
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(Icons.cloud_upload_outlined),
                  label: const Text('Upload & analyse'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _preview() {
    if (_captured == null) {
      return Container(
        decoration: BoxDecoration(
          color: AppColors.surfaceMuted,
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.add_a_photo_outlined,
                  size: 64, color: AppColors.textFaint),
              SizedBox(height: 8),
              Text(
                'Pick or capture an image to inspect',
                style: TextStyle(color: AppColors.textMuted),
              ),
            ],
          ),
        ),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: Image.file(_captured!, fit: BoxFit.cover),
    );
  }
}
