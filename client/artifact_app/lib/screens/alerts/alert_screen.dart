import 'package:flutter/material.dart';
import '../../models/artifact.dart';
import '../../services/museum_service.dart';

class AlertScreen extends StatefulWidget {
  const AlertScreen({super.key});

  @override
  State<AlertScreen> createState() => _AlertScreenState();
}

class _AlertScreenState extends State<AlertScreen> {

  final MuseumService service = MuseumService();

  void inspectArtifact(Artifact artifact) {

    setState(() {

      // sau khi kiểm tra chuyển về maintenance
      artifact.status = "maintenance";

    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text("${artifact.name} marked for inspection"),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {

    List<Artifact> alerts = service.getAlerts();

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: const Text("Alerts"),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: alerts.isEmpty
          ? const Center(child: Text("No alerts"))
          : ListView.builder(

        padding: const EdgeInsets.all(15),
        itemCount: alerts.length,

        itemBuilder: (context, index) {

          Artifact artifact = alerts[index];

          return Container(

            margin: const EdgeInsets.only(bottom: 15),
            padding: const EdgeInsets.all(15),

            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),

            child: Row(
              children: [

                const Icon(
                  Icons.warning_amber,
                  color: Colors.orange,
                  size: 30,
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

                      Text("Location: ${artifact.location}"),

                      Text(
                        "Status: ${artifact.status}",
                        style: const TextStyle(
                          color: Colors.red,
                        ),
                      ),

                      const SizedBox(height: 8),

                      Row(
                        children: [

                          ElevatedButton.icon(

                            onPressed: () => inspectArtifact(artifact),

                            icon: const Icon(Icons.search),

                            label: const Text("Inspect"),

                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF1E3A1F),
                            ),
                          ),

                          const SizedBox(width: 10),

                          ElevatedButton.icon(

                            onPressed: () {

                              setState(() {
                                artifact.status = "good";
                              });

                            },

                            icon: const Icon(Icons.check),

                            label: const Text("Resolve"),

                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green,
                            ),
                          ),
                        ],
                      )
                    ],
                  ),
                )
              ],
            ),
          );
        },
      ),
    );
  }
}