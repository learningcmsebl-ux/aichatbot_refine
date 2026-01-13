"""
LDAP/Active Directory Phonebook Sync Service
Syncs employee contact information from Active Directory to PostgreSQL phonebook
"""
import os
import logging
from typing import List, Dict, Optional
from ldap3 import Server, Connection, ALL, SUBTREE, Tls, core
import ssl

logger = logging.getLogger(__name__)


class LdapPhonebookSync:
    """Service to sync employee data from LDAP/Active Directory"""
    
    def __init__(
        self,
        ldap_server: str = None,
        base_dn: str = None,
        bind_user: str = None,
        bind_password: str = None,
        use_ssl: bool = False,
        port: int = None
    ):
        """
        Initialize LDAP connection
        
        Args:
            ldap_server: LDAP server hostname or IP (e.g., '192.168.5.60' or 'ldap.example.com')
            base_dn: Base distinguished name (e.g., 'DC=ebl,DC=local' or 'OU=Users,DC=company,DC=com')
            bind_user: Username for LDAP bind (e.g., 'EBL\\username' or 'username@domain.com')
            bind_password: Password for LDAP bind
            use_ssl: Use LDAPS (secure LDAP)
            port: LDAP port (default: 389 for LDAP, 636 for LDAPS)
        """
        # Get from environment if not provided
        self.ldap_server = ldap_server or os.getenv('LDAP_SERVER', '192.168.5.60')
        self.base_dn = base_dn or os.getenv('LDAP_BASE_DN', '')
        self.bind_user = bind_user or os.getenv('LDAP_BIND_USER', '')
        self.bind_password = bind_password or os.getenv('LDAP_BIND_PASSWORD', '')
        self.use_ssl = use_ssl or os.getenv('LDAP_USE_SSL', 'False').lower() == 'true'
        self.port = port or (636 if self.use_ssl else 389)
        
        # Build server URL
        protocol = 'ldaps' if self.use_ssl else 'ldap'
        self.server_url = f"{protocol}://{self.ldap_server}:{self.port}"
        
        logger.info(f"LDAP Sync initialized: {self.server_url}, Base DN: {self.base_dn}")
    
    def _get_connection(self) -> Connection:
        """Create and return LDAP connection"""
        server = Server(
            self.ldap_server,
            port=self.port,
            use_ssl=self.use_ssl,
            get_info=ALL
        )
        
        # Determine authentication method
        # If no bind_user, use anonymous bind
        if not self.bind_user:
            logger.info("Using anonymous LDAP bind (no credentials provided)")
            conn = Connection(
                server,
                auto_bind=True,
                raise_exceptions=False
            )
        elif not self.bind_password:
            # Username only (no password) - some LDAP servers support this
            # Note: The ldap3 library requires a password parameter, but we'll try different approaches
            logger.info(f"Attempting LDAP bind with username only (no password): {self.bind_user}")
            
            # Try NTLM authentication which might support username-only in some configurations
            try:
                logger.info("Trying NTLM authentication...")
                conn = Connection(
                    server,
                    user=self.bind_user,
                    password="",  # Empty password
                    authentication='NTLM',
                    auto_bind=True,
                    raise_exceptions=False
                )
                if conn.bind():
                    logger.info("Successfully bound using NTLM authentication")
                else:
                    raise Exception(f"Bind failed: {conn.result}")
            except Exception as e:
                logger.warning(f"NTLM authentication failed: {e}")
                # Fallback to SIMPLE with empty password (will likely fail but worth trying)
                logger.info("Trying SIMPLE authentication with empty password...")
                conn = Connection(
                    server,
                    user=self.bind_user,
                    password="",  # Empty password
                    authentication='SIMPLE',
                    auto_bind=True,
                    raise_exceptions=False
                )
                if not conn.bind():
                    error_msg = f"LDAP bind failed with username-only authentication. Server returned: {conn.result}"
                    logger.error(error_msg)
                    logger.error("The ldap3 library requires a password parameter for authentication.")
                    logger.error("If your LDAP server supports username-only authentication, you may need to:")
                    logger.error("  1. Provide a minimal password (even if the account doesn't require one)")
                    logger.error("  2. Use a different LDAP client library")
                    logger.error("  3. Configure the LDAP server to accept passwordless authentication")
                    raise ConnectionError(error_msg)
        else:
            # Use authenticated bind with username and password
            logger.info(f"Using LDAP bind with username and password: {self.bind_user}")
            conn = Connection(
                server,
                user=self.bind_user,
                password=self.bind_password,
                auto_bind=True,
                raise_exceptions=False
            )
        
        if not conn.bind():
            error_msg = f"LDAP bind failed: {conn.result}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        
        logger.info("LDAP connection established successfully")
        return conn
    
    def get_all_employees(self) -> List[Dict]:
        """
        Retrieve all enabled employees from Active Directory
        
        Returns:
            List of employee dictionaries with contact information
        """
        employees = []
        
        try:
            conn = self._get_connection()
            
            # Search filter: enabled user accounts only
            # userAccountControl:1.2.840.113556.1.4.803:=2 means account is disabled
            # We want accounts that are NOT disabled
            search_filter = (
                "(&(objectClass=user)"
                "(objectCategory=person)"
                "(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
            )
            
            # Attributes to retrieve from AD
            attributes = [
                'sAMAccountName',      # Username/Employee ID
                'cn',                  # Common Name (Full Name)
                'givenName',           # First Name
                'sn',                  # Last Name (Surname)
                'displayName',         # Display Name
                'mail',                # Email
                'telephoneNumber',     # Office Phone
                'mobile',              # Mobile Phone
                'ipPhone',             # IP Phone
                'otherTelephone',      # Other Phone Numbers
                'title',               # Job Title/Designation
                'department',          # Department
                'company',             # Company/Division
                'employeeID',         # Employee ID (if different from sAMAccountName)
                'physicalDeliveryOfficeName',  # Office Location
                'manager',             # Manager DN
                'description'          # Description/Notes
            ]
            
            # Perform search
            conn.search(
                search_base=self.base_dn if self.base_dn else '',
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                paged_size=1000  # Handle large directories
            )
            
            logger.info(f"LDAP search returned {len(conn.entries)} entries")
            
            # Process each entry
            for entry in conn.entries:
                try:
                    emp = self._map_ldap_entry_to_employee(entry)
                    if emp and emp.get('full_name'):  # Only include if has name
                        employees.append(emp)
                except Exception as e:
                    logger.warning(f"Failed to process LDAP entry: {e}")
                    continue
            
            conn.unbind()
            logger.info(f"Successfully retrieved {len(employees)} employees from LDAP")
            
        except Exception as e:
            logger.error(f"Error retrieving employees from LDAP: {e}", exc_info=True)
            raise
        
        return employees
    
    def _map_ldap_entry_to_employee(self, entry) -> Optional[Dict]:
        """
        Map LDAP entry to employee dictionary
        
        Args:
            entry: LDAP entry object
            
        Returns:
            Employee dictionary matching PhoneBookDB schema
        """
        def get_attr(attr_name: str, default: str = None) -> Optional[str]:
            """Helper to safely get attribute value"""
            try:
                if hasattr(entry, attr_name):
                    value = getattr(entry, attr_name)
                    if value and len(value) > 0:
                        return str(value[0]) if isinstance(value, list) else str(value)
            except Exception:
                pass
            return default
        
        # Get employee ID (prefer employeeID, fallback to sAMAccountName)
        employee_id = get_attr('employeeID') or get_attr('sAMAccountName')
        
        # Get full name (prefer displayName, then cn, then combine givenName+sn)
        full_name = get_attr('displayName') or get_attr('cn')
        if not full_name:
            first_name = get_attr('givenName', '')
            last_name = get_attr('sn', '')
            full_name = f"{first_name} {last_name}".strip()
        
        # Get phone numbers
        telephone = get_attr('telephoneNumber')
        mobile = get_attr('mobile')
        ip_phone = get_attr('ipPhone')
        
        # Handle otherTelephone (may contain multiple numbers)
        other_phones = get_attr('otherTelephone', '')
        if other_phones and not telephone:
            # Use first other telephone if main telephone is not available
            telephone = other_phones.split(',')[0].strip() if ',' in other_phones else other_phones
        
        # Build employee dictionary
        employee = {
            'employee_id': employee_id,
            'full_name': full_name,
            'first_name': get_attr('givenName'),
            'last_name': get_attr('sn'),
            'email': get_attr('mail'),
            'telephone': telephone,
            'mobile': mobile,
            'ip_phone': ip_phone,
            'designation': get_attr('title'),
            'department': get_attr('department'),
            'division': get_attr('company'),
            'group_email': None  # Not typically in AD, can be set separately
        }
        
        # Clean up empty strings
        for key, value in employee.items():
            if value == '':
                employee[key] = None
        
        return employee
    
    def search_employee(self, search_term: str, limit: int = 10) -> List[Dict]:
        """
        Search for employees in AD by name, email, or employee ID
        
        Args:
            search_term: Search term (name, email, or employee ID)
            limit: Maximum number of results
            
        Returns:
            List of matching employee dictionaries
        """
        employees = []
        
        try:
            conn = self._get_connection()
            
            # Build search filter
            search_filter = (
                f"(&(objectClass=user)(objectCategory=person)"
                f"(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
                f"(|(cn=*{search_term}*)(mail=*{search_term}*)(sAMAccountName=*{search_term}*)"
                f"(givenName=*{search_term}*)(sn=*{search_term}*)(displayName=*{search_term}*)))"
            )
            
            attributes = [
                'sAMAccountName', 'cn', 'givenName', 'sn', 'displayName',
                'mail', 'telephoneNumber', 'mobile', 'ipPhone', 'otherTelephone',
                'title', 'department', 'company', 'employeeID'
            ]
            
            conn.search(
                search_base=self.base_dn if self.base_dn else '',
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                size_limit=limit
            )
            
            for entry in conn.entries:
                try:
                    emp = self._map_ldap_entry_to_employee(entry)
                    if emp and emp.get('full_name'):
                        employees.append(emp)
                except Exception as e:
                    logger.warning(f"Failed to process search result: {e}")
                    continue
            
            conn.unbind()
            
        except Exception as e:
            logger.error(f"Error searching LDAP: {e}", exc_info=True)
            raise
        
        return employees


def get_ldap_sync_service() -> LdapPhonebookSync:
    """Get or create global LDAP sync service instance"""
    return LdapPhonebookSync()

