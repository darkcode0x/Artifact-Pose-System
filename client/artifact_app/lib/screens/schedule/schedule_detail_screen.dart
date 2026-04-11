import 'package:flutter/material.dart';
import '../../models/schedule.dart';

class ScheduleDetailScreen extends StatelessWidget {

  final Schedule schedule;

  const ScheduleDetailScreen({
    super.key,
    required this.schedule,
  });

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: const Text("Schedule Detail"),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: Padding(
        padding: const EdgeInsets.all(20),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,

          children: [

            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),

              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
              ),

              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,

                children: [

                  const Text(
                    "Artifact",
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.grey,
                    ),
                  ),

                  const SizedBox(height: 5),

                  Text(
                    schedule.artifactName,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),

                  const SizedBox(height: 20),

                  const Text(
                    "Inspection Time",
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.grey,
                    ),
                  ),

                  const SizedBox(height: 5),

                  Text(
                    schedule.time,
                    style: const TextStyle(fontSize: 16),
                  ),

                  const SizedBox(height: 20),

                  const Text(
                    "Operator",
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.grey,
                    ),
                  ),

                  const SizedBox(height: 5),

                  Text(
                    schedule.operator,
                    style: const TextStyle(fontSize: 16),
                  ),

                  const SizedBox(height: 20),

                  const Text(
                    "Status",
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.grey,
                    ),
                  ),

                  const SizedBox(height: 5),

                  const Text(
                    "Scheduled",
                    style: TextStyle(fontSize: 16),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 30),

            SizedBox(
              width: double.infinity,

              child: ElevatedButton(

                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E3A1F),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                ),

                onPressed: () {
                  Navigator.pop(context);
                },

                child: const Text(
                  "Back",
                  style: TextStyle(fontSize: 16),
                ),
              ),
            )
          ],
        ),
      ),
    );
  }
}