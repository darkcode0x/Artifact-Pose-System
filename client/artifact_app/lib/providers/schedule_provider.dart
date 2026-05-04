import 'package:flutter/foundation.dart';

import '../models/schedule.dart';
import '../services/api_client.dart';
import '../services/schedule_service.dart';

class ScheduleProvider with ChangeNotifier {
  final ScheduleService _service;

  ScheduleProvider(this._service);

  List<Schedule> _schedules = [];
  bool _loading = false;
  String? _error;
  DateTime _selectedDate = DateTime.now();

  List<Schedule> get schedules => List.unmodifiable(_schedules);
  bool get loading => _loading;
  String? get error => _error;
  DateTime get selectedDate => _selectedDate;

  void selectDate(DateTime date) {
    _selectedDate = date;
    notifyListeners();
    refresh();
  }

  List<Schedule> forSelectedDate() {
    return _schedules
        .where((s) =>
            s.scheduledDate.year == _selectedDate.year &&
            s.scheduledDate.month == _selectedDate.month &&
            s.scheduledDate.day == _selectedDate.day)
        .toList(growable: false);
  }

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _schedules = await _service.list();
    } on ApiException catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load schedule';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<Schedule?> create({
    required String artifactId, // Changed to String
    required DateTime date,
    required String time,
    required String operatorUsername,
    String notes = '',
  }) async {
    try {
      final created = await _service.create(
        artifactId: artifactId,
        scheduledDate: date,
        scheduledTime: time,
        operatorUsername: operatorUsername,
        notes: notes,
      );
      _schedules = [..._schedules, created]
        ..sort((a, b) => a.scheduledDate.compareTo(b.scheduledDate));
      notifyListeners();
      return created;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  Future<void> markComplete(String id, bool completed) async { // Changed to String
    try {
      final updated = await _service.markComplete(id, completed);
      _schedules =
          _schedules.map((s) => s.id == updated.id ? updated : s).toList();
      notifyListeners();
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
    }
  }
}
