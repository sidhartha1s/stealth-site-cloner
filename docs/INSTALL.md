# Installation

`stealth-site-cloner` runs anywhere Python 3.10+ runs. The only platform difference is how you install Python and how you launch PowerShell vs. bash. There is **no WSL, Docker, or virtualisation requirement** — Windows users run the script natively.

---

## What gets installed

| | Where | Size |
|---|---|---|
| Python packages (`requests`, `playwright`, `playwright-stealth`) | Your Python's site-packages | ~30 MB |
| Chromium binary used by Playwright | `~/.cache/ms-playwright/` (Linux) <br> `~/Library/Caches/ms-playwright/` (macOS) <br> `%USERPROFILE%\AppData\Local\ms-playwright\` (Windows) | ~150 MB |

Nothing else is touched. The Chromium build is self-contained and never replaces your system browser.

---

## Linux (Ubuntu / Debian / similar)

```bash
# 1. System packages
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# 2. Clone
git clone https://github.com/sidhartha1s/stealth-site-cloner.git
cd stealth-site-cloner

# 3. Recommended: virtualenv so deps don't pollute system Python
python3 -m venv .venv
source .venv/bin/activate

# 4. One-shot install
bash scripts/install.sh
```

`install.sh` does:

1. Verifies Python ≥ 3.10
2. `pip install -r requirements.txt`
3. `python3 -m playwright install chromium`
4. `python3 -m playwright install-deps chromium` (best-effort — needs sudo)

If step 4 prints a permission warning, run it manually once:

```bash
sudo $(which python3) -m playwright install-deps chromium
```

That installs the shared libraries Chromium needs (libnss3, libatk1.0, fonts, etc.). On a desktop Ubuntu install most are already present.

---

## macOS

```bash
# Homebrew is the easiest way to get Python and Git.
# Install Homebrew first if you don't have it: https://brew.sh
brew install python git

git clone https://github.com/sidhartha1s/stealth-site-cloner.git
cd stealth-site-cloner

python3 -m venv .venv
source .venv/bin/activate

bash scripts/install.sh
```

No system-package step is needed on macOS — Chromium ships self-contained.

---

## Windows 10 / 11 (native)

> No WSL, no Ubuntu, no Docker. This is plain Windows + plain Python.

### 1. Install Python

1. Go to https://python.org/downloads/windows/.
2. Download the latest **Python 3.x** Windows installer (64-bit).
3. Run the installer.
4. **Check "Add python.exe to PATH"** at the bottom of the first screen.
5. Click "Install Now".

Verify in a new PowerShell window:

```powershell
python --version
```

Should print `Python 3.12.x` or similar.

### 2. Install Git

1. Go to https://git-scm.com/download/win.
2. Download and run the installer. Default options are fine.

Verify:

```powershell
git --version
```

### 3. Clone and install

Open PowerShell in the directory where you want the repo:

```powershell
git clone https://github.com/sidhartha1s/stealth-site-cloner.git
cd stealth-site-cloner

# Recommended: virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Run the installer
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

`install.ps1` does:

1. Locates `python` (or `python3`) on PATH
2. Verifies Python ≥ 3.10
3. `pip install -r requirements.txt`
4. `python -m playwright install chromium`

### Windows troubleshooting

| Symptom | Fix |
|---|---|
| `python` not recognised in PowerShell | Re-run the Python installer with the "Add to PATH" box ticked. Or use the full path printed by `where.exe python`. |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | Run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Accept the prompt. |
| `playwright install chromium` fails with a long-path error | Open an **admin** PowerShell once and run: `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`. Then retry. |
| Antivirus quarantines the Chromium binary | Whitelist `%USERPROFILE%\AppData\Local\ms-playwright\` in your AV. |
| Corporate network blocks the Chromium download | Set `HTTPS_PROXY` before running the installer: `$env:HTTPS_PROXY = "http://proxy.example.com:8080"`. |

---

## Verify your install (any OS)

```bash
python stealth_clone.py https://example.com/ --out ./_test/ --limit 1
```

Expected output:

```
Fetching sitemap: https://example.com/sitemap.xml
  ⚠ Could not fetch ...   ← example.com has no sitemap; that's fine
No URLs found in sitemap — falling back to homepage only.
  ✓ https://example.com/

Done — 1/1 pages saved to ./_test/
```

And `_test/index.html` exists.

---

## Updating

```bash
git pull
pip install -r requirements.txt --upgrade
python -m playwright install chromium
```

---

## Uninstalling

Delete the repo folder. To also remove the Chromium cache:

```bash
# Linux
rm -rf ~/.cache/ms-playwright/

# macOS
rm -rf ~/Library/Caches/ms-playwright/

# Windows PowerShell
Remove-Item -Recurse "$env:LOCALAPPDATA\ms-playwright"
```

If you used a virtualenv, delete `.venv/` too.
