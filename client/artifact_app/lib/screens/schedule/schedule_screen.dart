import 'package:flutter/material.dart';
import '../../services/museum_service.dart';
import '../../models/schedule.dart';
import 'schedule_detail_screen.dart';


class ScheduleScreen extends StatefulWidget {
  const ScheduleScreen({super.key});

  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {

  final service = MuseumService();

  DateTime selectedDate = DateTime.now();

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: const Text("Inspection Schedule"),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: Column(

        children: [

          const SizedBox(height: 10),

          _dateSelector(),

          const SizedBox(height: 10),

          Expanded(
            child: _scheduleList(),
          )
        ],
      ),
    );
  }

  // ================= DATE SELECTOR =================

  Widget _dateSelector() {

    List<DateTime> days = List.generate(
        7,
            (index) => DateTime.now().add(Duration(days: index))
    );

    return SizedBox(

      height: 90,

      child: ListView.builder(

        scrollDirection: Axis.horizontal,

        itemCount: days.length,

        itemBuilder: (context, index) {

          DateTime day = days[index];

          bool selected =
              day.day == selectedDate.day &&
                  day.month == selectedDate.month;

          return GestureDetector(

            onTap: () {

              setState(() {
                selectedDate = day;
              });

            },

            child: Container(

              width: 70,

              margin: const EdgeInsets.symmetric(horizontal: 6),

              decoration: BoxDecoration(

                color: selected
                    ? const Color(0xFF1E3A1F)
                    : Colors.white,

                borderRadius: BorderRadius.circular(15),

              ),

              child: Column(

                mainAxisAlignment: MainAxisAlignment.center,

                children: [

                  Text(
                    "${day.day}",
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: selected
                          ? Colors.white
                          : Colors.black,
                    ),
                  ),

                  Text(
                    ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                    [day.weekday - 1],

                    style: TextStyle(
                      color: selected
                          ? Colors.white
                          : Colors.black54,
                    ),
                  )
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ================= LIST =================

  Widget _scheduleList() {

    List<Schedule> schedules =
    service.getScheduleByDate(selectedDate);

    if (schedules.isEmpty) {

      return const Center(
        child: Text("No inspection scheduled"),
      );
    }

    return ListView.builder(

      padding: const EdgeInsets.all(15),

      itemCount: schedules.length,

      itemBuilder: (context, index) {

        return _scheduleItem(schedules[index]);

      },
    );
  }

  // ================= ITEM =================

  Widget _scheduleItem(Schedule schedule) {

    return GestureDetector(

      onTap: () {

        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) =>
                ScheduleDetailScreen(schedule: schedule),
          ),
        );
      },

      child: Container(

        margin: const EdgeInsets.only(bottom: 15),

        padding: const EdgeInsets.all(15),

        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
        ),

        child: Row(

          children: [

            const Icon(
              Icons.event_note,
              size: 30,
              color: Color(0xFF1E3A1F),
            ),

            const SizedBox(width: 15),

            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [

                  Text(
                    schedule.artifactName,
                    style: const TextStyle(
                        fontWeight: FontWeight.bold),
                  ),

                  Text("Time: ${schedule.time}"),

                  Text("Operator: ${schedule.operator}"),
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