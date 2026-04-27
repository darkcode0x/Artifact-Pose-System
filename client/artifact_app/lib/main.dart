import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/artifact_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/schedule_provider.dart';
import 'screens/admin/admin_dashboard_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/dashboard/dashboard_screen.dart';
import 'services/api_client.dart';
import 'services/artifact_service.dart';
import 'services/auth_service.dart';
import 'services/schedule_service.dart';
import 'services/token_storage.dart';
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

    // ApiClient must call back into AuthProvider on a 401, but AuthProvider
    // is constructed via Provider — break the cycle with a forward ref.
    AuthProvider? authRef;
    final apiClient = ApiClient(
      tokens: tokens,
      onUnauthorized: () => authRef?.onSessionExpired(),
    );

    final authService = AuthService(api: apiClient, tokens: tokens);
    final artifactService = ArtifactService(apiClient);
    final scheduleService = ScheduleService(apiClient);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) {
            final p =
                AuthProvider(authService: authService, tokens: tokens);
            authRef = p;
            // Bootstrap (silent — UI will react via consumer).
            // ignore: discarded_futures
            p.bootstrap();
            return p;
          },
        ),
        ChangeNotifierProvider(create: (_) => ArtifactProvider(artifactService)),
        ChangeNotifierProvider(create: (_) => ScheduleProvider(scheduleService)),
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

/// Routes the user into the right screen based on auth state.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        switch (auth.status) {
          case AuthStatus.unknown:
            return const _SplashView();
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

class _SplashView extends StatelessWidget {
  const _SplashView();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
