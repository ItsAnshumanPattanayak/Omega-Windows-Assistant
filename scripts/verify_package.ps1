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
    $VersionInfo = (Get-Item -LiteralPath $Gui).VersionInfo
    if ($VersionInfo.CompanyName -ne "Anshuman Pattanayak" -or
        $VersionInfo.FileDescription -ne "Omega Windows Assistant" -or
        $VersionInfo.ProductName -ne "Omega Windows Assistant" -or
        $VersionInfo.ProductVersion -ne "2.0.0" -or
        $VersionInfo.OriginalFilename -ne "Omega.exe") {
        throw "Packaged Windows version metadata is incomplete or inconsistent."
    }
    $GuiProcess = Start-Process -FilePath $Gui -ArgumentList "--gui" -WorkingDirectory $Distribution -PassThru
    try {
        if ($GuiProcess.WaitForExit(3000)) {
            if ($GuiProcess.ExitCode -ne 0) {
                throw "The packaged GUI exited with code $($GuiProcess.ExitCode)."
            }
        } else {
            Write-Host "Packaged GUI remained responsive for the bounded launch window."
        }
    }
    finally {
        if (-not $GuiProcess.HasExited) {
            Stop-Process -Id $GuiProcess.Id -Force
            [void]$GuiProcess.WaitForExit(5000)
        }
    }
    Write-Host "Omega package verification passed without installation."
}
finally {
    $env:OMEGA_DATA_DIR = $PreviousDataDirectory
}
