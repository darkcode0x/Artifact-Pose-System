import 'package:flutter/foundation.dart' show kIsWeb;

class ApiConfig {
  // IP của máy tính chạy Server trong mạng nội bộ (Dành cho điện thoại thật)
  // Theo log gần nhất của bạn là 192.168.1.151 (hoặc 192.168.1.149 tùy thời điểm)
  static const String _pcIp = '192.168.1.151';

  static const String _defaultUrl = kIsWeb
      ? 'http://127.0.0.1:8000'
      : 'http://$_pcIp:8000';

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: _defaultUrl,
  );

  static Uri uri(String path, [Map<String, dynamic>? query]) {
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    final stringQuery = query?.map(
      (k, v) => MapEntry(k, v?.toString() ?? ''),
    );
    return Uri.parse('$normalizedBase$normalizedPath').replace(
      queryParameters: stringQuery == null || stringQuery.isEmpty
          ? null
          : stringQuery,
    );
  }

  static String resolveAssetUrl(String? path) {
    if (path == null || path.isEmpty) return '';
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return '$normalizedBase$normalizedPath';
  }
}
