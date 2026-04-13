# Build va cài app mobile Artifact len Android emulator (khong can Android Studio)

## 1) Cai dependencies he thong

```bash
sudo apt update
sudo apt install -y curl unzip zip xz-utils libglu1-mesa openjdk-17-jdk qemu-kvm
```

Neu can quyen KVM (de emulator nhanh hon):

```bash
sudo usermod -aG kvm "$USER"
```

Dang xuat/vao lai terminal sau khi add group.

## 2) Cai Flutter

```bash
sudo snap install flutter --classic
flutter --version
```

## 3) Cai Android command-line tools

```bash
mkdir -p "$HOME/Android/Sdk/cmdline-tools"
cd /tmp
rm -rf cmdline-tools cmdline-tools.zip
curl -Lo cmdline-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q cmdline-tools.zip
mkdir -p "$HOME/Android/Sdk/cmdline-tools/latest"
rm -rf "$HOME/Android/Sdk/cmdline-tools/latest"/*
mv cmdline-tools/* "$HOME/Android/Sdk/cmdline-tools/latest/"
```

## 4) Set bien moi truong Android SDK

```bash
grep -q 'ANDROID_HOME=$HOME/Android/Sdk' ~/.bashrc || echo 'export ANDROID_HOME=$HOME/Android/Sdk' >> ~/.bashrc
grep -q 'cmdline-tools/latest/bin' ~/.bashrc || echo 'export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin' >> ~/.bashrc
source ~/.bashrc
```

Kiem tra:

```bash
command -v sdkmanager
command -v adb
command -v emulator
```

## 5) Cai Android SDK packages can thiet

```bash
yes | sdkmanager --licenses
sdkmanager --install \
	"platform-tools" \
	"emulator" \
	"platforms;android-34" \
	"build-tools;34.0.0" \
	"system-images;android-34;google_apis;x86_64"
```

## 6) Tao AVD emulator

```bash
avdmanager delete avd -n artifact_api34 || true
echo "no" | avdmanager create avd \
	-n artifact_api34 \
	-k "system-images;android-34;google_apis;x86_64" \
	--device "pixel_6"
```

## 7) Chay emulator

```bash
emulator -avd artifact_api34 -memory 2048 -cores 2 -gpu swiftshader_indirect -no-snapshot -no-boot-anim
```

Mo terminal khac:

```bash
adb wait-for-device
while [[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" != "1" ]]; do echo "waiting emulator boot..."; sleep 1; done
adb devices
```

## 8) Build APK Artifact

```bash
cd /home/darkcode0x/Artifact-Pose-System/client/artifact_app
flutter pub get
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

APK tao ra tai:

`build/app/outputs/flutter-apk/app-debug.apk`

## 9) Cai APK vao emulator

```bash
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

Neu bao loi xung dot signature:

```bash
adb uninstall com.pbl5.artifactapp
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

## 10) Mo app

```bash
adb shell monkey -p com.pbl5.artifactapp -c android.intent.category.LAUNCHER 1
```

## 11) Ghi chu ket noi API

- `10.0.2.2` la host loopback tu Android emulator ve may local.
- Neu server cua ban chay o may local: `http://10.0.2.2:8000` la dung.
- Neu server chay qua Tailscale co the thay bang IP Tailscale host, vi du:

```bash
flutter build apk --debug --dart-define=API_BASE_URL=http://100.90.229.25:8000
```

## 12) Kiem tra nhanh truoc khi login

```bash
curl http://127.0.0.1:8000/health
```

Neu health khong `ok`, app se khong login duoc.