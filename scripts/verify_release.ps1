[CmdletBinding()]
param(
    [switch]$AllowDirty,
    [switch]$BuildPackage
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ExpectedVersion = "2.0.0"
$ExpectedTag = "v2.0.0"
$Python = if (Test-Path -LiteralPath (Join-Path $RepositoryRoot ".venv\Scripts\python.exe")) {
    Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
} else {
    "python"
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Release-readiness command failed: python $($Arguments -join ' ')"
    }
}

$GitRoot = (& git -C $RepositoryRoot rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [System.IO.Path]::GetFullPath($GitRoot) -ne $RepositoryRoot) {
    throw "Run this tracked script from the Omega repository checkout."
}

Push-Location $RepositoryRoot
try {
    $Branch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $Branch -ne "main") {
        throw "Omega release readiness requires branch main."
    }
    $WorkingChanges = @(& git status --porcelain=v1)
    if ($LASTEXITCODE -ne 0) { throw "Git working-tree state could not be read." }
    if ($WorkingChanges.Count -gt 0 -and -not $AllowDirty) {
        throw "The working tree is not clean. Review changes or use -AllowDirty for pre-commit QA."
    }

    Invoke-Python -Arguments @(
        "-m", "omega.distribution.release", "validate-version",
        "--repository-root", ".", "--tag", $ExpectedTag
    )
    $ActualVersion = (& $Python -c "from omega import APP_VERSION; print(APP_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or $ActualVersion -ne $ExpectedVersion) {
        throw "Omega version is not $ExpectedVersion."
    }

    Invoke-Python -Arguments @("-m", "black", "--check", ".")
    Invoke-Python -Arguments @("-m", "ruff", "check", ".")
    Invoke-Python -Arguments @("-m", "mypy", "src")
    Invoke-Python -Arguments @(
        "-m", "pytest", "-p", "no:cacheprovider",
        "tests/release", "tests/ci", "tests/distribution"
    )
    Invoke-Python -Arguments @("-m", "pytest", "-p", "no:cacheprovider")
    Invoke-Python -Arguments @("-m", "omega", "--help")
    Invoke-Python -Arguments @("-m", "omega", "--version")
    Invoke-Python -Arguments @("-m", "omega", "--gui-check")
    Invoke-Python -Arguments @("-m", "omega", "--security-check")
    Invoke-Python -Arguments @("-m", "omega", "--performance-check")

    $Prohibited = @(
        & git ls-files |
            Where-Object {
                $_ -match '(?i)(^|/)(\.env($|\.)|credentials\.json|token\.json|oauth\.json)$' -or
                $_ -match '(?i)\.(db|sqlite|sqlite3|db-wal|db-shm|log|dmp|gguf|onnx|safetensors|exe|msi)$'
            }
    )
    if ($LASTEXITCODE -ne 0) { throw "Tracked-file inventory could not be read." }
    if ($Prohibited.Count -gt 0) {
        throw "Prohibited release files are tracked: $($Prohibited -join ', ')"
    }

    if ($BuildPackage) {
        & (Join-Path $RepositoryRoot "scripts\build_windows.ps1") -Python $Python
        if ($LASTEXITCODE -ne 0) { throw "Optional Windows package build failed." }
    }

    Write-Host "Omega release readiness: PASS"
    Write-Host "Version: $ActualVersion"
    Write-Host "Expected tag: $ExpectedTag"
    Write-Host "Branch: $Branch"
    Write-Host "Working tree accepted for this run: $($WorkingChanges.Count -eq 0 -or $AllowDirty)"
    Write-Host "Package build requested: $BuildPackage"
    Write-Host "No commit, push, tag, release, install, or publication was performed."
}
finally {
    Pop-Location
}
