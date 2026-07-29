[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$InnoCompiler = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Bundle = Join-Path $RepositoryRoot "dist\Omega"
$InstallerScript = Join-Path $RepositoryRoot "installer\omega.iss"

$GitRoot = (& git -C $RepositoryRoot rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [System.IO.Path]::GetFullPath($GitRoot) -ne $RepositoryRoot) {
    throw "Run this script from the Omega repository checkout."
}
if (-not (Test-Path -LiteralPath $Bundle -PathType Container)) {
    throw "Build and verify the Omega one-folder bundle before the installer."
}

$Compiler = $InnoCompiler
if (-not $Compiler) {
    $Command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($Command) {
        $Compiler = $Command.Source
    } else {
        $Candidates = @(
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        )
        $Compiler = $Candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
    }
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
    throw "Inno Setup 6 compiler was not found; no installer was built."
}

$Version = (& $Python -c "from omega import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Omega version metadata is invalid."
}

& (Join-Path $RepositoryRoot "scripts\verify_package.ps1") -Python $Python
if ($LASTEXITCODE -ne 0) {
    throw "Package verification failed before installer compilation."
}
& $Compiler "/DMyAppVersion=$Version" $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}
Write-Host "Omega installer created under installer\output."
