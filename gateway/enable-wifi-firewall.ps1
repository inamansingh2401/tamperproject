#Requires -RunAsAdministrator
# Run in an Administrator PowerShell window whenever the LAN address changes.
param(
    [string]$LocalAddress = '10.178.156.16',
    [string]$RemoteSubnet = '10.178.156.0/24',
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'

$ruleName = 'TrackSure signed WiFi ingest'
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    $rule | Remove-NetFirewallRule
}
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort $Port -LocalAddress $LocalAddress -RemoteAddress $RemoteSubnet -Profile Any
