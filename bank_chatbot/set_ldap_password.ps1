# PowerShell script to securely set LDAP password
# This script prompts for the password securely

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "LDAP Password Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    exit 1
}

# Prompt for password securely
Write-Host "Enter LDAP password for EBL\aichatbot:" -ForegroundColor Yellow
$securePassword = Read-Host -AsSecureString "Password"

# Convert secure string to plain text (for .env file storage)
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)

# Read current settings
$envContent = Get-Content $envFile -Raw

# Update password
$envContent = $envContent -replace "LDAP_BIND_PASSWORD=.*", "LDAP_BIND_PASSWORD=$plainPassword"

Set-Content -Path $envFile -Value $envContent -NoNewline

# Clear password from memory
$plainPassword = $null
$securePassword = $null

Write-Host ""
Write-Host "[OK] Password updated in .env file" -ForegroundColor Green
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











