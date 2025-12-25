# Quick Platform Switching Guide

## How to Switch Between Platforms

### Option 1: Edit Config File (Recommended)

1. Open `lib/config/app_config.dart`
2. Change the `serverUrl` value in the `AppConfig` class:

```dart
// For Web/Edge:
static const String serverUrl = 'http://localhost:5000';

// For Android Emulator:
static const String serverUrl = 'http://10.0.2.2:5000';

// For iOS Simulator:
static const String serverUrl = 'http://localhost:5000';

// For Physical Device (update IP):
static const String serverUrl = 'http://192.168.1.18:5000';
```

3. Save the file
4. Run the app on your desired platform

### Option 2: Quick Commands

**Run on Edge:**
```bash
# 1. Set config to web URL in app_config.dart
# 2. Run:
flutter run -d edge
```

**Run on Android Emulator:**
```bash
# 1. Set config to emulator URL in app_config.dart
# 2. Run:
flutter run -d emulator-5554
```

## Current Configuration

Check `lib/config/app_config.dart` to see the current `serverUrl` setting.

## Platform URLs Reference

- **Web/Edge/Chrome**: `http://localhost:5000`
- **Android Emulator**: `http://10.0.2.2:5000` (special IP to access host localhost)
- **iOS Simulator**: `http://localhost:5000`
- **Physical Device**: `http://192.168.1.18:5000` (your computer's network IP)

## Important Notes

- Make sure your Flask server is running before launching the app
- For physical devices, ensure your phone and computer are on the same Wi-Fi network
- The Android emulator uses `10.0.2.2` as a special IP to access your computer's `localhost`

