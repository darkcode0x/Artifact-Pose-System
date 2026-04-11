import 'package:flutter/material.dart';
import '../../models/artifact.dart';
import '../../services/museum_service.dart';
import 'artifact_detail_screen.dart';
import 'add_artifact_screen.dart';
import '../schedule/schedule_screen.dart';

class ArtifactListScreen extends StatefulWidget {
  const ArtifactListScreen({super.key});

  @override
  State<ArtifactListScreen> createState() => _ArtifactListScreenState();
}

class _ArtifactListScreenState extends State<ArtifactListScreen> {

  final service = MuseumService();

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(

        title: const Text("Artifacts"),

        backgroundColor: const Color(0xFF1E3A1F),

        actions: [

          IconButton(
            icon: const Icon(Icons.calendar_month),

            onPressed: () {

              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const ScheduleScreen(),
                ),
              );

            },
          )
        ],
      ),

      body: ListView.builder(

        padding: const EdgeInsets.all(15),

        itemCount: service.artifacts.length,

        itemBuilder: (context, index) {

          Artifact artifact = service.artifacts[index];

          return _artifactCard(artifact);
        },
      ),

      floatingActionButton: FloatingActionButton(

        backgroundColor: const Color(0xFF1E3A1F),

        child: const Icon(Icons.add),

        onPressed: () async {

          final newArtifact = await Navigator.push(

            context,

            MaterialPageRoute(
              builder: (_) => const AddArtifactScreen(),
            ),
          );

          if (newArtifact != null) {

            setState(() {
              service.addArtifact(newArtifact);
            });

          }
        },
      ),
    );
  }

  // ================= CARD =================

  Widget _artifactCard(Artifact artifact) {

    return GestureDetector(

      onTap: () {

        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) =>
                ArtifactDetailScreen(artifact: artifact),
          ),
        );

      },

      child: Container(

        margin: const EdgeInsets.only(bottom: 15),

        padding: const EdgeInsets.all(18),

        decoration: BoxDecoration(

          color: Colors.white,

          borderRadius: BorderRadius.circular(20),

        ),

        child: Row(

          children: [

            Icon(
              artifact.hasImage
                  ? Icons.image
                  : Icons.image_not_supported,
              size: 40,
              color: const Color(0xFF1E3A1F),
            ),

            const SizedBox(width: 15),

            Expanded(

              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,

                children: [

                  Text(
                    artifact.name,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),

                  Text(
                    artifact.location,
                    style: const TextStyle(
                      color: Colors.black54,
                    ),
                  ),

                  Text(
                    "Status: ${artifact.status}",
                    style: const TextStyle(
                      color: Colors.black54,
                    ),
                  ),
                ],
              ),
            ),

            const Icon(Icons.chevron_right)
          ],
        ),
      ),
    );
  }
}