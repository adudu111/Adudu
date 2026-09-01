# Build CyberGlossary into a standalone onedir executable.
# Usage:  .\scripts\build.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venv
}

Write-Host "Installing dependencies..."
& $python -m pip install --upgrade pip | Out-Null
& $python -m pip install -e "$root[dev,build]"

Write-Host "Cleaning stale build output..."
foreach ($dir in @("dist", "build")) {
    $target = Join-Path $root $dir
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
}

Write-Host "Running tests..."
& $python -m pytest (Join-Path $root "tests")

Write-Host "Running ruff..."
& $python -m ruff check (Join-Path $root "src") (Join-Path $root "tests")

Write-Host "Building executable..."
& $python -m PyInstaller --noconfirm (Join-Path $root "packaging\CyberGlossary.spec")

$exe = Join-Path $root "dist\adudu\adudu.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: expected executable not found at $exe"
}

Write-Host ""
Write-Host "Build complete: $exe"
