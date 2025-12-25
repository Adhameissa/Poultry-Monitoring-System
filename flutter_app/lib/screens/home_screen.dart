import 'package:flutter/material.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import '../theme/app_theme.dart';

class HomeScreen extends StatelessWidget {
  final Function(int)? onNavigate;
  
  const HomeScreen({super.key, this.onNavigate});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.pets, color: AppTheme.primaryGreen),
            SizedBox(width: 10),
            Text('Poultry Monitor'),
          ],
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // Hero Section
            Container(
              padding: const EdgeInsets.all(40),
              child: Column(
                children: [
                  const Text(
                    'Poultry Monitoring System',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.darkGreen,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 15),
                  const Text(
                    'Advanced AI-powered monitoring for healthier poultry farms',
                    style: TextStyle(
                      fontSize: 16,
                      color: AppTheme.textColor,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 30),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      ElevatedButton(
                        onPressed: () {
                          onNavigate?.call(1); // Navigate to Dashboard
                        },
                        child: const Text('Get Started'),
                      ),
                      const SizedBox(width: 15),
                      OutlinedButton(
                        onPressed: () {
                          // Scroll to features
                        },
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppTheme.primaryGreen,
                          side: const BorderSide(color: AppTheme.primaryGreen),
                        ),
                        child: const Text('Learn More'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            // Features Section
            Container(
              padding: const EdgeInsets.all(20),
              color: AppTheme.white,
              child: Column(
                children: [
                  const Text(
                    'Our Features',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.darkGreen,
                    ),
                  ),
                  const SizedBox(height: 30),
                  _buildFeatureCard(
                    context,
                    icon: FontAwesomeIcons.chartLine,
                    title: 'Dashboard Analytics',
                    description: 'Monitor chicken count and health status in real-time with our comprehensive dashboard.',
                    onTap: () {
                      onNavigate?.call(1); // Navigate to Dashboard
                    },
                  ),
                  const SizedBox(height: 20),
                  _buildFeatureCard(
                    context,
                    icon: FontAwesomeIcons.virus,
                    title: 'Disease Detection',
                    description: 'Detect diseases in broiler chickens and through fecal analysis with AI models.',
                    onTap: () {
                      onNavigate?.call(2); // Navigate to Disease
                    },
                  ),
                  const SizedBox(height: 20),
                  _buildFeatureCard(
                    context,
                    icon: FontAwesomeIcons.weightScale,
                    title: 'Weight Estimation',
                    description: 'Estimate chicken weight from images with our trained computer vision model.',
                    onTap: () {
                      onNavigate?.call(3); // Navigate to Weight
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureCard(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String description,
    required VoidCallback onTap,
  }) {
    return Card(
      elevation: 2,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: const BoxDecoration(
                  color: AppTheme.primaryGreen,
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: AppTheme.white, size: 40),
              ),
              const SizedBox(height: 15),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                description,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textColor,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 10),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text(
                    'View Details',
                    style: TextStyle(
                      color: AppTheme.primaryGreen,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(width: 5),
                  const Icon(
                    Icons.arrow_forward,
                    color: AppTheme.primaryGreen,
                    size: 16,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

