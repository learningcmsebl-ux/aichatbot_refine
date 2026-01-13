# PowerShell script to securely update LDAP credentials in .env file
# This script prompts for credentials and updates .env file

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

Write-Host "Current LDAP configuration:" -ForegroundColor Yellow
$currentServer = ([regex]::Match($envContent, "LDAP_SERVER=([^\r\n]+)")).Groups[1].Value
$currentBaseDN = ([regex]::Match($envContent, "LDAP_BASE_DN=([^\r\n]+)")).Groups[1].Value
$currentUser = ([regex]::Match($envContent, "LDAP_BIND_USER=([^\r\n]+)")).Groups[1].Value

Write-Host "  Server: $currentServer" -ForegroundColor White
Write-Host "  Base DN: $currentBaseDN" -ForegroundColor White
Write-Host "  Bind User: $currentUser" -ForegroundColor White
Write-Host ""

# Prompt for updates
Write-Host "Enter LDAP credentials (press Enter to keep current value):" -ForegroundColor Cyan
Write-Host ""

# Base DN
$newBaseDN = Read-Host "Base DN [$currentBaseDN]"
if ([string]::IsNullOrWhiteSpace($newBaseDN)) {
    $newBaseDN = $currentBaseDN
}

# Bind User
$newUser = Read-Host "Bind User (format: EBL\username) [$currentUser]"
if ([string]::IsNullOrWhiteSpace($newUser)) {
    $newUser = $currentUser
}

# Bind Password (secure input)
$securePassword = Read-Host "Bind Password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
)

# Update .env file
Write-Host ""
Write-Host "Updating .env file..." -ForegroundColor Yellow

$envContent = $envContent -replace "LDAP_BASE_DN=.*", "LDAP_BASE_DN=$newBaseDN"
$envContent = $envContent -replace "LDAP_BIND_USER=.*", "LDAP_BIND_USER=$newUser"
$envContent = $envContent -replace "LDAP_BIND_PASSWORD=.*", "LDAP_BIND_PASSWORD=$passwordPlain"

Set-Content -Path $envFile -Value $envContent -NoNewline

Write-Host "[OK] Credentials updated in .env file" -ForegroundColor Green
Write-Host ""

# Test connection
Write-Host "Testing LDAP connection..." -ForegroundColor Yellow
Write-Host ""

$testResult = python sync_phonebook_from_ldap.py --dry-run 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] LDAP connection successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run a full sync:" -ForegroundColor Cyan
    Write-Host "  python sync_phonebook_from_ldap.py" -ForegroundColor White
} else {
    Write-Host "[FAILED] LDAP connection failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  1. Check if credentials are correct" -ForegroundColor White
    Write-Host "  2. Verify Base DN is correct" -ForegroundColor White
    Write-Host "  3. Ensure LDAP server is accessible: ping $currentServer" -ForegroundColor White
    Write-Host "  4. Check if account is locked or disabled" -ForegroundColor White
    Write-Host ""
    Write-Host "Error details:" -ForegroundColor Yellow
    $testResult | Select-String -Pattern "ERROR|Error|error" | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Red
    }
}

# Clear password from memory
$passwordPlain = $null
$securePassword = $null
