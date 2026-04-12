# app

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Run with local API server

Ung dung da duoc noi login API den endpoint:

- `POST /api/v1/auth/login`

Base URL duoc nap qua `--dart-define`:

- Key: `API_BASE_URL`
- Mac dinh: `http://10.0.2.2:8000` (Android emulator -> host machine)

Vi du chay app tren emulator Android:

```bash
cd client/artifact_app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Neu server duoc truy cap qua Tailscale IP cua may local, co the dung:

```bash
flutter run --dart-define=API_BASE_URL=http://100.90.229.25:8000
```

