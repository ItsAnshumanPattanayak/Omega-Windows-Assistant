[CmdletBinding()]
param([string]$Python = "", [switch]$SkipChecks)

& (Join-Path $PSScriptRoot "build_windows_app.ps1") -Python $Python -SkipChecks:$SkipChecks
exit $LASTEXITCODE
