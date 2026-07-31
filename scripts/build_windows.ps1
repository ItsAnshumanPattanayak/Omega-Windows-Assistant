[CmdletBinding()]
param([string]$Python = "", [switch]$SkipChecks)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$SpecPath = [System.IO.Path]::GetFullPath(
    (Join-Path $RepositoryRoot "packaging\omega.spec")
)
$EntryPointPath = [System.IO.Path]::GetFullPath(
    (Join-Path $RepositoryRoot "packaging\entrypoint.py")
)
$WorkPath = [System.IO.Path]::GetFullPath(
    (Join-Path $RepositoryRoot "build\pyinstaller")
)
$DistPath = [System.IO.Path]::GetFullPath(
    (Join-Path $RepositoryRoot "dist")
)
$BuildScript = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "build_windows_app.ps1")
)

if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
    throw "The PyInstaller spec file is missing: $SpecPath"
}
if (-not (Test-Path -LiteralPath $EntryPointPath -PathType Leaf)) {
    throw "The PyInstaller entrypoint is missing: $EntryPointPath"
}
if (-not (Test-Path -LiteralPath $BuildScript -PathType Leaf)) {
    throw "The Windows application build script is missing: $BuildScript"
}

Write-Host "Repository root: $RepositoryRoot"
Write-Host "PyInstaller spec: $SpecPath"
Write-Host "PyInstaller entrypoint: $EntryPointPath"
Write-Host "PyInstaller work path: $WorkPath"
Write-Host "PyInstaller dist path: $DistPath"

Push-Location $RepositoryRoot
try {
    & $BuildScript -Python $Python -SkipChecks:$SkipChecks
    if ($LASTEXITCODE -ne 0) {
        throw "The Windows application build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
