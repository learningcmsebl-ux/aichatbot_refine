# PowerShell script to open PostgreSQL port 5432 in Windows Firewall
# Run as Administrator: Right-click PowerShell -> "Run as Administrator"

$port = 5432
$ruleName = "PostgreSQL Port 5432"
$description = "Allow inbound TCP connections on port 5432 for PostgreSQL database"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Opening PostgreSQL Port 5432 in Firewall" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Check if rule already exists
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "Firewall rule '$ruleName' already exists." -ForegroundColor Yellow
    
    # Check if it's enabled
    if ($existingRule.Enabled -eq $true) {
        Write-Host "Rule is already enabled. Port 5432 should be accessible." -ForegroundColor Green
    } else {
        Write-Host "Rule exists but is disabled. Enabling it..." -ForegroundColor Yellow
        Enable-NetFirewallRule -DisplayName $ruleName
        Write-Host "Rule enabled successfully!" -ForegroundColor Green
    }
} else {
    Write-Host "Creating new firewall rule for port $port..." -ForegroundColor Yellow
    
    try {
        # Create new firewall rule
        New-NetFirewallRule `
            -DisplayName $ruleName `
            -Description $description `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort $port `
            -Action Allow `
            -Profile Domain,Private,Public `
            -Enabled True
        
        Write-Host "SUCCESS: Firewall rule created and enabled!" -ForegroundColor Green
        Write-Host "Port $port is now open for inbound connections." -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to create firewall rule: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Verifying rule status..." -ForegroundColor Cyan
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    Write-Host "Rule Name: $($rule.DisplayName)" -ForegroundColor White
    Write-Host "Enabled: $($rule.Enabled)" -ForegroundColor $(if ($rule.Enabled) { "Green" } else { "Red" })
    Write-Host "Direction: $($rule.Direction)" -ForegroundColor White
    Write-Host "Action: $($rule.Action)" -ForegroundColor White
    
    $portFilter = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $rule
    Write-Host "Protocol: $($portFilter.Protocol)" -ForegroundColor White
    Write-Host "Local Port: $($portFilter.LocalPort)" -ForegroundColor White
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Firewall configuration complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
