#!/usr/bin/env bash
# Linux / macOS installer for stealth-site-cloner.
# Run from the repo root: bash scripts/install.sh

set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed." >&2
  echo "  Linux:  sudo apt install python3 python3-pip python3-venv" >&2
  echo "  macOS:  brew install python" >&2
  exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python: $PY_VERSION"

PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 10 ]]; }; then
  echo "Error: Python 3.10 or newer is required (found $PY_VERSION)." >&2
  exit 1
fi

echo
echo "==> Upgrading pip"
python3 -m pip install --upgrade pip

echo
echo "==> Installing Python dependencies"
python3 -m pip install -r requirements.txt

echo
echo "==> Downloading Chromium for Playwright (~150 MB)"
python3 -m playwright install chromium

# On Linux, Chromium needs a handful of system shared libraries to start.
# 'install-deps' uses apt/yum/dnf and needs sudo; we don't fail if it's not
# possible — most modern desktop distros already have what's needed.
if [[ "$(uname)" == "Linux" ]]; then
  echo
  echo "==> Installing Chromium system dependencies (Linux only — may need sudo)"
  if ! python3 -m playwright install-deps chromium 2>/dev/null; then
    echo "  (skipped — re-run with sudo if Chromium fails to launch:"
    echo "     sudo \$(which python3) -m playwright install-deps chromium )"
  fi
fi

echo
echo "Done."
echo "Try:  python3 stealth_clone.py https://example.com/ --out ./out/ --limit 1"
