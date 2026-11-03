$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonBin = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonBin)) {
    $pythonBin = 'python'
}
& $pythonBin (Join-Path $projectRoot 'cli/compose.py') stop @args
exit $LASTEXITCODE
