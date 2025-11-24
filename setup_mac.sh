#!/bin/bash

# SerialLens Mac Setup Script
# Installs Flutter and dependencies via Homebrew

set -e

echo "🔹 Starting SerialLens Setup..."

# 1. Check/Install Homebrew
if ! command -v brew &> /dev/null; then
    echo "🔸 Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add brew to path for Apple Silicon (M1/M2)
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✅ Homebrew detected."
fi

# 2. Install Flutter
if ! command -v flutter &> /dev/null; then
    echo "🔸 Installing Flutter..."
    brew install --cask flutter
else
    echo "✅ Flutter detected."
fi

# 3. Install libserialport (Native dependency)
echo "🔸 Checking native dependencies..."
if ! brew list libserialport &> /dev/null; then
    echo "🔸 Installing libserialport..."
    brew install libserialport
else
    echo "✅ libserialport detected."
fi

# 4. Install CocoaPods (Required for MacOS builds)
if ! command -v pod &> /dev/null; then
    echo "🔸 Installing CocoaPods..."
    brew install cocoapods
else
    echo "✅ CocoaPods detected."
fi

# 5. Project Setup & Scaffolding
echo "🔹 Setting up project..."

# Ensure we have the macOS runner scaffolding
if [ ! -d "macos" ]; then
    echo "🔸 Generating macOS runner..."
    flutter config --enable-macos-desktop
    flutter create . --platforms=macos
fi

echo "🔸 Getting packages..."
flutter pub get

# 6. Patching Entitlements (Disable Sandbox for Serial Access)
echo "🔹 Patching macOS Entitlements..."

ENTITLEMENTS_DEBUG="macos/Runner/DebugProfile.entitlements"
ENTITLEMENTS_RELEASE="macos/Runner/Release.entitlements"

patch_entitlements() {
    local file=$1
    if [ -f "$file" ]; then
        # Check if sandbox is true, then replace it
        if grep -q "<key>com.apple.security.app-sandbox</key>" "$file"; then
             # Simple sed replacement for true -> false for the sandbox key specifically
             # We assume standard formatting from flutter create
             sed -i '' '/<key>com.apple.security.app-sandbox<\/key>/{n;s/<true\/>/<false\/>/;}' "$file"
             echo "✅ Patched $file (Sandbox Disabled)"
        else
             echo "⚠️  Could not find sandbox key in $file"
        fi
    fi
}

patch_entitlements "$ENTITLEMENTS_DEBUG"
patch_entitlements "$ENTITLEMENTS_RELEASE"

echo "✅ Setup Complete!"
echo ""
echo "🚀 To run the app:"
echo "   flutter run -d macos"
echo ""
echo "📦 To build a release .app:"
echo "   flutter build macos --release"
