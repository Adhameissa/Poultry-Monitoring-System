# Poultry Monitoring System - Flutter App

A Flutter mobile application for poultry monitoring and disease detection, converted from the Flask web application.

## Features

- **Dashboard Analytics**: Monitor chicken count and health status
- **Disease Detection**: Detect diseases in broiler chickens and through fecal analysis
- **Weight Estimation**: Estimate chicken weight from images
- **Download Reports**: Download comprehensive disease reports with medication guidelines

## Setup Instructions

### Prerequisites

- Flutter SDK (3.0.0 or higher)
- Dart SDK
- Android Studio / Xcode (for mobile development)
- Your Flask backend server running

### Installation

1. **Navigate to the Flutter app directory:**
   ```bash
   cd flutter_app
   ```

2. **Install dependencies:**
   ```bash
   flutter pub get
   ```

3. **Update API Service URL:**
   - Open `lib/services/api_service.dart`
   - Update the `baseUrl` constant with your Flask server IP address:
   ```dart
   static const String baseUrl = 'http://YOUR_SERVER_IP:5000';
   ```
   - For Android emulator, use `http://10.0.2.2:5000`
   - For iOS simulator, use `http://localhost:5000`
   - For physical device, use your computer's IP address (e.g., `http://192.168.1.100:5000`)

4. **Run the app:**
   ```bash
   flutter run
   ```

## Project Structure

```
flutter_app/
├── lib/
│   ├── main.dart                 # App entry point and navigation
│   ├── models/                   # Data models
│   │   ├── disease_model.dart
│   │   └── dashboard_model.dart
│   ├── screens/                  # App screens
│   │   ├── home_screen.dart
│   │   ├── dashboard_screen.dart
│   │   ├── disease_screen.dart
│   │   └── weight_screen.dart
│   ├── services/                 # API services
│   │   └── api_service.dart
│   └── theme/                     # App theme
│       └── app_theme.dart
├── pubspec.yaml                  # Dependencies
└── README.md
```

## API Endpoints Used

The app communicates with the Flask backend using these endpoints:

- `POST /analyze-image` - Analyze image for chicken detection
- `POST /analyze-video` - Analyze video for chicken detection
- `GET /generate-heatmap` - Generate heatmap from video analysis
- `POST /analyze-broiler-disease` - Analyze broiler disease
- `POST /analyze-fecal-disease` - Analyze fecal disease
- `GET /outputs/<filename>` - Get output images
- `GET /videooutputs/<filename>` - Get output videos

## Features Implementation

### Dashboard Screen
- Upload images or videos
- View analysis results (healthy/unhealthy counts)
- Display annotated images/videos
- Generate heatmaps from video analysis

### Disease Detection Screen
- Upload broiler chicken images
- Upload fecal images
- View detailed disease information
- Download comprehensive reports
- View medication guidelines in Arabic

### Weight Estimation Screen
- Upload chicken images
- View estimated weight
- See weight category (Underweight/Optimal/Overweight)

## Troubleshooting

### Connection Issues

1. **Check Flask server is running:**
   ```bash
   # In your Flask app directory
   python app.py
   ```

2. **Verify network connectivity:**
   - Ensure your device/emulator can reach the server
   - Check firewall settings
   - For physical devices, ensure both devices are on the same network

3. **Update baseUrl:**
   - Make sure the `baseUrl` in `api_service.dart` matches your server address

### Build Issues

1. **Clean and rebuild:**
   ```bash
   flutter clean
   flutter pub get
   flutter run
   ```

2. **Check Flutter version:**
   ```bash
   flutter --version
   ```
   Should be 3.0.0 or higher

## Notes

- The app requires your Flask backend to be running and accessible
- Image/video uploads are sent to the backend for processing
- Reports are generated locally and can be shared via the device's share functionality
- The app uses cached network images for better performance

## License

Same as the original Flask application.

