[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$InnoCompiler = "",
    [switch]$SkipChecks,
    [switch]$AllowDirty
)

& (Join-Path $PSScriptRoot "build_windows_installer.ps1") `
    -Python $Python `
    -InnoCompiler $InnoCompiler `
    -SkipChecks:$SkipChecks `
    -AllowDirty:$AllowDirty
exit $LASTEXITCODE
