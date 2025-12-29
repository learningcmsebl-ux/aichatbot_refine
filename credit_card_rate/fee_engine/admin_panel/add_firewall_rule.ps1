# PowerShell script to add Windows Firewall rule for Admin Panel (Port 8009)
# This script must be run as Administrator

Write-Host "Adding Windows Firewall rule for Fee Engine Admin Panel (Port 8009)..." -ForegroundColor Yellow

try {
    # Method 1: Using New-NetFirewallRule (PowerShell cmdlet)
    New-NetFirewallRule `
        -DisplayName "Fee Engine Admin Panel (Port 8009)" `
        -Direction Inbound `
        -LocalPort 8009 `
        -Protocol TCP `
        -Action Allow `
        -Description "Allow inbound traffic for Fee Engine Admin Panel on port 8009"
    
    Write-Host "✓ Firewall rule added successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The admin panel is now accessible from remote computers on port 8009." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To verify the rule was added, run:" -ForegroundColor Yellow
    Write-Host "  Get-NetFirewallRule -DisplayName '*Fee Engine Admin Panel*'" -ForegroundColor Gray
    
} catch {
    Write-Host "✗ Error adding firewall rule: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure you are running PowerShell as Administrator!" -ForegroundColor Yellow
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

