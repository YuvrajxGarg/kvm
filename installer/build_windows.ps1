# Builds the Windows setup wizard from the PyInstaller folder in dist\Kvm:
#   pwsh installer\build_windows.ps1 -App Kvm -Version 1.2.3 -Url https://kvm.pxlvzn.in
# Writes dist\Kvm-Setup.exe and dist\Kvm-Setup.exe.sha256. Installs Inno Setup with Chocolatey
# if the machine doesn't have it.
param(
  [string]$App = "Kvm",
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$Url = "https://kvm.pxlvzn.in"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  choco install innosetup -y --no-progress | Out-Host
  $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
}

if (-not (Test-Path "$root\dist\$App\$App.exe")) { throw "dist\$App\$App.exe not found: build the app first" }
$num = ($Version.TrimStart('v') -replace '[^0-9.].*$', '')
& $iscc /Qp "/DAppName=$App" "/DAppVersion=$num" "/DAppURL=$Url" "$PSScriptRoot\windows.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC failed ($LASTEXITCODE)" }

$setup = "$root\dist\$App-Setup.exe"
$h = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
"$h  $App-Setup.exe" | Out-File -Encoding ascii -NoNewline "$setup.sha256"
Get-Content "$setup.sha256"
