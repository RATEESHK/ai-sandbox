#requires -Version 5.1
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
<#
ai-sandbox bootstrap for PowerShell (Windows PowerShell 5.1 or PowerShell 7 on any OS). No Python required.

    cd C:\path\to\your-project
    powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\install.ps1            # = aisb init
    powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\install.ps1 verify     # any aisb command

-ExecutionPolicy Bypass applies to this process only; nothing on the machine changes.
1. Python 3.8+ present -> run aisb from this checkout (.\aisb\) or a downloaded aisb.pyz.
2. Otherwise download the standalone build for this OS/CPU from GitHub Releases, verify SHA256SUMS,
   unpack into .\.ai-sandbox\bin\aisb-bin\ and run it. Nothing is installed outside this folder.
Override with env vars: AISB_REPO (owner/repo), AISB_VERSION (default latest), AISB_BASE_URL.
#>
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = (Get-Location).Path
$repo = if ($env:AISB_REPO) { $env:AISB_REPO } else { 'RATEESHK/ai-sandbox' }
$ver = if ($env:AISB_VERSION) { $env:AISB_VERSION } else { 'latest' }
$base = if ($env:AISB_BASE_URL) { $env:AISB_BASE_URL } elseif ($ver -eq 'latest') { "https://github.com/$repo/releases/latest/download" } else { "https://github.com/$repo/releases/download/$ver" }
$aisbArgs = if ($args.Count -gt 0) { $args } else { @('init') }
if ($aisbArgs[0] -in @('-h', '--help', 'help')) { Get-Content $MyInvocation.MyCommand.Path -TotalCount 14 | Select-Object -Skip 2; exit 0 }
if (($here -eq $proj) -and (Test-Path (Join-Path $here 'aisb\cli.py')) -and -not (Test-Path (Join-Path $here '.ai-sandbox\policy.json'))) {
  Write-Host "install.ps1: you are inside the ai-sandbox repository itself. Run it from the project you want to sandbox:" -ForegroundColor Yellow
  Write-Host "    cd C:\path\to\your\project; powershell -NoProfile -ExecutionPolicy Bypass -File $here\install.ps1"
  exit 1
}

function Test-Py([string]$exe, [string[]]$pre) {
  try { & $exe @pre -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}
function Find-Python {
  $cands = @(
    @{ exe = (Join-Path $proj '.venv\Scripts\python.exe'); pre = @() }, @{ exe = (Join-Path $proj '.venv\bin\python'); pre = @() },
    @{ exe = (Join-Path $proj '.ai-sandbox\runtime\python\python.exe'); pre = @() }, @{ exe = (Join-Path $proj '.ai-sandbox\runtime\python\bin\python3'); pre = @() },
    @{ exe = 'py'; pre = @('-3') }, @{ exe = 'python3'; pre = @() }, @{ exe = 'python'; pre = @() })
  foreach ($c in $cands) {
    $isPath = ($c.exe -like '*\*') -or ($c.exe -like '*/*')
    if ($isPath -and -not (Test-Path $c.exe)) { continue }
    if (-not $isPath -and -not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    if (Test-Py $c.exe $c.pre) { return $c }
  }
  return $null
}
function Get-File([string]$url, [string]$dest) {
  try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest
}
function Test-Sum([string]$file, [string]$name, [string]$sums) {
  $line = Get-Content $sums | Where-Object { $_ -match "\s$([regex]::Escape($name))$" } | Select-Object -First 1
  if (-not $line) { throw "$name is not listed in SHA256SUMS - refusing" }
  $want = ($line -split '\s+')[0].ToLower()
  $got = (Get-FileHash -Algorithm SHA256 -Path $file).Hash.ToLower()
  if ($want -ne $got) { throw "SHA256 mismatch for $name (expected $want, got $got) - refusing" }
}

$py = Find-Python
if ($py) {
  if (Test-Path (Join-Path $here 'aisb\cli.py')) { $env:PYTHONPATH = "$here;$env:PYTHONPATH"; & $py.exe @($py.pre) -m aisb @aisbArgs; exit $LASTEXITCODE }
  $pyz = Join-Path $proj '.ai-sandbox\bin\aisb.pyz'
  if (-not (Test-Path $pyz)) { $pyz = Join-Path $here 'aisb.pyz' }
  if (Test-Path $pyz) { & $py.exe @($py.pre) $pyz @aisbArgs; exit $LASTEXITCODE }
  $tmp = Join-Path $proj '.ai-sandbox-bootstrap'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  try {
    Write-Host "install.ps1: downloading aisb.pyz from $base ..."
    Get-File "$base/SHA256SUMS" (Join-Path $tmp 'SHA256SUMS'); Get-File "$base/aisb.pyz" (Join-Path $tmp 'aisb.pyz')
    Test-Sum (Join-Path $tmp 'aisb.pyz') 'aisb.pyz' (Join-Path $tmp 'SHA256SUMS')
    & $py.exe @($py.pre) (Join-Path $tmp 'aisb.pyz') @aisbArgs; $rc = $LASTEXITCODE
  } finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
  exit $rc
}

# ---- no Python: standalone build
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { 'arm64' } else { 'x64' }
$os = 'windows'; $ext = 'zip'
if ($PSVersionTable.PSVersion.Major -ge 6) {
  if ($IsMacOS) { $os = 'macos'; $ext = 'tar.gz'; $arch = if ((uname -m) -match 'arm64|aarch64') { 'arm64' } else { 'x64' } }
  elseif ($IsLinux) { $os = 'linux'; $ext = 'tar.gz'; $arch = if ((uname -m) -match 'arm64|aarch64') { 'arm64' } else { 'x64' } }
}
$asset = "aisb-$os-$arch.$ext"
$dest = Join-Path $proj '.ai-sandbox\bin\aisb-bin'
$exe = Join-Path $dest $(if ($os -eq 'windows') { 'aisb.exe' } else { 'aisb' })
if (Test-Path $exe) { & $exe @aisbArgs; exit $LASTEXITCODE }
Write-Host "install.ps1: no Python 3.8+ found; downloading the standalone build $asset from $base ..."
$tmp = Join-Path $proj '.ai-sandbox-bootstrap'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
  Get-File "$base/SHA256SUMS" (Join-Path $tmp 'SHA256SUMS'); Get-File "$base/$asset" (Join-Path $tmp $asset)
  Test-Sum (Join-Path $tmp $asset) $asset (Join-Path $tmp 'SHA256SUMS')
  $un = Join-Path $tmp 'unpacked'; New-Item -ItemType Directory -Force -Path $un | Out-Null
  if ($ext -eq 'zip') { Expand-Archive -LiteralPath (Join-Path $tmp $asset) -DestinationPath $un -Force } else { tar -xzf (Join-Path $tmp $asset) -C $un }
  $src = if (Test-Path (Join-Path $un 'aisb-bin')) { Join-Path $un 'aisb-bin' } else { $un }
  if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
  Move-Item -LiteralPath $src -Destination $dest
} finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
if (-not (Test-Path $exe)) { Write-Error "install.ps1: $exe not found after extraction"; exit 1 }
if ($os -ne 'windows') { chmod +x $exe }
Write-Host "install.ps1: standalone aisb ready at $dest (project-local; delete the folder to remove it)"
& $exe @aisbArgs
exit $LASTEXITCODE
