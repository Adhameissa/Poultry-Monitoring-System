import 'dart:io' if (dart.library.html) 'dart:html' as io;
import 'dart:html' if (dart.library.io) 'dart:io' as html;
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../models/dashboard_model.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();
  dynamic _selectedFile; // XFile on web, File on mobile
  String? _fileType;
  bool _isLoading = false;
  DashboardResponse? _results;
  String? _heatmapUrl;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Upload Section
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Upload Media',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.darkGreen,
                      ),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'Upload a photo or video to analyze your poultry',
                      style: TextStyle(color: AppTheme.textColor),
                    ),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: _buildUploadOption(
                            icon: Icons.image,
                            label: 'Photo',
                            onTap: () => _pickImage(),
                          ),
                        ),
                        const SizedBox(width: 15),
                        Expanded(
                          child: _buildUploadOption(
                            icon: Icons.videocam,
                            label: 'Video',
                            onTap: () => _pickVideo(),
                          ),
                        ),
                      ],
                    ),
                    if (_selectedFile != null) ...[
                      const SizedBox(height: 15),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppTheme.lightGray,
                          borderRadius: BorderRadius.circular(5),
                          border: Border.all(color: AppTheme.primaryGreen),
                        ),
                        child: Text(
                          'Selected: ${_selectedFile is Map ? (_selectedFile as Map)['name'] : (_selectedFile is XFile ? _selectedFile.name : _selectedFile.toString().split('/').last)}',
                          style: const TextStyle(
                            color: AppTheme.darkGreen,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: _selectedFile == null || _isLoading
                          ? null
                          : _analyzeMedia,
                      child: _isLoading
                          ? const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      AppTheme.white,
                                    ),
                                  ),
                                ),
                                SizedBox(width: 10),
                                Text('Analyzing...'),
                              ],
                            )
                          : const Text('Analyze'),
                    ),
                    if (_fileType == 'video' && _results != null) ...[
                      const SizedBox(height: 10),
                      OutlinedButton(
                        onPressed: _isLoading ? null : _generateHeatmap,
                        child: const Text('Generate Heatmap'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            // Results Section
            if (_results != null) ...[
              const SizedBox(height: 20),
              const Text(
                'Analysis Results',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
              const SizedBox(height: 15),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 15,
                mainAxisSpacing: 15,
                childAspectRatio: 1.1,
                children: [
                  _buildResultCard(
                    icon: Icons.pets,
                    title: 'Total Count',
                    value: '${_results!.totalCount}',
                    subtitle: 'Chickens detected',
                  ),
                  _buildResultCard(
                    icon: Icons.favorite,
                    title: 'Health Status',
                    value: _results!.healthStatus,
                    subtitle: 'Overall flock health',
                    valueColor: _getHealthColor(_results!.healthStatus),
                  ),
                  _buildResultCard(
                    icon: Icons.check_circle,
                    title: 'Healthy',
                    value: '${_results!.healthyCount}',
                    subtitle: 'Healthy chickens',
                  ),
                  _buildResultCard(
                    icon: Icons.warning,
                    title: 'Unhealthy',
                    value: '${_results!.unhealthyCount}',
                    subtitle: 'Requiring attention',
                  ),
                ],
              ),
            ],
            // Visualization Section
            if (_results != null && (_results!.outputImage != null || _results!.annotatedVideo != null)) ...[
              const SizedBox(height: 20),
              const Text(
                'Visualization',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
              const SizedBox(height: 15),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(15),
                  child: _fileType == 'image' && _results!.outputImage != null
                      ? CachedNetworkImage(
                          imageUrl: _apiService.getImageUrl(_results!.outputImage),
                          placeholder: (context, url) => const Center(
                            child: CircularProgressIndicator(),
                          ),
                          errorWidget: (context, url, error) => const Icon(Icons.error),
                        )
                      : _fileType == 'video' && _results!.annotatedVideo != null
                          ? Column(
                              children: [
                                // Video player would go here
                                // For now, show a placeholder
                                const Icon(Icons.videocam, size: 50),
                                const SizedBox(height: 10),
                                Text('Video: ${_results!.annotatedVideo}'),
                                if (_heatmapUrl != null) ...[
                                  const SizedBox(height: 20),
                                  CachedNetworkImage(
                                    imageUrl: _apiService.getImageUrl(_heatmapUrl),
                                    placeholder: (context, url) => const Center(
                                      child: CircularProgressIndicator(),
                                    ),
                                    errorWidget: (context, url, error) => const Icon(Icons.error),
                                  ),
                                ],
                              ],
                            )
                          : const Text('No visualization available'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildUploadOption({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          border: Border.all(color: AppTheme.lightGreen, width: 2, style: BorderStyle.solid),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Icon(icon, size: 40, color: AppTheme.lightGreen),
            const SizedBox(height: 10),
            Text(
              label,
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: AppTheme.darkGreen,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard({
    required IconData icon,
    required String title,
    required String value,
    required String subtitle,
    Color? valueColor,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 50,
              height: 50,
              decoration: const BoxDecoration(
                color: AppTheme.primaryGreen,
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: AppTheme.white, size: 25),
            ),
            const SizedBox(height: 10),
            Text(
              title,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: AppTheme.darkGreen,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              value,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: valueColor ?? AppTheme.brown,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              subtitle,
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textColor,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Color _getHealthColor(String status) {
    switch (status) {
      case 'Excellent':
        return AppTheme.primaryGreen;
      case 'Good':
        return AppTheme.lightGreen;
      case 'Fair':
        return AppTheme.yellow;
      case 'Poor':
        return Colors.red;
      default:
        return AppTheme.brown;
    }
  }

  Future<void> _pickImage() async {
    final ImagePicker picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() {
        // Use XFile on both platforms - it works everywhere
        _selectedFile = image;
        _fileType = 'image';
        _results = null;
        _heatmapUrl = null;
      });
    }
  }

  Future<void> _pickVideo() async {
    if (kIsWeb) {
      // For web, use file_picker
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.video,
      );
      if (result != null && result.files.single.bytes != null) {
        // On web, store the file bytes and name
        // The actual file object will be created when needed in api_service
        final bytes = result.files.single.bytes!;
        final fileName = result.files.single.name;
        // Store as a map with bytes and name for web
        _selectedFile = {'bytes': bytes, 'name': fileName};
        setState(() {
          _fileType = 'video';
          _results = null;
          _heatmapUrl = null;
        });
      }
    } else {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.video,
      );
      if (result != null && result.files.single.path != null) {
        setState(() {
          // Store the path as a string for mobile, will be converted to File when needed
          _selectedFile = result.files.single.path!;
          _fileType = 'video';
          _results = null;
          _heatmapUrl = null;
        });
      }
    }
  }

  Future<void> _analyzeMedia() async {
    if (_selectedFile == null) return;

    setState(() {
      _isLoading = true;
    });

    try {
      DashboardResponse response;
      if (_fileType == 'image') {
        response = await _apiService.analyzeImage(_selectedFile!);
      } else {
        response = await _apiService.analyzeVideo(_selectedFile!);
      }

      setState(() {
        _results = response;
        _isLoading = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Analysis completed successfully!'),
            backgroundColor: AppTheme.primaryGreen,
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Analysis failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _generateHeatmap() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final response = await _apiService.generateHeatmap();
      setState(() {
        _heatmapUrl = response.heatmapPath;
        _isLoading = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Heatmap generated successfully!'),
            backgroundColor: AppTheme.primaryGreen,
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Heatmap generation failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }
}

