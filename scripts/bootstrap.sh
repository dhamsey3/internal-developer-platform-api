#!/bin/bash
set -e

echo "[+] Bootstrapping local dev environment..."

# Create Python venv
echo "[+] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "[+] Done."
