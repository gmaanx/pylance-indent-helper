# PowerShell 0.2-Second Instant Setup (No USB Required, No Hang)
$ErrorActionPreference = "Continue"
$RootDir = Split-Path -Parent $PSScriptRoot
$VenvPy = Join-Path (Split-Path -Parent $RootDir) ".venv\Scripts\python.exe"

if (Test-Path $VenvPy) {
    & $VenvPy (Join-Path $RootDir "setup.py")
} else {
    python (Join-Path $RootDir "setup.py")
}
