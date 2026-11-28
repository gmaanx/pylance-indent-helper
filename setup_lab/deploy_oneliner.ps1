$repoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $repoRoot "setup.bat") @args
exit $LASTEXITCODE
