[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ExpectedBuild = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "build\pyinstaller"))
$ExpectedDistribution = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "dist\Omega"))

function Invoke-Checked {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Python $($Arguments -join ' ')"
    }
}

function Remove-KnownBuildDirectory {
    param([string]$Path)
    $Resolved = [System.IO.Path]::GetFullPath($Path)
    if ($Resolved -notin @($ExpectedBuild, $ExpectedDistribution)) {
        throw "Refusing to clean an unapproved path: $Resolved"
    }
    if (Test-Path -LiteralPath $Resolved) {
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}

$GitRoot = (& git -C $RepositoryRoot rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [System.IO.Path]::GetFullPath($GitRoot) -ne $RepositoryRoot) {
    throw "Run this script from the Omega repository checkout."
}

Push-Location $RepositoryRoot
try {
    $PythonVersion = (& $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "The selected Python interpreter is unavailable."
    }
    $VersionParts = $PythonVersion.Split(".")
    $Major = [int]$VersionParts[0]
    $Minor = [int]$VersionParts[1]
    if ($Major -ne 3 -or $Minor -lt 11 -or $Minor -gt 14) {
        throw "Omega Windows builds require supported CPython 3.11 through 3.14; found $PythonVersion."
    }

    Invoke-Checked -Arguments @("-m", "PyInstaller", "--version")
    if (-not $SkipChecks) {
        Invoke-Checked -Arguments @("-m", "black", "--check", ".")
        Invoke-Checked -Arguments @("-m", "ruff", "check", ".")
        Invoke-Checked -Arguments @("-m", "mypy", "src")
        Invoke-Checked -Arguments @("-m", "pytest", "-p", "no:cacheprovider")
    }

    Remove-KnownBuildDirectory -Path $ExpectedBuild
    Remove-KnownBuildDirectory -Path $ExpectedDistribution
    Invoke-Checked -Arguments @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath", $ExpectedBuild,
        "--distpath", (Join-Path $RepositoryRoot "dist"),
        (Join-Path $RepositoryRoot "packaging\omega.spec")
    )
    & (Join-Path $RepositoryRoot "scripts\verify_package.ps1") -Python $Python
    if ($LASTEXITCODE -ne 0) {
        throw "Package verification failed."
    }
    Write-Host "Omega one-folder bundle created at $ExpectedDistribution"
}
finally {
    Pop-Location
}
