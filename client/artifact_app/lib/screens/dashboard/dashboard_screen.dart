import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/artifact_provider.dart';
import '../../providers/auth_provider.dart';
import '../../theme.dart';
import '../../widgets/responsive_scaffold.dart';
import '../alerts/alert_screen.dart';
import '../artifact/artifact_list_screen.dart';
import '../devices/device_list_screen.dart';
import '../profile/profile_screen.dart';
import '../schedule/schedule_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ArtifactProvider>().refresh();
      context.read<AuthProvider>().fetchFullProfile();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ArtifactProvider>();
    final auth = context.watch<AuthProvider>();
    // Ưu tiên hiển thị Họ tên nếu có, nếu không thì hiện Username
    final displayName = auth.currentUser?.fullName ?? auth.username ?? 'User';

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () async {
            await context.read<ArtifactProvider>().refresh();
            await context.read<AuthProvider>().fetchFullProfile();
          },
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              _DashboardHeader(
                title: 'Welcome, $displayName',
                subtitle: 'Operator Dashboard',
                onLogout: () => auth.logout(),
              ),
              const SizedBox(height: 16),
              ResponsiveBody(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _StatusSummaryCard(provider: provider),
                    const SizedBox(height: 24),
                    Text(
                      'Main Functions',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 12),
                    LayoutBuilder(
                      builder: (context, c) {
                        final cols = c.maxWidth > 520 ? 4 : 2;
                        return GridView.count(
                          crossAxisCount: cols,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: 1.05,
                          children: [
                            _ActionCard(
                              icon: Icons.inventory_2_outlined,
                              title: 'Artifacts',
                              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ArtifactListScreen())),
                            ),
                            _ActionCard(
                              icon: Icons.router_outlined,
                              title: 'IoT Devices',
                              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const DeviceListScreen())),
                            ),
                            _ActionCard(
                              icon: Icons.calendar_month,
                              title: 'Schedule',
                              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ScheduleScreen())),
                            ),
                            _ActionCard(
                              icon: Icons.warning_amber_outlined,
                              title: 'Alerts',
                              badge: provider.alerts.length,
                              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AlertScreen())),
                            ),
                            _ActionCard(
                              icon: Icons.person_outline,
                              title: 'My Profile',
                              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfileScreen())),
                            ),
                          ],
                        );
                      },
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  final VoidCallback onLogout;

  const _DashboardHeader({required this.title, required this.subtitle, required this.onLogout});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.primary, AppColors.primaryLight],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(32)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(subtitle, style: const TextStyle(color: Colors.white70, fontSize: 13)),
                const SizedBox(height: 4),
                Text(title, style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
          IconButton(icon: const Icon(Icons.logout, color: Colors.white), onPressed: onLogout),
        ],
      ),
    );
  }
}

class _StatusSummaryCard extends StatelessWidget {
  final ArtifactProvider provider;
  const _StatusSummaryCard({required this.provider});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _StatItem(value: '${provider.artifacts.length}', label: 'Total'),
            const VerticalDivider(width: 1),
            _StatItem(value: '${provider.alerts.length}', label: 'Alerts', color: Colors.red),
            const VerticalDivider(width: 1),
            _StatItem(value: '${provider.artifacts.where((a) => !a.status.isAlert).length}', label: 'Safe', color: Colors.green),
          ],
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String value;
  final String label;
  final Color? color;
  const _StatItem({required this.value, required this.label, this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color ?? AppColors.primary)),
        Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
      ],
    );
  }
}

class _ActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final int? badge;

  const _ActionCard({required this.icon, required this.title, required this.onTap, this.badge});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Stack(
          children: [
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, size: 32, color: AppColors.primary),
                  const SizedBox(height: 10),
                  Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                ],
              ),
            ),
            if (badge != null && badge! > 0)
              Positioned(
                right: 12, top: 12,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(10)),
                  child: Text('$badge', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
