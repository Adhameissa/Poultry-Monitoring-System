# How to Run the Flutter App

## Prerequisites

1. **Flutter SDK installed**
   - Download from: https://flutter.dev/docs/get-started/install
   - Verify installation:
     ```bash
     flutter --version
     flutter doctor
     ```

2. **Flask server running**
   - Your Flask server should be running on `http://192.168.1.18:5000`
   - If not running, start it:
     ```bash
     cd "F:\poultry monitoring system"
     python app.py
     ```

3. **IDE/Editor** (optional but recommended)
   - Android Studio (with Flutter plugin)
   - VS Code (with Flutter extension)
   - Or any text editor

## Step-by-Step Instructions

### Step 1: Navigate to Flutter App Directory

Open terminal/command prompt and navigate to the Flutter app folder:

```bash
cd "F:\poultry monitoring system\flutter_app"
```

### Step 2: Install Dependencies

Install all required Flutter packages:

```bash
flutter pub get
```

This will download all dependencies listed in `pubspec.yaml`.

### Step 3: Check Flutter Setup

Verify your Flutter environment is ready:

```bash
flutter doctor
```

Make sure you have:
- ✅ Flutter SDK
- ✅ Android toolchain (for Android) OR Xcode (for iOS)
- ✅ Connected device or emulator

### Step 4: Connect a Device or Start Emulator

#### Option A: Run on Web (Microsoft Edge) - Quick Start! ⚡

**This is the fastest way to test the app without an emulator!**

1. **Enable Web Support** (one-time setup):
   ```bash
   flutter config --enable-web
   ```

2. **Check web support:**
   ```bash
   flutter devices
   ```
   You should see `Chrome` or `Edge` listed.

3. **Run on Edge:**
   ```bash
   flutter run -d edge
   ```
   Or if Edge is not detected:
   ```bash
   flutter run -d chrome
   ```
   Then manually open Edge and navigate to the URL shown.

4. **Alternative - Specify Edge explicitly:**
   ```bash
   flutter run -d web-server --web-port=8080
   ```
   Then open Edge browser and go to: `http://localhost:8080`

**Note for Web:**
- ✅ Works immediately, no emulator needed
- ✅ Good for quick testing
- ⚠️ Some features may have limitations (file uploads work, but video might be limited)
- ⚠️ Make sure your `baseUrl` in `api_service.dart` is set to `http://192.168.1.18:5000` or `http://localhost:5000`

#### Option B: Physical Device (Recommended for testing with network IP)

**For Android:**
1. Enable Developer Options on your phone:
   - Go to Settings → About Phone
   - Tap "Build Number" 7 times
2. Enable USB Debugging:
   - Settings → Developer Options → USB Debugging
3. Connect phone via USB
4. Verify connection:
   ```bash
   flutter devices
   ```

**For iOS:**
1. Connect iPhone via USB
2. Trust the computer on your iPhone
3. Verify connection:
   ```bash
   flutter devices
   ```

#### Option B: Android Emulator

1. Open Android Studio
2. Tools → Device Manager
3. Create/Start an Android Virtual Device (AVD)
4. Wait for emulator to boot
5. Verify:
   ```bash
   flutter devices
   ```

#### Option C: iOS Simulator (Mac only)

1. Open Xcode
2. Xcode → Open Developer Tool → Simulator
3. Start a simulator
4. Verify:
   ```bash
   flutter devices
   ```

### Step 5: Update API URL (If Needed)

**IMPORTANT**: Check your testing environment and update `api_service.dart` if needed:

1. Open: `flutter_app/lib/services/api_service.dart`
2. Check the `baseUrl`:
   - **Physical Device**: `http://192.168.1.18:5000` ✅ (already set)
   - **Android Emulator**: Change to `http://10.0.2.2:5000`
   - **iOS Simulator**: Change to `http://127.0.0.1:5000`

### Step 6: Run the App

#### Method 1: Run on Web/Edge (Fastest - No Emulator Needed!)

```bash
# Enable web support (one-time)
flutter config --enable-web

# Run on Edge
flutter run -d edge

# Or run on Chrome (then open in Edge manually)
flutter run -d chrome

# Or run web server and open in Edge manually
flutter run -d web-server --web-port=8080
# Then open Edge and go to: http://localhost:8080
```

#### Method 2: Command Line (Device/Emulator)

```bash
flutter run
```

This will:
- Build the app
- Install it on your device/emulator
- Launch the app
- Enable hot reload for development

#### Method 2: Run with Specific Device

If you have multiple devices:

```bash
# List available devices
flutter devices

# Run on specific device
flutter run -d <device-id>
```

#### Method 3: Using IDE

**Android Studio:**
1. Open the `flutter_app` folder
2. Select device from toolbar
3. Click Run button (▶️)

**VS Code:**
1. Open the `flutter_app` folder
2. Press `F5` or click Run → Start Debugging
3. Select device when prompted

## What to Expect

1. **First Run**: Takes longer (2-5 minutes) as it builds the app
2. **Subsequent Runs**: Faster (30 seconds - 2 minutes)
3. **App Launch**: The app should open on your device/emulator
4. **Home Screen**: You should see the Poultry Monitoring System home screen

## Testing the Connection

1. **Navigate to Dashboard** (tap Dashboard in bottom navigation)
2. **Upload an Image**:
   - Tap "Photo" upload area
   - Select an image from gallery
   - Tap "Analyze"
3. **Check Results**: 
   - Should see analysis results
   - If you see errors, check Flask server is running

## Troubleshooting

### Error: "No devices found"

**Solution:**
- Make sure device/emulator is connected
- Run `flutter devices` to verify
- For Android: Enable USB debugging
- For iOS: Trust the computer

### Error: "Connection refused" or "Failed to connect"

**Solution:**
1. Verify Flask server is running:
   - Check browser: `http://192.168.1.18:5000`
2. Check `baseUrl` in `api_service.dart`:
   - Physical device: `http://192.168.1.18:5000`
   - Emulator: `http://10.0.2.2:5000`
3. Check same Wi-Fi network (for physical device)
4. Check firewall settings

### Error: "flutter: command not found"

**Solution:**
- Add Flutter to PATH
- Restart terminal
- Verify: `flutter --version`

### Error: "pub get failed"

**Solution:**
```bash
flutter clean
flutter pub get
```

### App crashes on launch

**Solution:**
1. Check Flutter version: `flutter --version` (should be 3.0+)
2. Clean and rebuild:
   ```bash
   flutter clean
   flutter pub get
   flutter run
   ```

## Development Tips

### Hot Reload
While app is running:
- Press `r` in terminal to hot reload
- Press `R` to hot restart
- Press `q` to quit

### View Logs
```bash
flutter logs
```

### Build for Release
```bash
# Android APK
flutter build apk

# iOS (Mac only)
flutter build ios
```

## Quick Command Reference

```bash
# Navigate to app
cd "F:\poultry monitoring system\flutter_app"

# Install dependencies
flutter pub get

# Enable web support (one-time, for Edge/Chrome)
flutter config --enable-web

# Check devices (should show Edge/Chrome after enabling web)
flutter devices

# Run on Edge (FASTEST - no emulator needed!)
flutter run -d edge

# Run on device/emulator
flutter run

# Clean build
flutter clean

# Check Flutter setup
flutter doctor
```

## Next Steps After Running

1. ✅ App launches successfully
2. ✅ Test Dashboard - upload image/video
3. ✅ Test Disease Detection - upload broiler/fecal image
4. ✅ Test Weight Estimation - upload image
5. ✅ Verify all features work with Flask backend

## Need Help?

- Check Flutter console for error messages
- Check Flask server console for API requests
- Verify network connectivity
- Review `CONNECTION_INFO.md` for connection details

