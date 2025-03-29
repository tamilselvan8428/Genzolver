#!/bin/bash

echo "🚀 Installing Microsoft Edge WebDriver..."
OS=$(uname)

if [[ "$OS" == "MINGW64_NT"* || "$OS" == "CYGWIN_NT"* ]]; then
    echo "🔹 Detected Windows OS"

    # Get Edge version from Windows registry properly
    EDGE_VERSION=$(powershell.exe -Command "(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Edge\BLBeacon' -ErrorAction SilentlyContinue).version")
    
    # If that fails, try another registry path
    if [[ -z "$EDGE_VERSION" ]]; then
        EDGE_VERSION=$(powershell.exe -Command "(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Edge\BLBeacon' -ErrorAction SilentlyContinue).version")
    fi
    
    # Check if we got a valid version
    if [[ -z "$EDGE_VERSION" ]]; then
        echo "❌ Could not determine Microsoft Edge version. Make sure Edge is installed."
        exit 1
    fi

    echo "🔹 Detected Edge Version: $EDGE_VERSION"

    # Download the correct WebDriver for the detected Edge version
    EDGE_DRIVER_URL="https://msedgedriver.azureedge.net/$EDGE_VERSION/edgedriver_win64.zip"

    echo "🔹 Downloading Edge WebDriver from: $EDGE_DRIVER_URL"
    curl -o edgedriver_win64.zip "$EDGE_DRIVER_URL"

    # Extract and install Edge WebDriver
    if [[ -f "edgedriver_win64.zip" ]]; then
        unzip -o edgedriver_win64.zip -d "$PWD"
        chmod +x msedgedriver.exe
        echo "✅ Microsoft Edge WebDriver installed successfully!"
    else
        echo "❌ Download failed. Check your internet connection."
        exit 1
    fi

else
    echo "❌ Unsupported OS"
    exit 1
fi

exit 0
