import 'package:flutter/material.dart';
import '../../models/artifact.dart';
import '../../models/image_comparison.dart';
import '../capture/capture_screen.dart';
import '../inspect/result_screen.dart';

class ArtifactDetailScreen extends StatelessWidget {

  final Artifact artifact;

  const ArtifactDetailScreen({super.key, required this.artifact});

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: Text(artifact.name),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: Padding(

        padding: const EdgeInsets.all(20),

        child: Column(

          crossAxisAlignment: CrossAxisAlignment.start,

          children: [

            // IMAGE
            Container(
              height: 220,
              width: double.infinity,

              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(20),
              ),

              child: artifact.hasImage
                  ? const Icon(Icons.image, size: 80)
                  : const Icon(Icons.image_not_supported, size: 80),
            ),

            const SizedBox(height: 25),

            // NAME
            Text(
              artifact.name,
              style: const TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.bold,
                color: Color(0xFF1E3A1F),
              ),
            ),

            const SizedBox(height: 10),

            _buildStatus(),

            const SizedBox(height: 20),

            // INFO CARD
            Container(

              padding: const EdgeInsets.all(15),

              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(15),
              ),

              child: Column(

                children: [

                  _infoRow(
                    Icons.description,
                    "Description",
                    artifact.description,
                  ),

                  const SizedBox(height: 15),

                  _infoRow(
                    Icons.place,
                    "Location",
                    artifact.location,
                  ),
                ],
              ),
            ),

            const Spacer(),

            // BUTTON
            artifact.hasImage
                ? _inspectButton(context)
                : _captureButton(context),
          ],
        ),
      ),
    );
  }

  // ================= STATUS =================

  Widget _buildStatus() {

    Color color;
    String text;

    switch (artifact.status) {

      case "need_check":
        color = Colors.orange;
        text = "Need Check";
        break;

      case "warning":
        color = Colors.red;
        text = "Warning";
        break;

      default:
        color = Colors.green;
        text = "Good";
    }

    return Row(

      children: [

        Container(
          width: 10,
          height: 10,

          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),

        const SizedBox(width: 8),

        Text(
          text,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  // ================= CAPTURE BUTTON =================

  Widget _captureButton(BuildContext context) {

    return SizedBox(

      width: double.infinity,

      child: ElevatedButton.icon(

        icon: const Icon(Icons.camera_alt),

        label: const Text("Capture Initial Image"),

        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF1E3A1F),
          padding: const EdgeInsets.symmetric(vertical: 15),
        ),

        onPressed: () {

          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const CaptureScreen(),
            ),
          );
        },
      ),
    );
  }

  // ================= INSPECT BUTTON =================

  Widget _inspectButton(BuildContext context) {

    return SizedBox(

      width: double.infinity,

      child: ElevatedButton.icon(

        icon: const Icon(Icons.search),

        label: const Text("Inspect Artifact"),

        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.blue,
          padding: const EdgeInsets.symmetric(vertical: 15),
        ),

        onPressed: () {

          // DEMO RESULT DATA
          ImageComparison result = ImageComparison(
            comparisonId: 1,
            artifactId: 1,
            previousImage: "https://picsum.photos/400/200",
            currentImage: "https://picsum.photos/401/200",
            heatmapPath: "https://picsum.photos/402/200",
            damageScore: 12.5,
            status: "warning",
            description: "Minor surface change detected",
            createdAt: DateTime.now(),
          );

          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ResultScreen(result: result),
            ),
          );
        },
      ),
    );
  }

  // ================= INFO ROW =================

  Widget _infoRow(IconData icon, String title, String value) {

    return Row(

      crossAxisAlignment: CrossAxisAlignment.start,

      children: [

        Icon(icon),

        const SizedBox(width: 10),

        Expanded(

          child: Column(

            crossAxisAlignment: CrossAxisAlignment.start,

            children: [

              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                ),
              ),

              Text(
                value,
                style: const TextStyle(
                  color: Colors.black54,
                ),
              ),
            ],
          ),
        )
      ],
    );
  }
}