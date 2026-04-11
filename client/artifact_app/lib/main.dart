import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

import 'screens/auth/login_screen.dart';
import 'screens/dashboard/dashboard_screen.dart';
import 'screens/admin/admin_dashboard_screen.dart';
import 'screens/admin/user_list_screen.dart';

late List<CameraDescription> cameras;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  cameras = await availableCameras();
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'PBL5 Login',

      initialRoute: '/login',

      routes: {
        '/login': (context) => LoginScreen(),
        '/admin': (context) => AdminDashboardScreen(),
        '/operator': (context) => DashboardScreen(),
        '/user_list': (context) => UserListScreen(),
      },
    );
  }
}