# PowerShell script to allow LightRAG port 9262 in Windows Firewall
# This script must be run as Administrator

Write-Host "Adding Windows Firewall rule for LightRAG port 9262..." -ForegroundColor Cyan

try {
    # Check if rule already exists
    $existingRule = Get-NetFirewallRule -DisplayName "LightRAG Port 9262" -ErrorAction SilentlyContinue
    
    if ($existingRule) {
        Write-Host "Firewall rule already exists. Enabling it..." -ForegroundColor Yellow
        Enable-NetFirewallRule -DisplayName "LightRAG Port 9262"
        Write-Host "✓ Firewall rule enabled" -ForegroundColor Green
    } else {
        # Create new firewall rule
        New-NetFirewallRule `
            -DisplayName "LightRAG Port 9262" `
            -Direction Inbound `
            -LocalPort 9262 `
            -Protocol TCP `
            -Action Allow `
            -Description "Allow LightRAG service on port 9262 for remote access" `
            -Profile Domain,Private,Public
        
        Write-Host "✓ Firewall rule created successfully" -ForegroundColor Green
    }
    
    # Verify the rule
    Write-Host "`nVerifying firewall rule..." -ForegroundColor Cyan
    $rule = Get-NetFirewallRule -DisplayName "LightRAG Port 9262"
    Write-Host "Rule Name: $($rule.DisplayName)" -ForegroundColor White
    Write-Host "Enabled: $($rule.Enabled)" -ForegroundColor White
    Write-Host "Direction: $($rule.Direction)" -ForegroundColor White
    Write-Host "Action: $($rule.Action)" -ForegroundColor White
    Write-Host "Profiles: $($rule.Profile -join ', ')" -ForegroundColor White
    
    # Show port details
    $portFilter = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $rule
    Write-Host "Protocol: $($portFilter.Protocol)" -ForegroundColor White
    Write-Host "Local Port: $($portFilter.LocalPort)" -ForegroundColor White
    
    Write-Host "`n✓ LightRAG port 9262 is now accessible from remote PCs" -ForegroundColor Green
    Write-Host "`nNote: Make sure LightRAG is listening on 0.0.0.0 (all interfaces) not just 127.0.0.1" -ForegroundColor Yellow
    
} catch {
    Write-Host "`n✗ Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`nPlease run this script as Administrator:" -ForegroundColor Yellow
    Write-Host "1. Right-click PowerShell" -ForegroundColor White
    Write-Host "2. Select 'Run as Administrator'" -ForegroundColor White
    Write-Host "3. Navigate to this directory and run: .\allow_lightrag_firewall.ps1" -ForegroundColor White
    exit 1
}

