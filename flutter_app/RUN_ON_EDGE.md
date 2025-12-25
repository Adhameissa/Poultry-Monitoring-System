# Run Flutter App on Microsoft Edge (No Emulator Needed!)

This is the **fastest way** to test your Flutter app without downloading an emulator.

## Quick Start (3 Steps)

### Step 1: Enable Web Support (One-Time Setup)

```bash
cd "F:\poultry monitoring system\flutter_app"
flutter config --enable-web
```

### Step 2: Install Dependencies

```bash
flutter pub get
```

### Step 3: Run on Edge

```bash
flutter run -d edge
```

That's it! The app will open in Microsoft Edge automatically.

## Alternative Methods

### Method 1: Run on Chrome (then open in Edge)

```bash
flutter run -d chrome
```

Then manually open Edge and copy the URL from Chrome.

### Method 2: Run Web Server

```bash
flutter run -d web-server --web-port=8080
```

Then open Microsoft Edge and navigate to:
```
http://localhost:8080
```

### Method 3: Build and Serve

```bash
# Build for web
flutter build web

# Serve the build (requires Python or any web server)
cd build/web
python -m http.server 8080
```

Then open Edge: `http://localhost:8080`

## Verify Web Support

Check if web is enabled:

```bash
flutter devices
```

You should see:
```
Chrome (chrome) • chrome • web-javascript • Google Chrome
Edge (edge)     • edge   • web-javascript • Microsoft Edge
```

## Important Notes for Web

### ✅ What Works:
- All screens and navigation
- Image uploads
- API calls to Flask server
- Disease detection
- Dashboard analytics
- Download reports

### ⚠️ Limitations:
- Video upload/playback might have limitations
- Some native features may not work
- Performance might be slightly different from mobile

### API Configuration for Web

Since you're running on the same computer as Flask:

1. Open `lib/services/api_service.dart`
2. Update `baseUrl` to:
   ```dart
   static const String baseUrl = 'http://localhost:5000';
   ```
   Or keep `http://192.168.1.18:5000` if you prefer.

## Troubleshooting

### Error: "No devices found" or Edge not listed

**Solution:**
```bash
# Enable web support
flutter config --enable-web

# Verify
flutter devices
```

### Error: "Web support is not enabled"

**Solution:**
```bash
flutter config --enable-web
flutter doctor
```

### App doesn't open in Edge automatically

**Solution:**
1. Check the terminal for the URL (usually `http://localhost:xxxxx`)
2. Manually open Edge
3. Navigate to that URL

### Connection to Flask server fails

**Solution:**
1. Make sure Flask server is running: `http://localhost:5000`
2. Update `baseUrl` in `api_service.dart` to `http://localhost:5000`
3. Check browser console (F12) for errors

### CORS Errors

If you see CORS errors:
- Your Flask app already has CORS enabled, but if issues persist:
- Check Flask server console for errors
- Verify `baseUrl` is correct

## Development Tips

### Hot Reload on Web
- Press `r` in terminal for hot reload
- Press `R` for hot restart
- Changes appear instantly in Edge

### Debug in Edge
1. Press `F12` in Edge to open DevTools
2. Check Console for errors
3. Check Network tab for API calls

### View Logs
```bash
flutter logs
```

## Quick Commands Summary

```bash
# One-time setup
flutter config --enable-web

# Run on Edge
flutter run -d edge

# Run on Chrome
flutter run -d chrome

# Run web server
flutter run -d web-server --web-port=8080
```

## Next Steps

Once you're ready to test on mobile:
1. Download Android Studio for Android emulator
2. Or connect a physical device
3. Then use `flutter run` (without `-d edge`)

For now, Edge is perfect for:
- ✅ Testing all features
- ✅ Verifying Flask connection
- ✅ UI/UX testing
- ✅ Quick development

## Full Workflow

```bash
# 1. Navigate to app
cd "F:\poultry monitoring system\flutter_app"

# 2. Enable web (one-time)
flutter config --enable-web

# 3. Install dependencies
flutter pub get

# 4. Make sure Flask is running (in another terminal)
# cd "F:\poultry monitoring system"
# python app.py

# 5. Run on Edge
flutter run -d edge

# 6. App opens in Edge automatically!
```

Enjoy testing your app in Edge! 🚀

