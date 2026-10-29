param(
    [string]$ExtensionsPath = (Join-Path $env:APPDATA 'pyRevit\Extensions'),
    [string]$Branch = 'main'
)
$ErrorActionPreference = 'Stop'
if (Get-Process Revit -ErrorAction SilentlyContinue) {
    throw 'Close Revit before installing BK BIM Tools.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Install Git for Windows from https://git-scm.com/download/win and reopen PowerShell.'
}
$target = Join-Path $ExtensionsPath 'BKDesigns.extension'
$backup = $null
New-Item -ItemType Directory -Path $ExtensionsPath -Force | Out-Null
$staging = Join-Path ([IO.Path]::GetTempPath()) ('BKBIMTools-' + [Guid]::NewGuid().ToString('N'))
try {
    # Clone first: authentication/network failures leave the existing install intact.
    & git clone --branch $Branch --single-branch 'https://github.com/bktouray/BK-BIM-Tools.git' $staging
    if ($LASTEXITCODE -ne 0) { throw 'Git clone failed. Check your connection and repository access.' }
    if (-not (Test-Path (Join-Path $staging 'startup.py'))) {
        throw 'This branch does not contain the updater yet. Merge the updater pull request first.'
    }
    if (Test-Path $target) {
        $backupDir = Join-Path $env:LOCALAPPDATA 'BKBIMTools\InstallBackups'
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        $backup = Join-Path $backupDir ('BKDesigns-' + [Guid]::NewGuid().ToString('N'))
        Move-Item -LiteralPath $target -Destination $backup
    }
    try {
        Move-Item -LiteralPath $staging -Destination $target
    } catch {
        if ($backup -and -not (Test-Path $target)) {
            Move-Item -LiteralPath $backup -Destination $target
        }
        throw
    }
    Write-Host "Installed BK BIM Tools at $target"
    if ($backup) { Write-Host "Previous installation backed up at $backup" }
    Write-Host 'Start Revit. Future updates: Utilities > Update BK BIM Tools.'
} finally {
    if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
}
