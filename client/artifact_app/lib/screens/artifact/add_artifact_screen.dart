import 'package:flutter/material.dart';
import '../../models/artifact.dart';

class AddArtifactScreen extends StatefulWidget {

  const AddArtifactScreen({super.key});

  @override
  State<AddArtifactScreen> createState() => _AddArtifactScreenState();
}

class _AddArtifactScreenState extends State<AddArtifactScreen> {

  final nameController = TextEditingController();
  final locationController = TextEditingController();
  final descriptionController = TextEditingController();

  String status = "good";

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: const Text("Add Artifact"),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: Padding(

        padding: const EdgeInsets.all(20),

        child: Column(

          crossAxisAlignment: CrossAxisAlignment.start,

          children: [

            // ===== NAME =====

            const Text(
              "Artifact Name",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 8),

            TextField(
              controller: nameController,
              decoration: InputDecoration(
                hintText: "Enter artifact name",
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),

            const SizedBox(height: 20),

            // ===== DESCRIPTION =====

            const Text(
              "Description",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 8),

            TextField(
              controller: descriptionController,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: "Artifact description",
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),

            const SizedBox(height: 20),

            // ===== LOCATION =====

            const Text(
              "Location",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 8),

            TextField(
              controller: locationController,
              decoration: InputDecoration(
                hintText: "Room / Display case",
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),

            const SizedBox(height: 20),

            // ===== STATUS =====

            const Text(
              "Status",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 8),

            DropdownButtonFormField(

              value: status,

              items: const [

                DropdownMenuItem(
                    value: "good",
                    child: Text("Good")),

                DropdownMenuItem(
                    value: "need_check",
                    child: Text("Need Check")),

                DropdownMenuItem(
                    value: "warning",
                    child: Text("Warning")),
              ],

              onChanged: (value) {

                setState(() {
                  status = value!;
                });

              },

              decoration: InputDecoration(
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),

            const Spacer(),

            // ===== ADD BUTTON =====

            SizedBox(

              width: double.infinity,
              height: 50,

              child: ElevatedButton(

                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E3A1F),
                ),

                onPressed: () {

                  if (nameController.text.isEmpty) {
                    return;
                  }

                  Artifact newArtifact = Artifact(

                    name: nameController.text,
                    status: status,
                    hasImage: false,
                    description: descriptionController.text,
                    location: locationController.text,

                  );

                  Navigator.pop(context, newArtifact);
                },

                child: const Text("Add Artifact"),
              ),
            )
          ],
        ),
      ),
    );
  }
}