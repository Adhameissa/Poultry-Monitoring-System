/// App Configuration
/// 
/// Easy switching between different platforms:
/// - Change [serverUrl] based on your target platform
/// - Options:
///   - Web/Edge: 'http://localhost:5000'
///   - Android Emulator: 'http://10.0.2.2:5000'
///   - iOS Simulator: 'http://localhost:5000'
///   - Physical Device: 'http://192.168.1.18:5000' (your network IP)
class AppConfig {
  // ============================================
  // QUICK SWITCH: Change this value to switch platforms
  // ============================================
  
  /// Server URL configuration
  /// 
  /// **For Web/Edge/Chrome:**
  /// ```dart
  /// static const String serverUrl = 'http://localhost:5000';
  /// ```
  /// 
  /// **For Android Emulator:**
  /// ```dart
  /// static const String serverUrl = 'http://10.0.2.2:5000';
  /// ```
  /// 
  /// **For iOS Simulator:**
  /// ```dart
  /// static const String serverUrl = 'http://localhost:5000';
  /// ```
  /// 
  /// **For Physical Device (same Wi-Fi network):**
  /// ```dart
  /// static const String serverUrl = 'http://192.168.1.18:5000';
  /// ```
  static const String serverUrl = 'http://localhost:5000'; // Currently set for Web/Edge
  
  // ============================================
  // Platform Presets (for reference)
  // ============================================
  
  /// Web/Edge/Chrome preset
  static const String webUrl = 'http://localhost:5000';
  
  /// Android Emulator preset
  static const String androidEmulatorUrl = 'http://10.0.2.2:5000';
  
  /// iOS Simulator preset
  static const String iosSimulatorUrl = 'http://localhost:5000';
  
  /// Physical Device preset (update with your network IP)
  static const String physicalDeviceUrl = 'http://192.168.1.18:5000';
}

