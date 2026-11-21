$repoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $repoRoot "setup_nhanh.bat") @args
exit $LASTEXITCODE
