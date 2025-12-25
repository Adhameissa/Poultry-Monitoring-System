import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../theme/app_theme.dart';

class WeightScreen extends StatefulWidget {
  const WeightScreen({super.key});

  @override
  State<WeightScreen> createState() => _WeightScreenState();
}

class _WeightScreenState extends State<WeightScreen> {
  File? _selectedFile;
  bool _isLoading = false;
  double? _estimatedWeight;
  String? _weightCategory;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Weight Estimation'),
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
                      'Weight Estimation',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.darkGreen,
                      ),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'Upload an image to estimate chicken weight',
                      style: TextStyle(color: AppTheme.textColor),
                    ),
                    const SizedBox(height: 20),
                    InkWell(
                      onTap: _pickImage,
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.all(30),
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: AppTheme.lightGreen,
                            width: 2,
                            style: BorderStyle.solid,
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Column(
                          children: [
                            Icon(Icons.cloud_upload, size: 40, color: AppTheme.lightGreen),
                            SizedBox(height: 15),
                            Text(
                              'Click to upload image',
                              style: TextStyle(
                                color: AppTheme.textColor,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
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
                          'Selected: ${_selectedFile!.path.split('/').last}',
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
                          : _estimateWeight,
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
                                Text('Estimating...'),
                              ],
                            )
                          : const Text('Estimate Weight'),
                    ),
                  ],
                ),
              ),
            ),
            // Results Section
            if (_estimatedWeight != null) ...[
              const SizedBox(height: 20),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Container(
                        width: 80,
                        height: 80,
                        decoration: const BoxDecoration(
                          color: AppTheme.brown,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.scale,
                          color: AppTheme.white,
                          size: 40,
                        ),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        '${_estimatedWeight!.toStringAsFixed(1)} kg',
                        style: const TextStyle(
                          fontSize: 36,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.brown,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 20,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          color: _getCategoryColor(),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          _weightCategory ?? 'Unknown',
                          style: const TextStyle(
                            color: AppTheme.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                      ),
                      const SizedBox(height: 30),
                      // Progress Bar
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Weight Category',
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                              color: AppTheme.darkGreen,
                            ),
                          ),
                          const SizedBox(height: 10),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(10),
                            child: LinearProgressIndicator(
                              value: _getProgressValue(),
                              minHeight: 20,
                              backgroundColor: Colors.grey[300],
                              valueColor: AlwaysStoppedAnimation<Color>(
                                _getCategoryColor(),
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          const Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Underweight',
                                style: TextStyle(fontSize: 12),
                              ),
                              Text(
                                'Optimal',
                                style: TextStyle(fontSize: 12),
                              ),
                              Text(
                                'Overweight',
                                style: TextStyle(fontSize: 12),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _pickImage() async {
    final ImagePicker picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() {
        _selectedFile = File(image.path);
        _estimatedWeight = null;
        _weightCategory = null;
      });
    }
  }

  Future<void> _estimateWeight() async {
    if (_selectedFile == null) return;

    setState(() {
      _isLoading = true;
    });

    // Simulate API call - Replace with actual API call when backend is ready
    await Future.delayed(const Duration(seconds: 2));

    // Mock weight estimation (replace with actual API call)
    final random = DateTime.now().millisecondsSinceEpoch % 200;
    final weight = 1.5 + (random / 100);

    setState(() {
      _estimatedWeight = weight;
      if (weight < 2.0) {
        _weightCategory = 'Underweight';
      } else if (weight >= 2.0 && weight <= 2.8) {
        _weightCategory = 'Optimal';
      } else {
        _weightCategory = 'Overweight';
      }
      _isLoading = false;
    });

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Weight estimation completed!'),
          backgroundColor: AppTheme.primaryGreen,
        ),
      );
    }
  }

  Color _getCategoryColor() {
    if (_weightCategory == null) return AppTheme.brown;
    switch (_weightCategory) {
      case 'Underweight':
        return Colors.red;
      case 'Optimal':
        return AppTheme.primaryGreen;
      case 'Overweight':
        return AppTheme.yellow;
      default:
        return AppTheme.brown;
    }
  }

  double _getProgressValue() {
    if (_estimatedWeight == null) return 0.0;
    // Normalize weight between 1.5 and 3.5 kg
    return ((_estimatedWeight! - 1.5) / 2.0).clamp(0.0, 1.0);
  }
}

