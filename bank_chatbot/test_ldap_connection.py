#!/usr/bin/env python3
"""
Quick LDAP connection test script
Tests connectivity and authentication without syncing data
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ldap_phonebook_sync import LdapPhonebookSync

def test_connection():
    """Test LDAP connection with current credentials"""
    print("="*60)
    print("LDAP Connection Test")
    print("="*60)
    print()
    
    # Get configuration
    ldap_server = os.getenv('LDAP_SERVER', '192.168.5.60')
    base_dn = os.getenv('LDAP_BASE_DN', '')
    bind_user = os.getenv('LDAP_BIND_USER', '')
    use_ssl = os.getenv('LDAP_USE_SSL', 'False').lower() == 'true'
    
    print(f"Configuration:")
    print(f"  Server: {ldap_server}")
    print(f"  Base DN: {base_dn or '(not set)'}")
    print(f"  Bind User: {bind_user or '(not set - using anonymous bind)'}")
    print(f"  Use SSL: {use_ssl}")
    print()
    
    # Allow anonymous bind (empty user and password)
    # Only check for placeholder values if user is provided
    if bind_user and bind_user == "EBL\\service_account":
        print("[ERROR] LDAP_BIND_USER is using placeholder value")
        print("   Please set it using: .\\set_ldap_credentials.ps1")
        print("   Or manually edit .env file")
        print("   Or leave it empty for anonymous bind")
        return 1
    
    if not bind_user:
        print("[INFO] Using anonymous LDAP bind (no credentials)")
        print()
    
    try:
        print("Testing connection...")
        ldap_service = LdapPhonebookSync()
        
        # Try to get connection
        print("  -> Attempting to connect...")
        conn = ldap_service._get_connection()
        print("  [OK] Connection established")
        
        # Try a simple search
        print("  -> Testing search query...")
        results = ldap_service.search_employee("test", limit=1)
        print(f"  [OK] Search successful (found {len(results)} test results)")
        
        # Try to get total count (if Base DN is set)
        if base_dn:
            print("  -> Testing full directory access...")
            all_employees = ldap_service.get_all_employees()
            print(f"  [OK] Retrieved {len(all_employees)} employees from LDAP")
            
            if all_employees:
                print()
                print("Sample employee:")
                emp = all_employees[0]
                print(f"  Name: {emp.get('full_name', 'N/A')}")
                print(f"  Employee ID: {emp.get('employee_id', 'N/A')}")
                print(f"  Email: {emp.get('email', 'N/A')}")
                print(f"  Department: {emp.get('department', 'N/A')}")
        
        print()
        print("="*60)
        print("[SUCCESS] LDAP connection test PASSED")
        print("="*60)
        print()
        print("You can now run a full sync:")
        print("  python sync_phonebook_from_ldap.py")
        return 0
        
    except ConnectionError as e:
        print()
        print("="*60)
        print("✗ LDAP connection test FAILED")
        print("="*60)
        print()
        print("Connection Error:", str(e))
        print()
        print("Possible issues:")
        print("  1. LDAP server is not accessible")
        print("  2. Invalid credentials (username/password)")
        print("  3. Base DN is incorrect")
        print("  4. Account is locked or disabled")
        print()
        print("To fix:")
        print("  1. Verify server is reachable: ping", ldap_server)
        print("  2. Update credentials: .\\update_ldap_credentials.ps1")
        print("  3. Check Base DN is correct")
        return 1
        
    except Exception as e:
        print()
        print("="*60)
        print("✗ LDAP connection test FAILED")
        print("="*60)
        print()
        print("Error:", str(e))
        print()
        return 1

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    sys.exit(test_connection())

