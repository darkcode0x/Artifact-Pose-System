import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'api_config.dart';
import 'token_storage.dart';

class ApiException implements Exception {
  final int? statusCode;
  final String message;

  ApiException(this.message, {this.statusCode});

  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() =>
      'ApiException(${statusCode ?? '-'}): $message';
}

/// Thin HTTP wrapper that:
///   - injects the bearer token
///   - decodes JSON
///   - turns non-2xx into typed exceptions
class ApiClient {
  final TokenStorage _tokens;
  final http.Client _http;
  final Duration timeout;

  /// Notified when a request comes back 401 — provider layer can react
  /// (clear session, route to login).
  final void Function()? onUnauthorized;

  ApiClient({
    required TokenStorage tokens,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 30),
    this.onUnauthorized,
  })  : _tokens = tokens,
        _http = httpClient ?? http.Client();

  Future<Map<String, String>> _headers({bool json = true}) async {
    final headers = <String, String>{};
    if (json) headers['Content-Type'] = 'application/json';
    final token = await _tokens.readToken();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    final res = await _http
        .get(ApiConfig.uri(path, query), headers: await _headers(json: false))
        .timeout(timeout);
    return _decode(res);
  }

  Future<dynamic> post(String path, {Object? body}) async {
    final res = await _http
        .post(
          ApiConfig.uri(path),
          headers: await _headers(),
          body: body == null ? null : jsonEncode(body),
        )
        .timeout(timeout);
    return _decode(res);
  }

  Future<dynamic> patch(String path, {Object? body}) async {
    final res = await _http
        .patch(
          ApiConfig.uri(path),
          headers: await _headers(),
          body: body == null ? null : jsonEncode(body),
        )
        .timeout(timeout);
    return _decode(res);
  }

  Future<void> delete(String path) async {
    final res = await _http
        .delete(ApiConfig.uri(path), headers: await _headers(json: false))
        .timeout(timeout);
    _decode(res, allowEmpty: true);
  }

  Future<dynamic> postMultipart(
    String path, {
    required File file,
    String fieldName = 'file',
    Map<String, String>? fields,
  }) async {
    final request = http.MultipartRequest('POST', ApiConfig.uri(path));
    request.headers.addAll(await _headers(json: false));
    if (fields != null) request.fields.addAll(fields);
    request.files.add(
      await http.MultipartFile.fromPath(
        fieldName,
        file.path,
        contentType: _guessImageType(file.path),
      ),
    );
    final streamed = await request.send().timeout(timeout);
    final response = await http.Response.fromStream(streamed);
    return _decode(response);
  }

  MediaType? _guessImageType(String path) {
    final lower = path.toLowerCase();
    if (lower.endsWith('.png')) return MediaType('image', 'png');
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
      return MediaType('image', 'jpeg');
    }
    return null;
  }

  dynamic _decode(http.Response res, {bool allowEmpty = false}) {
    final code = res.statusCode;
    if (code == 401) {
      onUnauthorized?.call();
      throw ApiException('Unauthorized', statusCode: code);
    }
    if (code < 200 || code >= 300) {
      String message = 'Request failed';
      try {
        final body = jsonDecode(res.body);
        if (body is Map && body['detail'] != null) {
          message = body['detail'].toString();
        }
      } catch (_) {
        if (res.body.isNotEmpty) message = res.body;
      }
      throw ApiException(message, statusCode: code);
    }
    if (res.body.isEmpty) {
      return allowEmpty ? null : <String, dynamic>{};
    }
    try {
      return jsonDecode(res.body);
    } catch (e) {
      throw ApiException('Invalid JSON response from server');
    }
  }

  // ── Workflow / Device APIs ───────────────────────────────────────────────

  Future<Map<String, dynamic>> deviceStatus(String deviceId) async {
    final res = await get('/devices/$deviceId/status');
    return Map<String, dynamic>.from(res as Map);
  }

  Future<Map<String, dynamic>> startInitialization({
    required String deviceId,
    required String artifactId,
    double baselineMm = 100.0,
    double stepsPerMm = 860.0,
  }) async {
    final res = await post(
      '/workflows/$deviceId/start-initialization',
      body: {
        'artifact_id': artifactId,
        'baseline_mm': baselineMm,
        'steps_per_mm': stepsPerMm,
      },
    );
    return Map<String, dynamic>.from(res as Map);
  }

  Future<Map<String, dynamic>> startAlignment({
    required String deviceId,
    required String artifactId,
  }) async {
    final res = await post(
      '/workflows/$deviceId/start-alignment',
      body: {'artifact_id': artifactId},
    );
    return Map<String, dynamic>.from(res as Map);
  }

  Future<Map<String, dynamic>> captureRequest({
    required String deviceId,
    required String artifactId,
    String jobType = 'alignment',
  }) async {
    final res = await post(
      '/workflows/$deviceId/capture-request',
      body: {'artifact_id': artifactId, 'job_type': jobType},
    );
    return Map<String, dynamic>.from(res as Map);
  }

  Future<Map<String, dynamic>> mqttHealth() async {
    final res = await get('/mqtt/health');
    return Map<String, dynamic>.from(res as Map);
  }

  void dispose() => _http.close();
}
