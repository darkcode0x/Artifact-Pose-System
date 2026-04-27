import 'package:flutter/material.dart';

class AppColors {
  static const Color primary = Color(0xFF1E3A1F);
  static const Color primaryLight = Color(0xFF2F5D32);
  static const Color background = Color(0xFFF4F6F3);
  static const Color surface = Colors.white;
  static const Color surfaceMuted = Color(0xFFE9ECE7);

  static const Color statusGood = Color(0xFF2E8B57);
  static const Color statusNeedCheck = Color(0xFFE08E0B);
  static const Color statusWarning = Color(0xFFE25C31);
  static const Color statusDamaged = Color(0xFFC0392B);
  static const Color statusMaintenance = Color(0xFF607D8B);

  static const Color textMuted = Colors.black54;
  static const Color textFaint = Colors.black45;
}

class AppBreakpoints {
  static const double phone = 600;
  static const double tablet = 900;
  static const double maxContentWidth = 720;
}

ThemeData buildAppTheme() {
  final base = ThemeData.light(useMaterial3: true);
  return base.copyWith(
    colorScheme: base.colorScheme.copyWith(
      primary: AppColors.primary,
      secondary: AppColors.primaryLight,
      surface: AppColors.surface,
    ),
    scaffoldBackgroundColor: AppColors.background,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.primary,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.4),
      ),
    ),
  );
}
