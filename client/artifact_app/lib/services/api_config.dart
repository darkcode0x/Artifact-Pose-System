class ApiConfig {
  // Pass --dart-define=API_BASE_URL=http://192.168.0.102:8000 at build time.
  // Default: PC home WiFi IP (192.168.0.102:8000).
  // For emulator use 10.0.2.2:8000; for adb-reverse use 127.0.0.1:8000.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://192.168.0.102:8000',
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

  /// Resolve a server-relative path (e.g. "/uploads/foo.jpg") into a full URL.
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
