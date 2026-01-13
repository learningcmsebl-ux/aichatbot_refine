# PowerShell script to update LDAP credentials in .env file (non-interactive)
# Usage: .\set_ldap_credentials.ps1 -BindUser "EBL\username" -BindPassword "password" [-BaseDN "DC=ebl,DC=local"]

param(
    [Parameter(Mandatory=$true)]
    [string]$BindUser,
    
    [Parameter(Mandatory=$true)]
    [string]$BindPassword,
    
    [Parameter(Mandatory=$false)]
    [string]$BaseDN
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "LDAP Credentials Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    exit 1
}

# Read current settings
$envContent = Get-Content $envFile -Raw

Write-Host "Updating LDAP credentials..." -ForegroundColor Yellow

# Update credentials
$envContent = $envContent -replace "LDAP_BIND_USER=.*", "LDAP_BIND_USER=$BindUser"
$envContent = $envContent -replace "LDAP_BIND_PASSWORD=.*", "LDAP_BIND_PASSWORD=$BindPassword"

if ($BaseDN) {
    $envContent = $envContent -replace "LDAP_BASE_DN=.*", "LDAP_BASE_DN=$BaseDN"
    Write-Host "  Base DN: $BaseDN" -ForegroundColor White
}

Write-Host "  Bind User: $BindUser" -ForegroundColor White
Write-Host "  Password: ***" -ForegroundColor White

Set-Content -Path $envFile -Value $envContent -NoNewline

Write-Host ""
Write-Host "[OK] Credentials updated in .env file" -ForegroundColor Green
Write-Host ""

# Test connection
Write-Host "Testing LDAP connection..." -ForegroundColor Yellow
Write-Host ""

$testResult = python test_ldap_connection.py 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] LDAP connection test PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run a full sync:" -ForegroundColor Cyan
    Write-Host "  python sync_phonebook_from_ldap.py" -ForegroundColor White
} else {
    Write-Host "[FAILED] LDAP connection test FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  1. Check if credentials are correct" -ForegroundColor White
    Write-Host "  2. Verify Base DN is correct" -ForegroundColor White
    Write-Host "  3. Ensure LDAP server is accessible" -ForegroundColor White
    Write-Host "  4. Check if account is locked or disabled" -ForegroundColor White
    Write-Host ""
    Write-Host "Error details:" -ForegroundColor Yellow
    $testResult | Select-String -Pattern "ERROR|Error|error|FAILED|Failed" | Select-Object -First 5 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Red
    }
}

