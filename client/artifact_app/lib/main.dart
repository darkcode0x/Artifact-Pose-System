import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/artifact_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/schedule_provider.dart';
import 'providers/user_provider.dart';
import 'screens/admin/admin_dashboard_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/dashboard/dashboard_screen.dart';
import 'services/api_client.dart';
import 'services/artifact_service.dart';
import 'services/auth_service.dart';
import 'services/device_service.dart';
import 'services/schedule_service.dart';
import 'services/token_storage.dart';
import 'services/workflow_service.dart';
import 'services/user_service.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ArtifactApp());
}

class ArtifactApp extends StatelessWidget {
  const ArtifactApp({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = TokenStorage();

    AuthProvider? authRef;
    final apiClient = ApiClient(
      tokens: tokens,
      onUnauthorized: () => authRef?.onSessionExpired(),
    );

    final authService = AuthService(api: apiClient, tokens: tokens);
    final artifactService = ArtifactService(apiClient);
    final scheduleService = ScheduleService(apiClient);
    final workflowService = WorkflowService(apiClient);
    final deviceService = DeviceService(apiClient);
    final userService = UserService(apiClient);

    return MultiProvider(
      providers: [
        Provider<TokenStorage>.value(value: tokens),
        Provider<ApiClient>.value(value: apiClient),
        Provider<DeviceService>.value(value: deviceService),
        Provider<UserService>.value(value: userService),
        ChangeNotifierProvider(
          create: (_) {
            final p = AuthProvider(
              authService: authService,
              tokens: tokens,
              api: apiClient,
            );
            authRef = p;
            p.bootstrap();
            return p;
          },
        ),
        ChangeNotifierProvider(
          create: (_) => ArtifactProvider(artifactService, workflowService),
        ),
        ChangeNotifierProvider(
          create: (_) => UserProvider(userService),
        ),
        ChangeNotifierProvider(
          create: (_) => ScheduleProvider(scheduleService),
        ),
      ],
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Artifact Monitor',
        theme: buildAppTheme(),
        home: const AuthGate(),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        switch (auth.status) {
          case AuthStatus.unknown:
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
          case AuthStatus.unauthenticated:
            return const LoginScreen();
          case AuthStatus.authenticated:
            return auth.isAdmin
                ? const AdminDashboardScreen()
                : const DashboardScreen();
        }
      },
    );
  }
}
