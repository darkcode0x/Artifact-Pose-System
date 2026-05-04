class Schedule {
  final String id; // VARCHAR(6)
  final String artifactId; // VARCHAR(6)
  final String? artifactName;
  final DateTime scheduledDate;
  final String scheduledTime;
  final String operatorUsername;
  final String notes;
  final bool completed;
  final DateTime createdAt;

  Schedule({
    required this.id,
    required this.artifactId,
    this.artifactName,
    required this.scheduledDate,
    required this.scheduledTime,
    required this.operatorUsername,
    required this.notes,
    required this.completed,
    required this.createdAt,
  });

  factory Schedule.fromJson(Map<String, dynamic> json) {
    return Schedule(
      id: json['id']?.toString() ?? '',
      artifactId: json['artifact_id']?.toString() ?? '',
      artifactName: json['artifact_name'] as String?,
      scheduledDate:
          DateTime.tryParse(json['scheduled_date']?.toString() ?? '') ??
              DateTime.now(),
      scheduledTime: json['scheduled_time']?.toString() ?? '09:00',
      operatorUsername: json['operator_username']?.toString() ?? '',
      notes: json['notes']?.toString() ?? '',
      completed: json['completed'] as bool? ?? false,
      createdAt:
          DateTime.tryParse(json['created_at']?.toString() ?? '') ?? DateTime.now(),
    );
  }
}
