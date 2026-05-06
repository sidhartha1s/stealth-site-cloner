# Windows PowerShell installer for stealth-site-cloner.
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1

$ErrorActionPreference = "Stop"

# Find a usable python: prefer 'python', fall back to 'python3'.
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
  Write-Host "Error: Python is not installed or not on PATH." -ForegroundColor Red
  Write-Host "  Install Python 3.10+ from https://python.org/downloads/windows/"
  Write-Host "  IMPORTANT: tick 'Add python.exe to PATH' during installation."
  exit 1
}

$pyVersion = & $py.Path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $pyVersion"

$pyMajor = [int](& $py.Path -c "import sys; print(sys.version_info.major)")
$pyMinor = [int](& $py.Path -c "import sys; print(sys.version_info.minor)")
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 10)) {
  Write-Host "Error: Python 3.10 or newer is required (found $pyVersion)." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "==> Upgrading pip"
& $py.Path -m pip install --upgrade pip

Write-Host ""
Write-Host "==> Installing Python dependencies"
& $py.Path -m pip install -r requirements.txt

Write-Host ""
Write-Host "==> Downloading Chromium for Playwright (~150 MB)"
& $py.Path -m playwright install chromium

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Try:  python stealth_clone.py https://example.com/ --out .\out\ --limit 1"
