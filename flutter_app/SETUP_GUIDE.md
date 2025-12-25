# Flutter App Setup Guide - Connecting to Flask Server

## Flask Server Configuration

Your Flask server is configured to run on:
- **Host**: `0.0.0.0` (listens on all network interfaces)
- **Port**: `5000`

This means your server is accessible from:
- Localhost: `http://localhost:5000`
- Network: `http://YOUR_COMPUTER_IP:5000`

## Flutter App Configuration

### Step 1: Update API Service URL

Open `flutter_app/lib/services/api_service.dart` and update the `baseUrl` based on your testing environment:

#### For Android Emulator:
```dart
static const String baseUrl = 'http://10.0.2.2:5000';
```
*(10.0.2.2 is a special IP that Android emulator uses to access the host machine)*

#### For iOS Simulator:
```dart
static const String baseUrl = 'http://localhost:5000';
```

#### For Physical Device (Phone/Tablet):
1. Find your computer's IP address:
   - **Windows**: Open Command Prompt and run `ipconfig`
     - Look for "IPv4 Address" (e.g., 192.168.1.100)
   - **Mac/Linux**: Open Terminal and run `ifconfig` or `ip addr`
     - Look for your network interface IP (e.g., 192.168.1.100)

2. Update the baseUrl:
   ```dart
   static const String baseUrl = 'http://192.168.1.100:5000'; // Replace with your IP
   ```

3. **Important**: Make sure your phone and computer are on the same Wi-Fi network!

### Step 2: Start Flask Server

Make sure your Flask server is running:

```bash
# In your Flask project directory
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
```

### Step 3: Test Connection

1. **Test Flask server directly:**
   - Open browser on your computer
   - Go to `http://localhost:5000`
   - You should see your Flask app

2. **Test from Flutter app:**
   - Run the Flutter app
   - Try uploading an image in Dashboard or Disease Detection
   - Check for connection errors in the console

## Troubleshooting

### Connection Refused / Timeout

1. **Check Flask server is running:**
   ```bash
   # Check if port 5000 is in use
   netstat -an | findstr 5000  # Windows
   lsof -i :5000                # Mac/Linux
   ```

2. **Check firewall settings:**
   - Windows: Allow Python through Windows Firewall
   - Make sure port 5000 is not blocked

3. **Verify IP address:**
   - Make sure you're using the correct IP for your device type
   - For physical devices, both devices must be on same network

4. **Test with curl/Postman:**
   ```bash
   # Test from command line
   curl http://localhost:5000/
   ```

### CORS Errors

If you see CORS errors, your Flask app already has CORS enabled:
```python
from flask_cors import CORS
CORS(app)
```

This should allow requests from the Flutter app.

### Network Security (Android)

For Android 9+ (API 28+), you may need to allow cleartext traffic:

1. Create/edit `android/app/src/main/AndroidManifest.xml`:
   ```xml
   <application
       android:usesCleartextTraffic="true"
       ...>
   ```

2. Or create `android/app/src/main/res/xml/network_security_config.xml`:
   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <network-security-config>
       <domain-config cleartextTrafficPermitted="true">
           <domain includeSubdomains="true">10.0.2.2</domain>
           <domain includeSubdomains="true">localhost</domain>
           <domain includeSubdomains="true">192.168.1.0</domain>
       </domain-config>
   </network-security-config>
   ```

   Then reference it in AndroidManifest.xml:
   ```xml
   <application
       android:networkSecurityConfig="@xml/network_security_config"
       ...>
   ```

## Quick Reference

| Environment | baseUrl |
|------------|---------|
| Android Emulator | `http://10.0.2.2:5000` |
| iOS Simulator | `http://localhost:5000` |
| Physical Device | `http://YOUR_IP:5000` |

## Testing Checklist

- [ ] Flask server is running on port 5000
- [ ] Updated `baseUrl` in `api_service.dart` for your environment
- [ ] Tested Flask server in browser (`http://localhost:5000`)
- [ ] Flutter app can connect (no connection errors)
- [ ] Image upload works
- [ ] API responses are received

## Need Help?

If you're still having connection issues:

1. Check Flutter console for error messages
2. Check Flask server console for incoming requests
3. Verify network connectivity
4. Try using your computer's IP address instead of localhost/10.0.2.2

