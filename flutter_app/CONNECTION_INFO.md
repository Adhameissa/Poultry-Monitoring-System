# Connection Information

## Your Flask Server

Your Flask server is running and accessible at:

- **Localhost**: `http://127.0.0.1:5000`
- **Network IP**: `http://192.168.1.18:5000`
- **All interfaces**: `0.0.0.0:5000`

## Flutter App Configuration

The Flutter app is currently configured to use: `http://192.168.1.18:5000`

### To Change the Connection URL:

Edit `flutter_app/lib/services/api_service.dart` and update the `baseUrl`:

#### Option 1: For Android Emulator
```dart
static const String baseUrl = 'http://10.0.2.2:5000';
```

#### Option 2: For iOS Simulator
```dart
static const String baseUrl = 'http://127.0.0.1:5000';
// or
static const String baseUrl = 'http://localhost:5000';
```

#### Option 3: For Physical Device (Current Setting)
```dart
static const String baseUrl = 'http://192.168.1.18:5000';
```

## Testing Checklist

- [x] Flask server is running on port 5000
- [x] Server accessible at http://192.168.1.18:5000
- [ ] Flutter app `baseUrl` updated for your testing environment
- [ ] Phone and computer on same Wi-Fi network (for physical device)
- [ ] Test connection from Flutter app

## Quick Test

1. **Test Flask server in browser:**
   - Open: `http://192.168.1.18:5000`
   - Should see your Flask app homepage

2. **Test from Flutter app:**
   - Run the app
   - Try uploading an image
   - Check for connection errors

## Troubleshooting

### If connection fails on physical device:

1. **Check same network:**
   - Phone and computer must be on same Wi-Fi
   - Try accessing `http://192.168.1.18:5000` from phone's browser

2. **Check firewall:**
   - Windows Firewall might be blocking port 5000
   - Allow Python through firewall

3. **Try localhost alternatives:**
   - If on same machine, try `http://127.0.0.1:5000` for iOS simulator
   - Or `http://10.0.2.2:5000` for Android emulator

### Network IP Changed?

If your computer gets a new IP address:
1. Run `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
2. Find your new IPv4 address
3. Update `baseUrl` in `api_service.dart`
4. Restart Flask server if needed

