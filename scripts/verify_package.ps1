[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$DistributionDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Distribution = if ($DistributionDirectory) {
    [System.IO.Path]::GetFullPath($DistributionDirectory)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "dist\Omega"))
}
$AllowedDistribution = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "dist\Omega"))
$VerificationRoot = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "build\package-verification"))

if ($Distribution -ne $AllowedDistribution) {
    throw "Verification accepts only the reviewed Omega distribution directory."
}
if (-not (Test-Path -LiteralPath $Distribution -PathType Container)) {
    throw "The Omega distribution does not exist: $Distribution"
}
if (Test-Path -LiteralPath $VerificationRoot) {
    Remove-Item -LiteralPath $VerificationRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $VerificationRoot | Out-Null

$Cli = Join-Path $Distribution "OmegaCLI.exe"
$Gui = Join-Path $Distribution "Omega.exe"
if (-not (Test-Path -LiteralPath $Cli -PathType Leaf) -or -not (Test-Path -LiteralPath $Gui -PathType Leaf)) {
    throw "The expected CLI and GUI executables are missing."
}

$PreviousDataDirectory = $env:OMEGA_DATA_DIR
$env:OMEGA_DATA_DIR = Join-Path $VerificationRoot "runtime"
try {
    & $Python -m omega.distribution $Distribution
    if ($LASTEXITCODE -ne 0) { throw "Distribution manifest verification failed." }
    & $Cli --version
    if ($LASTEXITCODE -ne 0) { throw "Packaged --version failed." }
    & $Cli --help
    if ($LASTEXITCODE -ne 0) { throw "Packaged --help failed." }
    & $Cli --gui-check
    if ($LASTEXITCODE -ne 0) { throw "Packaged --gui-check failed." }
    "Shut down Omega" | & $Cli
    if ($LASTEXITCODE -ne 0) { throw "Packaged first-run startup failed." }
    if (-not (Test-Path -LiteralPath (Join-Path $env:OMEGA_DATA_DIR "database\omega.db"))) {
        throw "Packaged database was not created in the isolated user-data directory."
    }
    Write-Host "Omega package verification passed without installation."
}
finally {
    $env:OMEGA_DATA_DIR = $PreviousDataDirectory
}
