# SerialLens Flutter Build Instructions

## Prerequisites

*   **macOS** (Silicon M1/M2 recommended)
*   **Xcode** (Install from App Store)
*   **Homebrew**

## Quick Setup

Run the provided setup script to install Flutter and dependencies.
**Important:** This script will also attempt to patch the macOS entitlements to allow USB Serial access (disabling App Sandbox).

```bash
chmod +x setup_mac.sh
./setup_mac.sh
```

## Manual Setup

If you prefer to install manually:

1.  **Install Flutter:**
    ```bash
    brew install --cask flutter
    ```
2.  **Install libserialport:**
    ```bash
    brew install libserialport
    ```
3.  **Install CocoaPods:**
    ```bash
    brew install cocoapods
    ```
4.  **Configure Flutter:**
    ```bash
    flutter config --enable-macos-desktop
    flutter create .
    ```
5.  **Fix macOS Permissions (Critical):**
    By default, macOS apps are sandboxed and cannot access serial ports. You must edit `macos/Runner/DebugProfile.entitlements` and `macos/Runner/Release.entitlements`.

    Change `com.apple.security.app-sandbox` to `false`:
    ```xml
    <key>com.apple.security.app-sandbox</key>
    <false/>
    ```
    *Alternatively, add the `com.apple.security.device.serial` entitlement, but disabling sandbox is easier for local tools.*

## Running the App

To run in **Debug Mode** (with hot reload):

```bash
flutter run -d macos
```

## Building for Release

To create a standalone macOS Application (`.app`):

```bash
flutter build macos --release
```

The output file will be located at:
`build/macos/Build/Products/Release/serial_lens.app`

## Troubleshooting

*   **"App is damaged" or Security Warning:**
    Since this app is not code-signed with an Apple Developer Certificate, you may need to allow it manually in *System Settings > Privacy & Security* or run:
    ```bash
    xattr -cr build/macos/Build/Products/Release/serial_lens.app
    ```
