# Installs dist\Kvm-Setup.exe silently (CI runners are administrators), checks the app, the
# service and its control endpoint, smoke-tests the installed app, then uninstalls and checks
# everything is gone. CI only.
#   pwsh installer\test_windows.ps1 [-Smoke "python tests/smoke_app.py"]
param([string]$App = "Kvm", [string]$Smoke = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dir = "$env:ProgramFiles\$App"
$exe = "$dir\$App.exe"
$key = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PXLVZN.${App}_is1"

Write-Host "== install"
$p = Start-Process "$root\dist\$App-Setup.exe" -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$env:TEMP\$App-setup.log" -Wait -PassThru
if ($p.ExitCode -ne 0) { Get-Content "$env:TEMP\$App-setup.log" | Out-Host; throw "setup exited with $($p.ExitCode)" }
if (-not (Test-Path $exe)) { throw "$exe missing after install" }
$reg = Get-ItemProperty $key
Write-Host "registered: $($reg.DisplayName) $($reg.DisplayVersion) at $($reg.InstallLocation)"

Write-Host "== service"
$svc = $null
for ($i = 0; $i -lt 30; $i++) { $svc = Get-Service -Name $App -ErrorAction SilentlyContinue; if ($svc -and $svc.Status -eq 'Running') { break }; Start-Sleep 1 }
if (-not $svc) { throw "the Kvm service isn't registered" }
Write-Host "service: $($svc.Status), $((Get-CimInstance Win32_Service -Filter "Name='$App'").PathName)"
if ($svc.Status -ne 'Running') {
  Write-Host "-- service.log"; Get-Content "$env:ProgramData\PXLVZN\Kvm\service.log" -ErrorAction SilentlyContinue | Out-Host
  Write-Host "-- events"
  Get-WinEvent -FilterHashtable @{LogName = 'System'; ProviderName = 'Service Control Manager'; StartTime = (Get-Date).AddMinutes(-10)} -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match 'Kvm' } | Select-Object -First 10 | Format-List TimeCreated, Id, Message | Out-Host
  Get-WinEvent -FilterHashtable @{LogName = 'Application'; StartTime = (Get-Date).AddMinutes(-10)} -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match 'Kvm|Python|pywin' } | Select-Object -First 10 | Format-List TimeCreated, ProviderName, Message | Out-Host
  Write-Host "-- setup log"; Get-Content "$env:TEMP\$App-setup.log" -Tail 40 -ErrorAction SilentlyContinue | Out-Host
  throw "the Kvm service didn't start"
}
if ((Get-CimInstance Win32_Service -Filter "Name='$App'").StartName -ne 'LocalSystem') { throw "the service must run as LocalSystem" }

Write-Host "== the service answers the window"
$ok = $false
for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
  Start-Process $exe -ArgumentList "status", "--out", "$env:TEMP\kvm-status.txt" -Wait
  $out = Get-Content "$env:TEMP\kvm-status.txt" -Raw -ErrorAction SilentlyContinue
  if ($out -match '"me"') { $ok = $true } else { Start-Sleep 1 }
}
Get-Content "$env:TEMP\kvm-status.txt" | Select-Object -First 30 | Out-Host
if (-not $ok) {
  Write-Host "-- service: $((Get-Service -Name $App).Status)"
  Write-Host "-- service.log"; Get-Content "$env:ProgramData\PXLVZN\Kvm\service.log" -ErrorAction SilentlyContinue | Out-Host
  Write-Host "-- listening"; netstat -ano | Select-String ":4761[01]" | Out-Host
  Get-WinEvent -FilterHashtable @{LogName = 'Application'; StartTime = (Get-Date).AddMinutes(-10)} -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match 'Kvm|Python' } | Select-Object -First 10 | Format-List TimeCreated, ProviderName, Message | Out-Host
  throw "the service's control endpoint didn't answer"
}
$acl = (Get-Acl "$env:ProgramData\PXLVZN\Kvm").Access | ForEach-Object { $_.IdentityReference.Value }
Write-Host "pair store readable by: $($acl -join ', ')"
if ($acl -match 'Users') { throw "the pair store must not be readable by every user" }

if ($Smoke) {
  Write-Host "== smoke test the installed app"
  Invoke-Expression "$Smoke `"$exe`""
  if ($LASTEXITCODE -ne 0) { throw "smoke test failed ($LASTEXITCODE)" }
}

Write-Host "== uninstall"
$uninst = $reg.UninstallString.Trim('"')
$p = Start-Process $uninst -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "uninstall exited with $($p.ExitCode)" }
for ($i = 0; $i -lt 30 -and ((Test-Path $dir) -or (Test-Path $key) -or (Get-Service -Name $App -ErrorAction SilentlyContinue)); $i++) { Start-Sleep 1 }
if (Get-Service -Name $App -ErrorAction SilentlyContinue) { throw "service still registered after uninstall" }
if (Test-Path $dir) { throw "$dir still there after uninstall" }
if (Test-Path $key) { throw "uninstall entry still registered" }
Write-Host "installer OK"
