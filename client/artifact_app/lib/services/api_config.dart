class ApiConfig {
  // Android emulator reaches host machine via 10.0.2.2
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static Uri uri(String path) {
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$normalizedBase$normalizedPath');
  }
}
