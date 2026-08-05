# tuya-df — Windows Installer (PowerShell)
# Usage: irm https://raw.githubusercontent.com/maidang-xing/tuya-df/main/install.ps1 | iex
#Requires -Version 5.1

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Yellow }
function Write-OK($msg)   { Write-Host $msg -ForegroundColor Green }
function Write-Err($msg)  { Write-Host $msg -ForegroundColor Red }

Write-Host ""
Write-Host "tuya-df installer (Windows)" -ForegroundColor White
Write-Host ""

# ---- Detect Python ----
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>$null
        if ($ver -match "Python (3\.\d+)") {
            $pyver = [version]$matches[1]
            if ($pyver -ge [version]"3.9") {
                $python = $cmd
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Step "Python 3.9+ not found. Installing via winget..."
    try {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $python = "python"
    } catch {
        Write-Err "Could not install Python. Please install Python 3.9+ from https://python.org"
        exit 1
    }
}

Write-Host "Python: $(& $python --version)"

# ---- Ensure pip ----
try { & $python -m pip --version 2>$null | Out-Null } catch {
    Write-Step "Installing pip..."
    & $python -m ensurepip --upgrade
}

# ---- Install pipx ----
Write-Step "Installing pipx..."
& $python -m pip install --user pipx 2>$null
& $python -m pipx ensurepath 2>$null

# Refresh PATH
$userScripts = Join-Path $env:APPDATA "Python\Scripts"
if (Test-Path $userScripts) { $env:PATH = "$userScripts;$env:PATH" }

# ---- Install tuya-df ----
Write-Step "Installing tuya-df..."
pipx install "git+https://github.com/maidang-xing/tuya-df.git"
pipx inject tuya-df playwright

# ---- Install Chromium ----
Write-Step "Installing Chromium for browser login..."
$tuyaPython = Join-Path $env:LOCALAPPDATA "pipx\venvs\tuya-df\Scripts\python.exe"
if (Test-Path $tuyaPython) {
    & $tuyaPython -m playwright install chromium
} else {
    & $python -m playwright install chromium
}

# ---- Install Claude Code skill ----
$claudeSkillsDir = Join-Path $env:USERPROFILE ".claude\skills"
if ((Test-Path (Join-Path $env:USERPROFILE ".claude")) -or (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Step "Installing Claude Code skill..."
    New-Item -ItemType Directory -Force -Path $claudeSkillsDir | Out-Null

    $tempDir = Join-Path $env:TEMP "tuya-df-skill"
    if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
    git clone --depth 1 https://github.com/maidang-xing/tuya-df.git $tempDir 2>$null

    $skillSrc = Join-Path $tempDir ".claude\skills\tuya-df"
    if (Test-Path $skillSrc) {
        Copy-Item -Recurse -Force $skillSrc $claudeSkillsDir
        Write-OK "Skill installed to $claudeSkillsDir\tuya-df"
    }
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}

# ---- Verify ----
Write-Host ""
$tuyaCmd = Get-Command tuya-df -ErrorAction SilentlyContinue
if ($tuyaCmd) {
    Write-OK "tuya-df installed successfully!"
    & tuya-df --version
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  tuya-df auth login      # Log in to the forum (opens browser)"
    Write-Host "  tuya-df categories      # See forum categories"
    Write-Host '  tuya-df post create --title "Hello" --body "World" -c show-tell'
} else {
    Write-Step "tuya-df not found in PATH. Open a new terminal window."
    Write-Host "  Or add to PATH: $userScripts"
}
