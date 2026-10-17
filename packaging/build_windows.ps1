# Build the Windows one-dir bundle and zip it. Run from anywhere in PowerShell.
param(
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$Venv = ".venv-build"
if (-not (Test-Path $Venv)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $VenvPython -m pip install ".[gui,dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$Version = (& $VenvPython -c "import pcc; print(pcc.__version__)")
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) { throw "could not read pcc.__version__" }
$Version = $Version.Trim()

& $VenvPython -m PyInstaller --noconfirm --clean packaging\pcc.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

if (-not (Test-Path "dist\PrintCostCalculator")) { throw "dist\PrintCostCalculator not found" }

$Out = "packaging\out"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Zip = Join-Path $Out "PrintCostCalculator-$Version-windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path "dist\PrintCostCalculator" -DestinationPath $Zip
Write-Host "Built $Zip"
