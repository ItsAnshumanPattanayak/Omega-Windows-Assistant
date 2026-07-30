[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$BuildRoot = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "build\pyinstaller"))
$DistributionRoot = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "dist\Omega"))
$VerificationRoot = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "build\package-verification"))
$ManifestPath = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "dist\Omega-build-manifest.json"))
$ExpectedVersion = "2.0.0"

if (-not $Python) {
    $VirtualPython = if ($env:VIRTUAL_ENV) {
        Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    } else {
        Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
    }
    if (-not (Test-Path -LiteralPath $VirtualPython -PathType Leaf)) {
        throw "Activate the Omega virtual environment or provide -Python explicitly."
    }
    $Python = $VirtualPython
}

function Invoke-CheckedPython {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Python $($Arguments -join ' ')"
    }
}

function Remove-KnownGeneratedDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    $Resolved = [System.IO.Path]::GetFullPath($Path)
    if ($Resolved -notin @($BuildRoot, $DistributionRoot, $VerificationRoot)) {
        throw "Refusing to clean an unapproved generated path: $Resolved"
    }
    if (Test-Path -LiteralPath $Resolved) {
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}

$GitRoot = (& git -C $RepositoryRoot rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [System.IO.Path]::GetFullPath($GitRoot) -ne $RepositoryRoot) {
    throw "This script must run from the Omega repository checkout."
}

Push-Location $RepositoryRoot
try {
    $ActualVersion = (& $Python -c "from omega import APP_VERSION; print(APP_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or $ActualVersion -ne $ExpectedVersion) {
        throw "Omega must report version $ExpectedVersion before packaging."
    }
    Invoke-CheckedPython -Arguments @("-m", "PyInstaller", "--version")
    if (-not $SkipChecks) {
        Invoke-CheckedPython -Arguments @("-m", "black", "--check", ".")
        Invoke-CheckedPython -Arguments @("-m", "ruff", "check", ".")
        Invoke-CheckedPython -Arguments @("-m", "mypy", "src")
        Invoke-CheckedPython -Arguments @("-m", "pytest", "-p", "no:cacheprovider")
    }

    Remove-KnownGeneratedDirectory -Path $BuildRoot
    Remove-KnownGeneratedDirectory -Path $DistributionRoot
    Remove-KnownGeneratedDirectory -Path $VerificationRoot
    Invoke-CheckedPython -Arguments @(
        "-m", "PyInstaller", "--noconfirm", "--clean",
        "--workpath", $BuildRoot,
        "--distpath", (Join-Path $RepositoryRoot "dist"),
        (Join-Path $RepositoryRoot "packaging\omega.spec")
    )
    & (Join-Path $RepositoryRoot "scripts\verify_package.ps1") -Python $Python
    if ($LASTEXITCODE -ne 0) { throw "Package verification failed." }

    if (-not (Test-Path -LiteralPath (Join-Path $DistributionRoot "Omega.exe"))) {
        throw "The expected Omega.exe output is missing."
    }
    $Files = @(Get-ChildItem -LiteralPath $DistributionRoot -Recurse -File)
    $BundleSize = ($Files | Measure-Object -Property Length -Sum).Sum
    $Manifest = [ordered]@{
        product = "Omega Windows Assistant"
        version = $ActualVersion
        bundle_directory = "dist/Omega"
        file_count = $Files.Count
        size_bytes = $BundleSize
        generated_at_utc = [DateTime]::UtcNow.ToString("o")
    }
    $Manifest | ConvertTo-Json | Set-Content -LiteralPath $ManifestPath -Encoding utf8
    Write-Host "Omega application bundle: $DistributionRoot"
    Write-Host "Bundle size (bytes): $BundleSize"
    Write-Host "Build manifest: $ManifestPath"
}
finally {
    Pop-Location
}
