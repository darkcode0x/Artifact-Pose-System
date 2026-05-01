import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
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
  bool _isBusy = false;
  String? _statusMessage;
  XFile? _localFile; // Dùng cho simulator
  final _descriptionController = TextEditingController();

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  /// LUỒNG THẬT: Điều khiển thiết bị từ xa (Raspberry Pi)
  Future<void> _handleRemoteCapture() async {
    setState(() {
      _isBusy = true;
      _statusMessage = 'Đang gửi lệnh chụp tới thiết bị...';
    });

    final provider = context.read<ArtifactProvider>();
    final ok = await provider.triggerRemoteCapture(
      deviceId: 'pi_camera_01', 
      artifactId: widget.artifact.id,
      isReference: false,
    );

    if (!ok) {
      if (mounted) {
        setState(() {
          _isBusy = false;
          _statusMessage = 'Không thể kết nối tới thiết bị. Kiểm tra MQTT/Server.';
        });
      }
      return;
    }

    if (mounted) setState(() => _statusMessage = 'Thiết bị đang chụp... Đang chờ phân tích kết quả...');

    // Đợi server xử lý (Phân tích Pose + Damage)
    await Future.delayed(const Duration(seconds: 5));
    
    final history = await provider.historyFor(widget.artifact.id);
    
    if (mounted) {
      setState(() => _isBusy = false);
      if (history.isNotEmpty) {
        // Trả về kết quả mới nhất vừa lưu vào Postgres
        Navigator.pop<Inspection>(context, history.first);
      } else {
        setState(() => _statusMessage = 'Hết thời gian chờ hoặc phân tích thất bại.');
      }
    }
  }

  /// LUỒNG SIMULATOR: Chọn ảnh từ máy (Fix lỗi Image.file trên Web)
  Future<void> _handleSimulatorUpload() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.gallery);
    if (picked == null) return;

    setState(() {
      _localFile = picked;
      _isBusy = true;
      _statusMessage = 'Đang tải ảnh lên server để phân tích...';
    });

    final provider = context.read<ArtifactProvider>();
    final auth = context.read<AuthProvider>();

    final inspection = await provider.inspect(
      widget.artifact.id,
      image: picked,
      description: _descriptionController.text.trim(),
      createdBy: auth.username,
    );

    if (mounted) {
      setState(() => _isBusy = false);
      if (inspection != null) {
        Navigator.pop<Inspection>(context, inspection);
      } else {
        setState(() => _statusMessage = provider.error ?? 'Phân tích thất bại');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Kiểm tra: ${widget.artifact.name}')),
      body: SafeArea(
        child: ResponsiveBody(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Expanded(child: _buildPreview()),
              const SizedBox(height: 20),
              TextField(
                controller: _descriptionController,
                decoration: const InputDecoration(
                  labelText: 'Ghi chú kiểm tra',
                  prefixIcon: Icon(Icons.notes),
                ),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: ElevatedButton.icon(
                  onPressed: _isBusy ? null : _handleRemoteCapture,
                  icon: const Icon(Icons.settings_remote),
                  label: const Text('Ra lệnh thiết bị chụp (Real)'),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: OutlinedButton.icon(
                  onPressed: _isBusy ? null : _handleSimulatorUpload,
                  icon: const Icon(Icons.bug_report_outlined),
                  label: const Text('Simulator: Chọn ảnh từ máy'),
                  style: OutlinedButton.styleFrom(foregroundColor: Colors.orange),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPreview() {
    if (_localFile != null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: kIsWeb 
          ? Image.network(_localFile!.path, fit: BoxFit.cover)
          : Image.file(File(_localFile!.path), fit: BoxFit.cover),
      );
    }
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_isBusy ? Icons.sync : Icons.camera_enhance_outlined, size: 64, color: AppColors.textFaint),
            const SizedBox(height: 12),
            Text(_statusMessage ?? 'Sẵn sàng điều khiển thiết bị', style: const TextStyle(color: AppColors.textMuted)),
          ],
        ),
      ),
    );
  }
}
