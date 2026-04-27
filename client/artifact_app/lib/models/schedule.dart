class Schedule {
  final int id;
  final int artifactId;
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
    required this.artifactName,
    required this.scheduledDate,
    required this.scheduledTime,
    required this.operatorUsername,
    required this.notes,
    required this.completed,
    required this.createdAt,
  });

  factory Schedule.fromJson(Map<String, dynamic> json) {
    return Schedule(
      id: json['id'] as int,
      artifactId: json['artifact_id'] as int,
      artifactName: json['artifact_name'] as String?,
      scheduledDate:
          DateTime.tryParse(json['scheduled_date'] as String? ?? '') ??
              DateTime.now(),
      scheduledTime: json['scheduled_time'] as String? ?? '09:00',
      operatorUsername: json['operator_username'] as String? ?? '',
      notes: json['notes'] as String? ?? '',
      completed: json['completed'] as bool? ?? false,
      createdAt:
          DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
