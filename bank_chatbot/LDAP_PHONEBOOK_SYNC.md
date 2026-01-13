# LDAP Phonebook Sync Service

This service syncs employee contact information from Active Directory (LDAP) to the PostgreSQL phonebook database.

## Features

- ✅ Automatic sync from Active Directory
- ✅ Handles large directories with paged searches
- ✅ Upsert logic (insert new, update existing)
- ✅ Maps AD attributes to phonebook schema
- ✅ Error handling and logging
- ✅ Dry-run mode for testing

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `ldap3` package for LDAP connectivity.

### 2. Configure LDAP Connection

Add LDAP configuration to your `.env` file:

```env
# LDAP/Active Directory Configuration
LDAP_SERVER=192.168.5.60
LDAP_BASE_DN=DC=ebl,DC=local
LDAP_BIND_USER=EBL\service_account
LDAP_BIND_PASSWORD=your_ldap_password
LDAP_USE_SSL=False
```

**Configuration Details:**

- `LDAP_SERVER`: LDAP server hostname or IP address
- `LDAP_BASE_DN`: Base distinguished name for searching (e.g., `DC=ebl,DC=local` or `OU=Users,DC=company,DC=com`)
- `LDAP_BIND_USER`: Username for LDAP authentication (format: `DOMAIN\username` or `username@domain.com`)
- `LDAP_BIND_PASSWORD`: Password for LDAP authentication
- `LDAP_USE_SSL`: Use LDAPS (secure LDAP) - set to `True` for production

### 3. Find Your Base DN

To find your Base DN, you can use:

**Windows (PowerShell):**
```powershell
Get-ADDomain | Select-Object DistinguishedName
```

**Or query LDAP directly:**
```bash
ldapsearch -x -H ldap://192.168.5.60 -b "" -s base namingContexts
```

## Usage

### Manual Sync

Run the sync script:

```bash
# Basic sync (updates existing, inserts new)
python sync_phonebook_from_ldap.py

# Clear all existing records and sync fresh
python sync_phonebook_from_ldap.py --clear

# Dry run (see what would be synced without making changes)
python sync_phonebook_from_ldap.py --dry-run
```

### Command Line Options

```bash
python sync_phonebook_from_ldap.py [OPTIONS]

Options:
  --clear          Clear all existing records before syncing
  --dry-run        Show what would be synced without updating database
  --ldap-server    Override LDAP_SERVER env var
  --base-dn        Override LDAP_BASE_DN env var
  --bind-user      Override LDAP_BIND_USER env var
  --bind-password  Override LDAP_BIND_PASSWORD env var
```

### Scheduled Sync (Recommended)

Set up a scheduled task to run sync periodically:

**Windows Task Scheduler:**
```powershell
# Create scheduled task to run daily at 2 AM
schtasks /create /tn "LDAP Phonebook Sync" /tr "python E:\Chatbot_refine\bank_chatbot\sync_phonebook_from_ldap.py" /sc daily /st 02:00
```

**Linux Cron:**
```bash
# Add to crontab (runs daily at 2 AM)
0 2 * * * cd /path/to/bank_chatbot && python sync_phonebook_from_ldap.py
```

**Docker (if running in container):**
```yaml
# Add to docker-compose.yml
services:
  ldap-sync:
    build: .
    command: python sync_phonebook_from_ldap.py
    environment:
      - LDAP_SERVER=${LDAP_SERVER}
      - LDAP_BASE_DN=${LDAP_BASE_DN}
      # ... other env vars
    volumes:
      - ./:/app
    restart: "no"  # Run once, or use cron in container
```

## How It Works

1. **LDAP Connection**: Connects to Active Directory using provided credentials
2. **Search**: Searches for all enabled user accounts (`userAccountControl` not disabled)
3. **Mapping**: Maps AD attributes to phonebook schema:
   - `sAMAccountName` / `employeeID` → `employee_id`
   - `cn` / `displayName` → `full_name`
   - `givenName` → `first_name`
   - `sn` → `last_name`
   - `mail` → `email`
   - `telephoneNumber` → `telephone`
   - `mobile` → `mobile`
   - `ipPhone` → `ip_phone`
   - `title` → `designation`
   - `department` → `department`
   - `company` → `division`
4. **Upsert**: Inserts new employees or updates existing ones (matched by `employee_id` or `email`)
5. **Full-text Search**: Updates PostgreSQL full-text search index automatically

## AD Attribute Mapping

| AD Attribute | Phonebook Field | Notes |
|-------------|----------------|-------|
| `sAMAccountName` / `employeeID` | `employee_id` | Prefers `employeeID`, falls back to `sAMAccountName` |
| `displayName` / `cn` | `full_name` | Prefers `displayName`, then `cn`, then combines `givenName` + `sn` |
| `givenName` | `first_name` | |
| `sn` | `last_name` | |
| `mail` | `email` | |
| `telephoneNumber` | `telephone` | |
| `mobile` | `mobile` | |
| `ipPhone` | `ip_phone` | |
| `otherTelephone` | `telephone` | Used if `telephoneNumber` is empty |
| `title` | `designation` | Job title |
| `department` | `department` | |
| `company` | `division` | |

## Troubleshooting

### Connection Errors

**Error: "LDAP bind failed"**
- Check LDAP server is accessible: `ping 192.168.5.60`
- Verify credentials are correct
- Check if LDAP port is open: `telnet 192.168.5.60 389`

**Error: "Invalid credentials"**
- Verify `LDAP_BIND_USER` format (use `DOMAIN\username` or `username@domain.com`)
- Check password is correct
- Ensure account is not locked

### Base DN Issues

**Error: "No such object" or empty results**
- Verify `LDAP_BASE_DN` is correct
- Try using root domain: `DC=ebl,DC=local`
- Or specific OU: `OU=Users,DC=ebl,DC=local`

### SSL/TLS Issues

**Error: "SSL certificate verification failed"**
- Set `LDAP_USE_SSL=False` for testing
- For production, ensure SSL certificate is valid
- Or disable certificate verification (not recommended for production)

### Performance

**Sync is slow:**
- Large directories may take time
- Consider syncing during off-hours
- Use `--dry-run` first to estimate time

## Security Best Practices

1. **Use Service Account**: Create a dedicated AD service account with minimal permissions (read-only)
2. **Secure Password Storage**: Store `LDAP_BIND_PASSWORD` in environment variables or secret manager
3. **Use LDAPS**: Enable SSL/TLS in production (`LDAP_USE_SSL=True`)
4. **Network Security**: Ensure LDAP traffic is on secure network
5. **Regular Updates**: Run sync frequently to keep data current

## Integration with Chatbot

The synced phonebook is automatically used by the chatbot for employee/contact queries. No additional configuration needed - just ensure the sync runs regularly.

## API Usage (Programmatic)

You can also use the LDAP sync service programmatically:

```python
from app.services.ldap_phonebook_sync import LdapPhonebookSync
from app.services.phonebook_postgres import PhoneBookDB

# Initialize services
ldap = LdapPhonebookSync(
    ldap_server="192.168.5.60",
    base_dn="DC=ebl,DC=local",
    bind_user="EBL\\service_account",
    bind_password="password"
)

phonebook = PhoneBookDB()

# Sync
stats = phonebook.sync_from_ldap(ldap, clear_existing=False)
print(f"Synced {stats['total']} employees")
```

## Support

For issues or questions:
1. Check logs: `sync_phonebook_from_ldap.py` outputs detailed logs
2. Test connection: Use `--dry-run` to test without making changes
3. Verify AD access: Ensure service account has read permissions

