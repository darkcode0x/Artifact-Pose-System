import '../models/artifact.dart';
import '../models/schedule.dart';

class MuseumService {

  // ================= ARTIFACT LIST =================

  final List<Artifact> artifacts = [

    Artifact(
      name: "Ancient Vase",
      status: "good",
      hasImage: true,
      description: "Ceramic vase from 15th century",
      location: "Room A1",
    ),

    Artifact(
      name: "Bronze Statue",
      status: "warning",
      hasImage: false,
      description: "Ancient bronze warrior statue",
      location: "Room B2",
    ),

    Artifact(
      name: "Golden Mask",
      status: "warning",
      hasImage: true,
      description: "Ancient golden burial mask",
      location: "Room C3",
    ),

    Artifact(
      name: "Stone Tablet",
      status: "need inspection",
      hasImage: false,
      description: "Stone tablet with ancient script",
      location: "Room D1",
    ),

    Artifact(
      name: "Ancient Painting",
      status: "good",
      hasImage: true,
      description: "Historical painting from 17th century",
      location: "Room A2",
    ),
  ];

  // ================= SCHEDULE LIST =================

  final List<Schedule> schedules = [

    Schedule(
      artifactName: "Ancient Vase",
      date: DateTime.now(),
      time: "09:00",
      operator: "Admin",
    ),

    Schedule(
      artifactName: "Bronze Statue",
      date: DateTime.now(),
      time: "14:00",
      operator: "Admin",
    ),

    Schedule(
      artifactName: "Golden Mask",
      date: DateTime.now().add(const Duration(days: 1)),
      time: "10:00",
      operator: "Admin",
    ),
  ];

  // ================= ADD ARTIFACT =================

  void addArtifact(Artifact artifact) {
    artifacts.add(artifact);
  }

  // ================= ALERT LIST =================

  List<Artifact> getAlerts() {

    return artifacts.where((artifact) {

      return artifact.status.toLowerCase() == "warning" ||
          artifact.status.toLowerCase() == "need inspection";

    }).toList();
  }

  // ================= FILTER SCHEDULE =================

  List<Schedule> getScheduleByDate(DateTime date) {

    return schedules.where((schedule) {

      return schedule.date.day == date.day &&
          schedule.date.month == date.month &&
          schedule.date.year == date.year;

    }).toList();

  }
}