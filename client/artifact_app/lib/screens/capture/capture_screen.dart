import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({Key? key}) : super(key: key);

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  CameraController? _controller;
  Future<void>? _initializeControllerFuture;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();

    final backCamera = cameras.firstWhere(
          (camera) => camera.lensDirection == CameraLensDirection.back,
    );

    _controller = CameraController(
      backCamera,
      ResolutionPreset.medium,
      enableAudio: false,
    );

    _initializeControllerFuture = _controller!.initialize();
    setState(() {});
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _captureImage() async {
    try {
      await _initializeControllerFuture;
      final image = await _controller!.takePicture();
      debugPrint("Saved at: ${image.path}");
    } catch (e) {
      debugPrint("Error: $e");
    }
  }

  void _controlDevice(String direction) {
    debugPrint("Move: $direction");
    // TODO: gửi lệnh lên backend điều khiển thiết bị
  }

  @override
  @override
  Widget build(BuildContext context) {
    if (_controller == null) {
      return const Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: CircularProgressIndicator(color: Colors.white),
        ),
      );
    }

    return Scaffold(
      body: FutureBuilder(
        future: _initializeControllerFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.done) {

            final size = MediaQuery.of(context).size;
            final deviceRatio = size.width / size.height;
            final previewRatio = _controller!.value.aspectRatio;

            return Stack(
              children: [

                // ================= FULLSCREEN CAMERA =================
                SizedBox.expand(
                  child: FittedBox(
                    fit: BoxFit.cover,
                    child: SizedBox(
                      width: size.width,
                      height: size.width / previewRatio,
                      child: CameraPreview(_controller!),
                    ),
                  ),
                ),

                // ================= SCAN FRAME =================
                Center(
                  child: Container(
                    width: 260,
                    height: 260,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: Colors.greenAccent,
                        width: 3,
                      ),
                    ),
                  ),
                ),

                // ================= TOP BAR =================
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 15),
                    child: Row(
                      mainAxisAlignment:
                      MainAxisAlignment.spaceBetween,
                      children: [
                        GestureDetector(
                          onTap: () => Navigator.pop(context),
                          child: const CircleAvatar(
                            backgroundColor: Colors.black54,
                            child: Icon(Icons.arrow_back,
                                color: Colors.white),
                          ),
                        ),
                        const Text(
                          "Live Monitor",
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(width: 40),
                      ],
                    ),
                  ),
                ),

                // ================= D-PAD (OVERLAY) =================
                Positioned(
                  bottom: 140,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.all(15),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.5),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Column(
                        children: [
                          _controlButton(Icons.keyboard_arrow_up, "UP"),
                          Row(
                            mainAxisAlignment:
                            MainAxisAlignment.center,
                            children: [
                              _controlButton(Icons.keyboard_arrow_left, "LEFT"),
                              const SizedBox(width: 40),
                              _controlButton(Icons.keyboard_arrow_right, "RIGHT"),
                            ],
                          ),
                          _controlButton(Icons.keyboard_arrow_down, "DOWN"),
                        ],
                      ),
                    ),
                  ),
                ),

                // ================= CAPTURE BUTTON =================
                Positioned(
                  bottom: 40,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: GestureDetector(
                      onTap: _captureImage,
                      child: Container(
                        width: 85,
                        height: 85,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: Colors.white,
                            width: 4,
                          ),
                        ),
                        child: const Center(
                          child: CircleAvatar(
                            radius: 30,
                            backgroundColor: Color(0xFF1E3A1F),
                            child: Icon(Icons.camera_alt,
                                color: Colors.white),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            );
          } else {
            return const Center(
              child: CircularProgressIndicator(color: Colors.white),
            );
          }
        },
      ),
    );
  }

  Widget _controlButton(IconData icon, String direction) {
    return GestureDetector(
      onTap: () => _controlDevice(direction),
      child: Container(
        width: 55,
        height: 55,
        margin: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: const Color(0xFF1E3A1F),
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.4),
              blurRadius: 5,
            )
          ],
        ),
        child: Icon(icon, color: Colors.white, size: 30),
      ),
    );
  }
}