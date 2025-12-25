class DashboardResponse {
  final bool success;
  final int healthyCount;
  final int unhealthyCount;
  final int totalCount;
  final String? outputImage;
  final String? annotatedVideo;
  final String? message;

  DashboardResponse({
    required this.success,
    required this.healthyCount,
    required this.unhealthyCount,
    required this.totalCount,
    this.outputImage,
    this.annotatedVideo,
    this.message,
  });

  factory DashboardResponse.fromJson(Map<String, dynamic> json) {
    return DashboardResponse(
      success: json['success'] ?? false,
      healthyCount: json['healthy_count'] ?? 0,
      unhealthyCount: json['unhealthy_count'] ?? 0,
      totalCount: json['total_count'] ?? 0,
      outputImage: json['output_image'],
      annotatedVideo: json['annotated_video'],
      message: json['message'],
    );
  }

  String get healthStatus {
    if (totalCount == 0) return 'No Chickens';
    final percentage = (healthyCount / totalCount) * 100;
    if (percentage >= 80) return 'Excellent';
    if (percentage >= 60) return 'Good';
    if (percentage >= 40) return 'Fair';
    return 'Poor';
  }
}

class HeatmapResponse {
  final bool success;
  final String? heatmapPath;
  final String? error;

  HeatmapResponse({
    required this.success,
    this.heatmapPath,
    this.error,
  });

  factory HeatmapResponse.fromJson(Map<String, dynamic> json) {
    return HeatmapResponse(
      success: json['success'] ?? false,
      heatmapPath: json['heatmap_path'],
      error: json['error'],
    );
  }
}

