import 'dart:io' if (dart.library.html) 'dart:html' as io;
import 'package:poultry_monitoring/utils/html_stub.dart' if (dart.library.html) 'dart:html' as html;
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../models/disease_model.dart';
import '../models/dashboard_model.dart';
import '../config/app_config.dart';


class ApiService {
  // Flask server configuration
  // The baseUrl is now configured in lib/config/app_config.dart
  // To switch platforms, simply change the serverUrl in AppConfig
  static const String baseUrl = AppConfig.serverUrl;
  final Dio _dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(seconds: 30),
    headers: {
      'Accept': 'application/json',
    },
  ));

  // Dashboard - Analyze Image
  Future<DashboardResponse> analyzeImage(dynamic imageFile) async {
    try {
      FormData formData;
      
      if (kIsWeb) {
        // Web platform - XFile from image_picker
        final xFile = imageFile as XFile;
        final bytes = await xFile.readAsBytes();
        final fileName = xFile.name;
        formData = FormData.fromMap({
          'image': MultipartFile.fromBytes(
            bytes,
            filename: fileName,
          ),
        });
      } else {
        // Mobile platform - XFile works on both, use path directly
        final xFile = imageFile as XFile;
        String fileName = xFile.path.split('/').last;
        formData = FormData.fromMap({
          'image': await MultipartFile.fromFile(
            xFile.path,
            filename: fileName,
          ),
        });
      }

      Response response = await _dio.post(
        '/analyze-image',
        data: formData,
      );

      return DashboardResponse.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to analyze image: $e');
    }
  }

  // Dashboard - Analyze Video
  Future<DashboardResponse> analyzeVideo(dynamic videoFile) async {
    try {
      FormData formData;
      
      if (kIsWeb) {
        // Web platform - videoFile can be html.File or Map with bytes
        List<int> bytes;
        String fileName;
        
        if (videoFile is Map) {
          // Handle map from file_picker
          bytes = videoFile['bytes'] as List<int>;
          fileName = videoFile['name'] as String;
        } else {
          // Handle html.File object (only on web, so html is dart:html)
          // On web, html.File has a name property
          final file = videoFile as html.File;
          final reader = html.FileReader();
          reader.readAsArrayBuffer(file);
          await reader.onLoad.first;
          bytes = reader.result as List<int>;
          // On web, html.File has 'name' property
          // On mobile stub, File also has 'name' property
          fileName = file.name;
        }
        
        formData = FormData.fromMap({
          'video': MultipartFile.fromBytes(
            bytes,
            filename: fileName,
          ),
        });
      } else {
        // Mobile platform - videoFile is a String path from file_picker
        final filePath = videoFile as String;
        // MultipartFile.fromFile accepts a string path directly, no need to create File object
        String fileName = filePath.split('/').last;
        formData = FormData.fromMap({
          'video': await MultipartFile.fromFile(
            filePath,
            filename: fileName,
          ),
        });
      }

      Response response = await _dio.post(
        '/analyze-video',
        data: formData,
      );

      return DashboardResponse.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to analyze video: $e');
    }
  }

  // Generate Heatmap
  Future<HeatmapResponse> generateHeatmap() async {
    try {
      Response response = await _dio.get('/generate-heatmap');
      return HeatmapResponse.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to generate heatmap: $e');
    }
  }

  // Disease Detection - Broiler
  Future<DiseaseResponse> analyzeBroilerDisease(dynamic imageFile) async {
    try {
      FormData formData;
      
      if (kIsWeb) {
        // Web platform - XFile from image_picker
        final xFile = imageFile as XFile;
        final bytes = await xFile.readAsBytes();
        final fileName = xFile.name;
        formData = FormData.fromMap({
          'image': MultipartFile.fromBytes(
            bytes,
            filename: fileName,
          ),
        });
      } else {
        // Mobile platform - XFile works on both, use path directly
        final xFile = imageFile as XFile;
        String fileName = xFile.path.split('/').last;
        formData = FormData.fromMap({
          'image': await MultipartFile.fromFile(
            xFile.path,
            filename: fileName,
          ),
        });
      }

      Response response = await _dio.post(
        '/analyze-broiler-disease',
        data: formData,
      );

      return DiseaseResponse.fromJson(response.data);
    } catch (e) {
      // Try mock endpoint if main fails
      try {
        FormData formData;
        
        if (kIsWeb) {
          final xFile = imageFile as XFile;
          final bytes = await xFile.readAsBytes();
          final fileName = xFile.name;
          formData = FormData.fromMap({
            'image': MultipartFile.fromBytes(
              bytes,
              filename: fileName,
            ),
          });
        } else {
          // Mobile platform - XFile works on both
          final xFile = imageFile as XFile;
          String fileName = xFile.path.split('/').last;
          formData = FormData.fromMap({
            'image': await MultipartFile.fromFile(
              xFile.path,
              filename: fileName,
            ),
          });
        }

        Response response = await _dio.post(
          '/analyze-broiler-disease-mock',
          data: formData,
        );

        return DiseaseResponse.fromJson(response.data);
      } catch (e2) {
        throw Exception('Failed to analyze broiler disease: $e2');
      }
    }
  }

  // Disease Detection - Fecal
  Future<DiseaseResponse> analyzeFecalDisease(dynamic imageFile) async {
    try {
      FormData formData;
      
      if (kIsWeb) {
        // Web platform - XFile from image_picker
        final xFile = imageFile as XFile;
        final bytes = await xFile.readAsBytes();
        final fileName = xFile.name;
        formData = FormData.fromMap({
          'image': MultipartFile.fromBytes(
            bytes,
            filename: fileName,
          ),
        });
      } else {
        // Mobile platform - XFile works on both, use path directly
        final xFile = imageFile as XFile;
        String fileName = xFile.path.split('/').last;
        formData = FormData.fromMap({
          'image': await MultipartFile.fromFile(
            xFile.path,
            filename: fileName,
          ),
        });
      }

      Response response = await _dio.post(
        '/analyze-fecal-disease',
        data: formData,
      );

      return DiseaseResponse.fromJson(response.data);
    } catch (e) {
      // Try mock endpoint if main fails
      try {
        FormData formData;
        
        if (kIsWeb) {
          final xFile = imageFile as XFile;
          final bytes = await xFile.readAsBytes();
          final fileName = xFile.name;
          formData = FormData.fromMap({
            'image': MultipartFile.fromBytes(
              bytes,
              filename: fileName,
            ),
          });
        } else {
          // Mobile platform - XFile works on both
          final xFile = imageFile as XFile;
          String fileName = xFile.path.split('/').last;
          formData = FormData.fromMap({
            'image': await MultipartFile.fromFile(
              xFile.path,
              filename: fileName,
            ),
          });
        }

        Response response = await _dio.post(
          '/analyze-fecal-disease-mock',
          data: formData,
        );

        return DiseaseResponse.fromJson(response.data);
      } catch (e2) {
        throw Exception('Failed to analyze fecal disease: $e2');
      }
    }
  }

  // Get full image URL
  String getImageUrl(String? path) {
    if (path == null) return '';
    if (path.startsWith('http')) return path;
    return '$baseUrl$path';
  }

  // Get video URL
  String getVideoUrl(String? filename) {
    if (filename == null) return '';
    return '$baseUrl/videooutputs/$filename';
  }
}

