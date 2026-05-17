$ErrorActionPreference = "Stop"

$versionUrl = "http://127.0.0.1:50021/version"
try {
    $version = Invoke-RestMethod -Uri $versionUrl -TimeoutSec 2
    Write-Host "VOICEVOX already running: $version"
    exit 0
} catch {
}

$candidates = @()
$wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
if (Test-Path $wingetRoot) {
    $candidates += Get-ChildItem -Path $wingetRoot -Recurse -Filter VOICEVOX.exe -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName
}

if (-not $candidates) {
    Write-Error "VOICEVOX.exe was not found. Install VOICEVOX CPU with winget first."
}

$exe = $candidates[0]
Start-Process -FilePath $exe -WindowStyle Hidden

for ($i = 0; $i -lt 60; $i++) {
    try {
        $version = Invoke-RestMethod -Uri $versionUrl -TimeoutSec 2
        Write-Host "VOICEVOX ready: $version"
        exit 0
    } catch {
        Start-Sleep -Seconds 2
    }
}

Write-Error "VOICEVOX did not become ready on $versionUrl"
