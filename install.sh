#!/bin/bash
echo "🚀 Installing Google Chrome & ChromeDriver..."

# Install Chrome
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y

# Install ChromeDriver
wget -q https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/bin/chromedriver
chmod +x /usr/bin/chromedriver

echo "✅ Chrome & ChromeDriver installed!"
