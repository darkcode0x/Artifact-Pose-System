import 'package:flutter/material.dart';
import 'add_user_screen.dart';

class UserListScreen extends StatefulWidget {
  const UserListScreen({super.key});

  @override
  State<UserListScreen> createState() => _UserListScreenState();
}

class _UserListScreenState extends State<UserListScreen> {

  final List<Map<String, String>> users = [
    {"username": "admin", "role": "admin"},
    {"username": "staff1", "role": "user"},
    {"username": "staff2", "role": "user"},
  ];

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFFE9ECE7),

      appBar: AppBar(
        title: const Text("User Management"),
        backgroundColor: const Color(0xFF1E3A1F),
      ),

      body: ListView.builder(
        padding: const EdgeInsets.all(15),
        itemCount: users.length,
        itemBuilder: (context, index) {
          final user = users[index];
          return _userCard(user);
        },
      ),

      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFF1E3A1F),
        child: const Icon(Icons.add),
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const AddUserScreen(),
            ),
          );
        },
      ),
    );
  }

  // ================= USER CARD =================

  Widget _userCard(Map<String, String> user) {

    return GestureDetector(

      onTap: () {
        // future: open user detail
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

            const CircleAvatar(
              radius: 22,
              backgroundColor: Color(0xFF1E3A1F),
              child: Icon(Icons.person, color: Colors.white),
            ),

            const SizedBox(width: 15),

            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [

                  Text(
                    user["username"]!,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),

                  Text(
                    "Role: ${user["role"]}",
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