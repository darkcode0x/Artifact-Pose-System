import 'package:flutter/material.dart';
import '../../models/image_comparison.dart';

class ResultScreen extends StatelessWidget {

  final ImageComparison result;

  const ResultScreen({
    super.key,
    required this.result,
  });

  Color getStatusColor(String status) {

    switch (status.toLowerCase()) {

      case "good":
        return Colors.green;

      case "warning":
        return Colors.orange;

      case "damaged":
        return Colors.red;

      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: const Text("Inspection Result"),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: SingleChildScrollView(

        padding: const EdgeInsets.all(20),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            const Text(
              "Image Comparison",
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 20),

            // previous image
            const Text("Previous Image"),

            const SizedBox(height: 8),

            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                result.previousImage,
                height: 200,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),

            const SizedBox(height: 20),

            // current image
            const Text("Current Image"),

            const SizedBox(height: 8),

            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                result.currentImage,
                height: 200,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),

            const SizedBox(height: 20),

            // heatmap
            const Text("AI Heatmap"),

            const SizedBox(height: 8),

            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                result.heatmapPath,
                height: 200,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),

            const SizedBox(height: 25),

            // damage score
            Row(
              children: [

                const Text(
                  "Damage Score: ",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                  ),
                ),

                Text("${result.damageScore.toStringAsFixed(2)} %"),
              ],
            ),

            const SizedBox(height: 10),

            // status
            Row(
              children: [

                const Text(
                  "Status: ",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                  ),
                ),

                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: getStatusColor(result.status),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    result.status,
                    style: const TextStyle(
                      color: Colors.white,
                    ),
                  ),
                )
              ],
            ),

            const SizedBox(height: 20),

            const Text(
              "Description",
              style: TextStyle(
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 5),

            Text(result.description),

            const SizedBox(height: 20),

            Text(
              "Checked at: ${result.createdAt}",
              style: const TextStyle(
                color: Colors.grey,
              ),
            ),

            const SizedBox(height: 30),

            Center(
              child: ElevatedButton(

                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E3A1F),
                ),

                onPressed: () {

                  Navigator.pop(context);

                },

                child: const Text("Back"),
              ),
            )
          ],
        ),
      ),
    );
  }
}