import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'api_config.dart';
import 'token_storage.dart';

class ApiException implements Exception {
  final int? statusCode;
  final String message;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => 'ApiException(${statusCode ?? '-'}): $message';
}

class ApiClient {
  final TokenStorage _tokens;
  final http.Client _http;
  final Duration timeout;
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

  Future<dynamic> post(String path, {Object? body, Map<String, dynamic>? query}) async {
    final res = await _http
        .post(
          ApiConfig.uri(path, query),
          headers: await _headers(),
          body: body == null ? null : jsonEncode(body),
        )
        .timeout(timeout);
    return _decode(res);
  }

  Future<dynamic> patch(String path, {Object? body, Map<String, dynamic>? query}) async {
    final res = await _http
        .patch(
          ApiConfig.uri(path, query),
          headers: await _headers(),
          body: body == null ? null : jsonEncode(body),
        )
        .timeout(timeout);
    return _decode(res);
  }

  Future<void> delete(String path, {Map<String, dynamic>? query}) async {
    final res = await _http
        .delete(ApiConfig.uri(path, query), headers: await _headers(json: false))
        .timeout(timeout);
    _decode(res, allowEmpty: true);
  }

  Future<dynamic> postMultipart(
    String path, {
    required XFile file,
    String fieldName = 'file',
    Map<String, String>? fields,
  }) async {
    final request = http.MultipartRequest('POST', ApiConfig.uri(path));
    request.headers.addAll(await _headers(json: false));
    if (fields != null) request.fields.addAll(fields);

    if (kIsWeb) {
      final bytes = await file.readAsBytes();
      request.files.add(http.MultipartFile.fromBytes(
        fieldName,
        bytes,
        filename: file.name,
      ));
    } else {
      request.files.add(await http.MultipartFile.fromPath(
        fieldName,
        file.path,
      ));
    }
    
    final streamed = await request.send().timeout(timeout);
    final response = await http.Response.fromStream(streamed);
    return _decode(response);
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
      } catch (_) {}
      throw ApiException(message, statusCode: code);
    }
    if (res.body.isEmpty) return allowEmpty ? null : <String, dynamic>{};
    try {
      return jsonDecode(res.body);
    } catch (e) {
      throw ApiException('Invalid JSON response from server');
    }
  }

  void dispose() => _http.close();
}
