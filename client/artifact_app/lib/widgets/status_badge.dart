import 'package:flutter/material.dart';

import '../models/artifact_status.dart';
import '../theme.dart';

class StatusBadge extends StatelessWidget {
  final ArtifactStatus status;
  final bool compact;

  const StatusBadge({super.key, required this.status, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final color = _color(status);
    final label = status.label;
    final fontSize = compact ? 11.0 : 13.0;
    final padding = compact
        ? const EdgeInsets.symmetric(horizontal: 8, vertical: 3)
        : const EdgeInsets.symmetric(horizontal: 12, vertical: 5);

    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          SizedBox(width: compact ? 5 : 7),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w600,
              fontSize: fontSize,
            ),
          ),
        ],
      ),
    );
  }

  static Color _color(ArtifactStatus s) {
    switch (s) {
      case ArtifactStatus.good:
        return AppColors.statusGood;
      case ArtifactStatus.needCheck:
        return AppColors.statusNeedCheck;
      case ArtifactStatus.warning:
        return AppColors.statusWarning;
      case ArtifactStatus.damaged:
        return AppColors.statusDamaged;
      case ArtifactStatus.maintenance:
        return AppColors.statusMaintenance;
    }
  }
}
