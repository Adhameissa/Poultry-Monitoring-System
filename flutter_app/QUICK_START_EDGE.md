# 🚀 Quick Start: Run on Edge (No Emulator!)

**Fastest way to test your app - 3 commands!**

## Step 1: Enable Web Support (One-Time)

```bash
cd "F:\poultry monitoring system\flutter_app"
flutter config --enable-web
```

## Step 2: Install Dependencies

```bash
flutter pub get
```

## Step 3: Run on Edge

```bash
flutter run -d edge
```

**Done!** The app opens in Microsoft Edge automatically! 🎉

---

## Make Sure Flask Server is Running

In another terminal window:

```bash
cd "F:\poultry monitoring system"
python app.py
```

You should see: `Running on http://192.168.1.18:5000`

---

## That's It!

The app is now running in Edge. You can:
- ✅ Test all features
- ✅ Upload images
- ✅ Connect to Flask server
- ✅ Test disease detection
- ✅ Download reports

## Need Help?

See `RUN_ON_EDGE.md` for detailed instructions and troubleshooting.

