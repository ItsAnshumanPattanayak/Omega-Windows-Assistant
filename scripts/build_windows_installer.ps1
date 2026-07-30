[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$InnoCompiler = "",
    [switch]$SkipChecks,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)

$ExpectedVersion = "2.0.0"

$Bundle = Join-Path $RepositoryRoot "dist\Omega"
$InstallerScript = Join-Path $RepositoryRoot "installer\omega.iss"
$InstallerDirectory = Join-Path $RepositoryRoot "dist\installer"

$InstallerName = "Omega-Windows-Assistant-Setup-v$ExpectedVersion.exe"
$InstallerPath = Join-Path $InstallerDirectory $InstallerName
$ChecksumPath = "$InstallerPath.sha256"
$ManifestPath = Join-Path $InstallerDirectory "installer-manifest.json"

# ----------------------------------------------------------------------
# Resolve Python
# ----------------------------------------------------------------------

if (-not $Python) {
    $VirtualPython = if ($env:VIRTUAL_ENV) {
        Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    }
    else {
        Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
    }

    if (-not (Test-Path -LiteralPath $VirtualPython -PathType Leaf)) {
        throw (
            "Activate the Omega virtual environment or provide " +
            "-Python explicitly."
        )
    }

    $Python = $VirtualPython
}

Write-Host "Using Python:"
Write-Host "  $Python"

# ----------------------------------------------------------------------
# Validate repository
# ----------------------------------------------------------------------

$GitRoot = (
    & git -C $RepositoryRoot rev-parse --show-toplevel
).Trim()

if (
    $LASTEXITCODE -ne 0 -or
    [System.IO.Path]::GetFullPath($GitRoot) -ne $RepositoryRoot
) {
    throw "This script must run from the Omega repository checkout."
}

$Branch = (
    & git -C $RepositoryRoot branch --show-current
).Trim()

if ($LASTEXITCODE -ne 0 -or $Branch -ne "main") {
    throw "Installer builds require branch main."
}

$Changes = @(
    & git -C $RepositoryRoot status --porcelain=v1
)

if ($LASTEXITCODE -ne 0) {
    throw "Git working-tree state could not be read."
}

if ($Changes.Count -gt 0 -and -not $AllowDirty) {
    throw (
        "Review or commit working-tree changes before an installer build. " +
        "Use -AllowDirty only after reviewing the changes."
    )
}

# ----------------------------------------------------------------------
# Validate Omega version and PyInstaller
# ----------------------------------------------------------------------

$ActualVersion = (
    & $Python -c "from omega import APP_VERSION; print(APP_VERSION)"
).Trim()

if (
    $LASTEXITCODE -ne 0 -or
    $ActualVersion -ne $ExpectedVersion
) {
    throw (
        "Omega must report version $ExpectedVersion before installer " +
        "compilation. Current value: $ActualVersion"
    )
}

Write-Host "Omega version:"
Write-Host "  $ActualVersion"

& $Python -m PyInstaller --version

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is unavailable."
}

# ----------------------------------------------------------------------
# Resolve Inno Setup compiler
# ----------------------------------------------------------------------

$Compiler = $InnoCompiler

if ($Compiler) {
    $Compiler = [Environment]::ExpandEnvironmentVariables($Compiler)

    if (
        -not (
            Test-Path -LiteralPath $Compiler -PathType Leaf
        )
    ) {
        throw (
            "The Inno Setup compiler provided through -InnoCompiler " +
            "does not exist: $Compiler"
        )
    }
}
else {
    $Candidates = @()

    if ($env:ProgramFiles) {
        $Candidates += Join-Path `
            $env:ProgramFiles `
            "Inno Setup 7\ISCC.exe"
    }

    if (${env:ProgramFiles(x86)}) {
        $Candidates += Join-Path `
            ${env:ProgramFiles(x86)} `
            "Inno Setup 7\ISCC.exe"
    }

    if ($env:ProgramFiles) {
        $Candidates += Join-Path `
            $env:ProgramFiles `
            "Inno Setup 6\ISCC.exe"
    }

    if (${env:ProgramFiles(x86)}) {
        $Candidates += Join-Path `
            ${env:ProgramFiles(x86)} `
            "Inno Setup 6\ISCC.exe"
    }

    $Compiler = $Candidates |
        Where-Object {
            $_ -and (
                Test-Path -LiteralPath $_ -PathType Leaf
            )
        } |
        Select-Object -First 1

    if (-not $Compiler) {
        $Command = Get-Command ISCC.exe -ErrorAction SilentlyContinue

        if ($Command) {
            $Compiler = $Command.Source
        }
    }
}

if (
    -not $Compiler -or
    -not (
        Test-Path -LiteralPath $Compiler -PathType Leaf
    )
) {
    $CheckedPaths = if ($Candidates) {
        $Candidates -join [Environment]::NewLine
    }
    else {
        "No default Inno Setup paths were available."
    }

    throw @"
Inno Setup compiler ISCC.exe was not found.

Checked locations:
$CheckedPaths

Install Inno Setup 7 or Inno Setup 6 and rerun this script.

You can also provide the compiler explicitly:

    -InnoCompiler "C:\Program Files\Inno Setup 7\ISCC.exe"
"@
}

Write-Host "Using Inno Setup compiler:"
Write-Host "  $Compiler"

# ----------------------------------------------------------------------
# Validate installer source
# ----------------------------------------------------------------------

if (
    -not (
        Test-Path -LiteralPath $InstallerScript -PathType Leaf
    )
) {
    throw "The Inno Setup script is missing: $InstallerScript"
}

# ----------------------------------------------------------------------
# Build the PyInstaller application bundle
# ----------------------------------------------------------------------

$BuildApplicationScript = Join-Path `
    $RepositoryRoot `
    "scripts\build_windows_app.ps1"

if (
    -not (
        Test-Path -LiteralPath $BuildApplicationScript -PathType Leaf
    )
) {
    throw (
        "The Windows application build script is missing: " +
        $BuildApplicationScript
    )
}

Write-Host ""
Write-Host "Building Omega application bundle..."

& $BuildApplicationScript `
    -Python $Python `
    -SkipChecks:$SkipChecks

if (
    $LASTEXITCODE -ne 0 -or
    -not (
        Test-Path -LiteralPath $Bundle -PathType Container
    )
) {
    throw "The verified Omega application bundle was not created."
}

$OmegaExecutable = Join-Path $Bundle "Omega.exe"

if (
    -not (
        Test-Path -LiteralPath $OmegaExecutable -PathType Leaf
    )
) {
    throw "The packaged Omega executable is missing: $OmegaExecutable"
}

Write-Host "Application bundle created:"
Write-Host "  $Bundle"

# ----------------------------------------------------------------------
# Compile the Inno Setup installer
# ----------------------------------------------------------------------

New-Item `
    -ItemType Directory `
    -Path $InstallerDirectory `
    -Force |
    Out-Null

Write-Host ""
Write-Host "Compiling Omega installer..."

& $Compiler `
    "/DMyAppVersion=$ActualVersion" `
    $InstallerScript

if ($LASTEXITCODE -ne 0) {
    throw (
        "Inno Setup compilation failed with exit code " +
        "$LASTEXITCODE."
    )
}

if (
    -not (
        Test-Path -LiteralPath $InstallerPath -PathType Leaf
    )
) {
    throw "The expected installer output is missing: $InstallerPath"
}

# ----------------------------------------------------------------------
# Generate checksum and artifact manifest
# ----------------------------------------------------------------------

$InstallerFile = Get-Item -LiteralPath $InstallerPath
$InstallerSize = $InstallerFile.Length

$Hash = (
    Get-FileHash `
        -LiteralPath $InstallerPath `
        -Algorithm SHA256
).Hash.ToLowerInvariant()

"$Hash  $InstallerName" |
    Set-Content `
        -LiteralPath $ChecksumPath `
        -Encoding ascii

$Manifest = [ordered]@{
    product = "Omega Windows Assistant"
    version = $ActualVersion
    publisher = "Anshuman Pattanayak"
    installer = $InstallerName
    installer_path = $InstallerPath
    size_bytes = $InstallerSize
    sha256 = $Hash
    signed = $false
    inno_compiler = $Compiler
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
}

$Manifest |
    ConvertTo-Json |
    Set-Content `
        -LiteralPath $ManifestPath `
        -Encoding utf8

# ----------------------------------------------------------------------
# Final output
# ----------------------------------------------------------------------

Write-Host ""
Write-Host "Omega installer build completed successfully."
Write-Host ""
Write-Host "Installer:"
Write-Host "  $InstallerPath"
Write-Host ""
Write-Host "Installer size:"
Write-Host "  $InstallerSize bytes"
Write-Host ""
Write-Host "SHA-256:"
Write-Host "  $Hash"
Write-Host ""
Write-Host "Checksum file:"
Write-Host "  $ChecksumPath"
Write-Host ""
Write-Host "Artifact manifest:"
Write-Host "  $ManifestPath"