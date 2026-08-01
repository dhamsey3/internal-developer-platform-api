#!/bin/bash
set -e

echo "[+] Bootstrapping local dev environment..."

# Create Python venv
echo "[+] Creating Python virtual environment..."
if ! python3 -m venv .venv; then
  echo "[!] Failed to create virtual environment."
  echo "[!] On Debian/Ubuntu, install python3-venv: sudo apt install python3-venv"
  exit 1
fi
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "[+] Done."
