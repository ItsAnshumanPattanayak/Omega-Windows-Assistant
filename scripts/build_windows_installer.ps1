[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$InnoCompiler = "",
    [switch]$SkipChecks,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ExpectedVersion = "2.0.0"
$Bundle = Join-Path $RepositoryRoot "dist\Omega"
$InstallerScript = Join-Path $RepositoryRoot "installer\omega.iss"
$InstallerDirectory = Join-Path $RepositoryRoot "dist\installer"
$InstallerName = "Omega-Windows-Assistant-Setup-v$ExpectedVersion.exe"
$InstallerPath = Join-Path $InstallerDirectory $InstallerName
$ChecksumPath = "$InstallerPath.sha256"
$ManifestPath = Join-Path $InstallerDirectory "installer-manifest.json"

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

$GitRoot = (& git -C $RepositoryRoot rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [System.IO.Path]::GetFullPath($GitRoot) -ne $RepositoryRoot) {
    throw "This script must run from the Omega repository checkout."
}
$Branch = (& git -C $RepositoryRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $Branch -ne "main") {
    throw "Installer builds require branch main."
}
$Changes = @(& git -C $RepositoryRoot status --porcelain=v1)
if ($LASTEXITCODE -ne 0) { throw "Git working-tree state could not be read." }
if ($Changes.Count -gt 0 -and -not $AllowDirty) {
    throw "Review or commit working-tree changes before an installer build."
}

$ActualVersion = (& $Python -c "from omega import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $ActualVersion -ne $ExpectedVersion) {
    throw "Omega must report version $ExpectedVersion before installer compilation."
}
& $Python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) { throw "PyInstaller is unavailable." }

$Compiler = $InnoCompiler
if (-not $Compiler) {
    $Candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $Compiler = $Candidates | Where-Object {
        $_ -and (Test-Path -LiteralPath $_ -PathType Leaf)
    } | Select-Object -First 1
    if (-not $Compiler) {
        $Command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($Command) { $Compiler = $Command.Source }
    }
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
    throw "Inno Setup 6 compiler was not found. Install it manually from https://jrsoftware.org/isdl.php and rerun this script."
}

& (Join-Path $RepositoryRoot "scripts\build_windows_app.ps1") -Python $Python -SkipChecks:$SkipChecks
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Bundle -PathType Container)) {
    throw "The verified Omega application bundle was not created."
}

New-Item -ItemType Directory -Path $InstallerDirectory -Force | Out-Null
& $Compiler "/DMyAppVersion=$ActualVersion" $InstallerScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
    throw "The expected installer output is missing: $InstallerPath"
}

$InstallerSize = (Get-Item -LiteralPath $InstallerPath).Length
$Hash = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $InstallerName" | Set-Content -LiteralPath $ChecksumPath -Encoding ascii
$Manifest = [ordered]@{
    product = "Omega Windows Assistant"
    version = $ActualVersion
    publisher = "Anshuman Pattanayak"
    installer = $InstallerName
    size_bytes = $InstallerSize
    sha256 = $Hash
    signed = $false
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
}
$Manifest | ConvertTo-Json | Set-Content -LiteralPath $ManifestPath -Encoding utf8
Write-Host "Omega installer: $InstallerPath"
Write-Host "Installer size (bytes): $InstallerSize"
Write-Host "SHA-256: $Hash"
Write-Host "Checksum file: $ChecksumPath"
Write-Host "Artifact manifest: $ManifestPath"
