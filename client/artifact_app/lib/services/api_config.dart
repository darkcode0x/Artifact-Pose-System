class ApiConfig {
  // Pass --dart-define=API_BASE_URL=https://your-backend at build time.
  // Default 10.0.2.2 lets the Android emulator reach the host machine.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
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
