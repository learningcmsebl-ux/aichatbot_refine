# PowerShell script to configure LDAP settings in .env file
# This script helps you find and configure the correct LDAP Base DN

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "LDAP Configuration Helper" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create .env file from env.example first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Current LDAP settings in .env:" -ForegroundColor Yellow
Get-Content $envFile | Select-String -Pattern "LDAP" | ForEach-Object {
    if ($_ -match "PASSWORD") {
        Write-Host "  LDAP_BIND_PASSWORD=***" -ForegroundColor Gray
    } else {
        Write-Host "  $_" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "To configure LDAP settings, you need:" -ForegroundColor Cyan
Write-Host "1. LDAP Server: 192.168.5.60 (already configured)" -ForegroundColor White
Write-Host "2. Base DN: The distinguished name of your AD domain" -ForegroundColor White
Write-Host "3. Bind User: Service account username (format: EBL\username)" -ForegroundColor White
Write-Host "4. Bind Password: Service account password" -ForegroundColor White
Write-Host ""

# Try to get Base DN from AD (if running on domain-joined machine)
Write-Host "Attempting to detect Base DN from Active Directory..." -ForegroundColor Yellow
try {
    $domain = Get-ADDomain -ErrorAction Stop
    $detectedBaseDN = $domain.DistinguishedName
    Write-Host "✓ Detected Base DN: $detectedBaseDN" -ForegroundColor Green
    Write-Host ""
    Write-Host "Would you like to update LDAP_BASE_DN to: $detectedBaseDN ?" -ForegroundColor Cyan
    $update = Read-Host "Update? (Y/N)"
    
    if ($update -eq "Y" -or $update -eq "y") {
        $content = Get-Content $envFile -Raw
        $content = $content -replace "LDAP_BASE_DN=.*", "LDAP_BASE_DN=$detectedBaseDN"
        Set-Content -Path $envFile -Value $content -NoNewline
        Write-Host "✓ Updated LDAP_BASE_DN in .env" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠ Could not auto-detect Base DN (not on domain-joined machine or AD module not available)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To find your Base DN manually:" -ForegroundColor Cyan
    Write-Host "  Option 1: Run on domain controller or domain-joined machine:" -ForegroundColor White
    Write-Host "    Get-ADDomain | Select-Object DistinguishedName" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Option 2: Query LDAP directly:" -ForegroundColor White
    Write-Host "    ldapsearch -x -H ldap://192.168.5.60 -b "" -s base namingContexts" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Option 3: Common formats:" -ForegroundColor White
    Write-Host "    DC=ebl,DC=local" -ForegroundColor Gray
    Write-Host "    DC=company,DC=com" -ForegroundColor Gray
    Write-Host "    OU=Users,DC=ebl,DC=local" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. Update LDAP_BIND_USER with your service account (format: EBL\username)" -ForegroundColor White
Write-Host "2. Update LDAP_BIND_PASSWORD with the service account password" -ForegroundColor White
Write-Host "3. Verify LDAP_BASE_DN is correct" -ForegroundColor White
Write-Host "4. Test connection: python sync_phonebook_from_ldap.py --dry-run" -ForegroundColor White
Write-Host ""

