import 'package:flutter/material.dart';

import '../artifact/artifact_list_screen.dart';
import '../schedule/schedule_screen.dart';
import '../alerts/alert_screen.dart';

class AdminDashboardScreen extends StatelessWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F6F3),

      body: SafeArea(
        child: Column(
          children: [

            // ================= HEADER =================

            Container(
              padding: const EdgeInsets.fromLTRB(20, 25, 20, 25),
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF1E3A1F), Color(0xFF2F5D32)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.vertical(
                  bottom: Radius.circular(30),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "Museum Monitoring",
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: 14,
                        ),
                      ),
                      SizedBox(height: 6),
                      Text(
                        "Admin Dashboard",
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  IconButton(
                    icon: const Icon(Icons.logout, color: Colors.white),
                    onPressed: () => _logout(context),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 25),

            // ================= STATUS =================

            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 25),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.05),
                      blurRadius: 12,
                    )
                  ],
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _StatusItem("12", "Users"),
                    _StatusItem("24", "Artifacts"),
                    _StatusItem("3", "Alerts"),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 35),

            // ================= MAIN FUNCTIONS =================

            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [

                    const Text(
                      "Admin Functions",
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),

                    const SizedBox(height: 20),

                    Row(
                      children: [

                        Expanded(
                          child: _actionCard(
                            icon: Icons.people,
                            title: "Users",
                            onTap: () {
                              Navigator.pushNamed(context, "/user_list");
                            },
                          ),
                        ),

                        const SizedBox(width: 20),

                        Expanded(
                          child: _actionCard(
                            icon: Icons.inventory,
                            title: "Artifacts",
                            onTap: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => const ArtifactListScreen(),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 20),

                    Row(
                      children: [

                        Expanded(
                          child: _actionCard(
                            icon: Icons.calendar_month,
                            title: "Schedules",
                            onTap: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => const ScheduleScreen(),
                                ),
                              );
                            },
                          ),
                        ),

                        const SizedBox(width: 20),

                        Expanded(
                          child: _actionCard(
                            icon: Icons.warning_amber,
                            title: "Alerts",
                            onTap: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => AlertScreen(),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 30),

                    // ================= ACTIVITY =================

                    const Text(
                      "Recent Admin Activity",
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),

                    const SizedBox(height: 10),

                    Expanded(
                      child: ListView(
                        children: const [
                          _ActivityItem(
                              "User 'john_doe' created",
                              "1 hour ago"
                          ),
                          _ActivityItem(
                              "Artifact #1023 updated",
                              "Today"
                          ),
                          _ActivityItem(
                              "Schedule #55 approved",
                              "Yesterday"
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ================= ACTION CARD =================

  static Widget _actionCard({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 30),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 12,
            )
          ],
        ),
        child: Column(
          children: [
            Icon(
              icon,
              size: 32,
              color: const Color(0xFF1E3A1F),
            ),
            const SizedBox(height: 10),
            Text(
              title,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }

  static void _logout(BuildContext context) {
    Navigator.pushNamedAndRemoveUntil(
      context,
      '/login',
          (route) => false,
    );
  }
}

// ================= STATUS ITEM =================

class _StatusItem extends StatelessWidget {
  final String value;
  final String label;

  const _StatusItem(this.value, this.label);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: Color(0xFF1E3A1F),
          ),
        ),
        const SizedBox(height: 6),
        Text(label),
      ],
    );
  }
}

// ================= ACTIVITY ITEM =================

class _ActivityItem extends StatelessWidget {
  final String title;
  final String time;

  const _ActivityItem(this.title, this.time);

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const CircleAvatar(
        backgroundColor: Color(0xFF1E3A1F),
        child: Icon(Icons.admin_panel_settings, color: Colors.white),
      ),
      title: Text(title),
      subtitle: Text(time),
    );
  }
}