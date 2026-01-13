#!/usr/bin/env python3
"""
LDAP Phonebook Sync Script
Syncs employee contact information from Active Directory to PostgreSQL phonebook

Usage:
    python sync_phonebook_from_ldap.py [--clear] [--dry-run]

Options:
    --clear     Clear all existing records before syncing
    --dry-run   Show what would be synced without actually updating the database
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logging.info(f"Loaded environment variables from {env_path}")

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.phonebook_postgres import PhoneBookDB, get_phonebook_db
from app.services.ldap_phonebook_sync import LdapPhonebookSync, get_ldap_sync_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Sync phonebook from LDAP/Active Directory'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear all existing records before syncing'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without updating the database'
    )
    parser.add_argument(
        '--ldap-server',
        type=str,
        help='LDAP server hostname or IP (overrides LDAP_SERVER env var)'
    )
    parser.add_argument(
        '--base-dn',
        type=str,
        help='LDAP base DN (overrides LDAP_BASE_DN env var)'
    )
    parser.add_argument(
        '--bind-user',
        type=str,
        help='LDAP bind user (overrides LDAP_BIND_USER env var)'
    )
    parser.add_argument(
        '--bind-password',
        type=str,
        help='LDAP bind password (overrides LDAP_BIND_PASSWORD env var)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize LDAP service
        logger.info("Initializing LDAP connection...")
        ldap_kwargs = {}
        if args.ldap_server:
            ldap_kwargs['ldap_server'] = args.ldap_server
        if args.base_dn:
            ldap_kwargs['base_dn'] = args.base_dn
        if args.bind_user:
            ldap_kwargs['bind_user'] = args.bind_user
        if args.bind_password:
            ldap_kwargs['bind_password'] = args.bind_password
        
        ldap_service = LdapPhonebookSync(**ldap_kwargs) if ldap_kwargs else get_ldap_sync_service()
        
        # Test LDAP connection
        logger.info("Testing LDAP connection...")
        test_employees = ldap_service.search_employee("test", limit=1)
        logger.info("✓ LDAP connection successful")
        
        if args.dry_run:
            # Dry run: just show what would be synced
            logger.info("DRY RUN MODE - No database changes will be made")
            all_employees = ldap_service.get_all_employees()
            logger.info(f"Would sync {len(all_employees)} employees from LDAP")
            
            # Show sample
            if all_employees:
                logger.info("\nSample employees that would be synced:")
                for i, emp in enumerate(all_employees[:5], 1):
                    logger.info(f"\n{i}. {emp.get('full_name', 'N/A')}")
                    logger.info(f"   Employee ID: {emp.get('employee_id', 'N/A')}")
                    logger.info(f"   Email: {emp.get('email', 'N/A')}")
                    logger.info(f"   Department: {emp.get('department', 'N/A')}")
                    logger.info(f"   Designation: {emp.get('designation', 'N/A')}")
            
            logger.info(f"\nTotal: {len(all_employees)} employees would be synced")
            return 0
        
        # Initialize phonebook database
        logger.info("Connecting to phonebook database...")
        phonebook_db = get_phonebook_db()
        logger.info("✓ Database connection successful")
        
        # Perform sync
        logger.info("Starting LDAP sync...")
        stats = phonebook_db.sync_from_ldap(ldap_service, clear_existing=args.clear)
        
        # Print summary
        print("\n" + "="*60)
        print("LDAP SYNC SUMMARY")
        print("="*60)
        print(f"Total employees in LDAP: {stats['total']}")
        print(f"New employees inserted:  {stats['inserted']}")
        print(f"Existing employees updated: {stats['updated']}")
        print(f"Errors: {stats['errors']}")
        print("="*60)
        
        if stats['errors'] > 0:
            logger.warning(f"Sync completed with {stats['errors']} errors")
            return 1
        
        logger.info("✓ LDAP sync completed successfully")
        return 0
        
    except ConnectionError as e:
        logger.error(f"LDAP connection failed: {e}")
        logger.error("Please check:")
        logger.error("  - LDAP server is accessible")
        logger.error("  - LDAP credentials are correct")
        logger.error("  - Base DN is correct")
        return 1
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

