"""
Phone Book PostgreSQL Database
Fast query system for employee contact information using PostgreSQL
Optimized for performance with full-text search and proper indexing
"""
import re
import os
from typing import List, Dict, Optional
import logging
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import text
from contextlib import contextmanager

logger = logging.getLogger(__name__)

Base = declarative_base()


class Employee(Base):
    """Employee model for PostgreSQL"""
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, index=True, nullable=True)
    full_name = Column(String, nullable=False)
    first_name = Column(String, index=True, nullable=True)
    last_name = Column(String, index=True, nullable=True)
    designation = Column(String, index=True, nullable=True)
    department = Column(String, index=True, nullable=True)
    division = Column(String, nullable=True)
    email = Column(String, index=True, nullable=True)
    telephone = Column(String, nullable=True)
    pabx = Column(String, nullable=True)
    ip_phone = Column(String, nullable=True)
    mobile = Column(String, index=True, nullable=True)
    group_email = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Full-text search vector (computed column)
    search_vector = Column(TSVECTOR)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_employee_id', 'employee_id'),
        Index('idx_full_name', 'full_name'),
        Index('idx_email', 'email'),
        Index('idx_mobile', 'mobile'),
        Index('idx_department', 'department'),
        Index('idx_designation', 'designation'),
        # Full-text search index
        Index('idx_search_vector', 'search_vector', postgresql_using='gin'),
    )


class PhoneBookDB:
    """PostgreSQL database for phone book with fast search capabilities"""
    
    def __init__(self, database_url: str = None):
        """
        Initialize PostgreSQL phone book database
        
        Args:
            database_url: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
        """
        if database_url is None:
            # Get from environment variables
            database_url = os.getenv(
                'PHONEBOOK_DB_URL',
                os.getenv('POSTGRES_DB_URL') or 
                f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
                f"{os.getenv('POSTGRES_PASSWORD', '')}@"
                f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
                f"{os.getenv('POSTGRES_PORT', '5432')}/"
                f"{os.getenv('POSTGRES_DB', 'postgres')}"
            )
        
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            echo=False
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._init_database()
    
    def _init_database(self):
        """Initialize database with schema and full-text search"""
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        
        # Create full-text search trigger function and trigger
        with self.engine.connect() as conn:
            # Create function to update search vector
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION employees_search_vector_update()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.search_vector := 
                        setweight(to_tsvector('english', COALESCE(NEW.full_name, '')), 'A') ||
                        setweight(to_tsvector('english', COALESCE(NEW.designation, '')), 'B') ||
                        setweight(to_tsvector('english', COALESCE(NEW.department, '')), 'B') ||
                        setweight(to_tsvector('english', COALESCE(NEW.division, '')), 'C') ||
                        setweight(to_tsvector('english', COALESCE(NEW.email, '')), 'C');
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            # Create trigger
            conn.execute(text("""
                DROP TRIGGER IF EXISTS employees_search_vector_trigger ON employees;
                CREATE TRIGGER employees_search_vector_trigger
                BEFORE INSERT OR UPDATE ON employees
                FOR EACH ROW
                EXECUTE FUNCTION employees_search_vector_update();
            """))
            
            # Update existing rows
            conn.execute(text("""
                UPDATE employees SET updated_at = updated_at 
                WHERE search_vector IS NULL;
            """))
            
            conn.commit()
        
        logger.info(f"[OK] Phone book PostgreSQL database initialized")
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def parse_phonebook_file(self, file_path: str) -> List[Dict]:
        """Parse phone book text file and extract employee records"""
        employees = []
        current_department = None
        current_division = None
        current_group_email = None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Detect department/division headers
            if 'Employee Name' in line and 'Emp ID' in line:
                i += 1
                continue
            
            # Check for group email
            if 'Group Email' in line or 'Group E-Mail' in line or 'Group Mail ID' in line:
                email_match = re.search(r'([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)', line)
                if email_match:
                    current_group_email = email_match.group(1)
                i += 1
                continue
            
            # Detect department/division
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if 'Employee Name' in next_line and 'Emp ID' in next_line:
                    if current_department is None:
                        current_department = line
                    else:
                        current_division = line
                    i += 1
                    continue
            
            # Parse employee data row
            parts = line.split()
            if len(parts) >= 3:
                emp_id = None
                emp_id_idx = -1
                
                for idx, part in enumerate(parts):
                    clean_part = part.strip('.,;:')
                    if clean_part.isdigit() and 3 <= len(clean_part) <= 5:
                        emp_id = clean_part
                        emp_id_idx = idx
                        break
                
                if emp_id and emp_id_idx > 0:
                    name_parts = parts[:emp_id_idx]
                    full_name = ' '.join(name_parts)
                    
                    email_idx = -1
                    for idx, part in enumerate(parts[emp_id_idx + 1:], start=emp_id_idx + 1):
                        if '@' in part:
                            email_idx = idx
                            break
                    
                    if email_idx > emp_id_idx + 1:
                        designation = ' '.join(parts[emp_id_idx + 1:email_idx])
                    elif len(parts) > emp_id_idx + 1:
                        designation = parts[emp_id_idx + 1]
                    else:
                        designation = ''
                    
                    email = parts[email_idx] if email_idx > 0 else ''
                    remaining = parts[email_idx + 1:] if email_idx > 0 else parts[emp_id_idx + 2:]
                    
                    telephone = remaining[0] if len(remaining) > 0 and remaining[0] != '-' else ''
                    pabx = remaining[1] if len(remaining) > 1 and remaining[1] != '-' else ''
                    ip_phone = remaining[2] if len(remaining) > 2 and remaining[2] != '-' else ''
                    mobile = remaining[3] if len(remaining) > 3 and remaining[3] != '-' else ''
                    
                    name_parts_list = full_name.split()
                    first_name = name_parts_list[0] if name_parts_list else ''
                    last_name = ' '.join(name_parts_list[1:]) if len(name_parts_list) > 1 else ''
                    
                    if full_name and emp_id:
                        employee = {
                            'employee_id': emp_id,
                            'full_name': full_name,
                            'first_name': first_name,
                            'last_name': last_name,
                            'designation': designation,
                            'department': current_department or '',
                            'division': current_division or '',
                            'email': email,
                            'telephone': telephone,
                            'pabx': pabx,
                            'ip_phone': ip_phone,
                            'mobile': mobile,
                            'group_email': current_group_email or ''
                        }
                        employees.append(employee)
            
            i += 1
        
        logger.info(f"[OK] Parsed {len(employees)} employees from phone book")
        return employees
    
    def import_phonebook(self, file_path: str):
        """Import phone book data from text file"""
        employees = self.parse_phonebook_file(file_path)
        
        with self.get_session() as session:
            # Clear existing data
            session.query(Employee).delete()
            session.commit()
            
            # Bulk insert
            inserted = 0
            for emp in employees:
                try:
                    employee = Employee(**emp)
                    session.add(employee)
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert employee {emp.get('full_name', 'unknown')}: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"[OK] Imported {inserted} employees into PostgreSQL database")
        return inserted
    
    def upsert_employee(self, employee_data: Dict) -> bool:
        """
        Insert or update employee record
        
        Args:
            employee_data: Dictionary with employee information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_session() as session:
                # Try to find existing employee by employee_id or email
                existing = None
                if employee_data.get('employee_id'):
                    existing = session.query(Employee).filter(
                        Employee.employee_id == employee_data['employee_id']
                    ).first()
                elif employee_data.get('email'):
                    existing = session.query(Employee).filter(
                        Employee.email == employee_data['email']
                    ).first()
                
                if existing:
                    # Update existing record
                    for key, value in employee_data.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                    session.commit()
                    logger.debug(f"Updated employee: {employee_data.get('full_name', 'unknown')}")
                    return True
                else:
                    # Insert new record
                    employee = Employee(**employee_data)
                    session.add(employee)
                    session.commit()
                    logger.debug(f"Inserted employee: {employee_data.get('full_name', 'unknown')}")
                    return True
        except Exception as e:
            logger.error(f"Error upserting employee {employee_data.get('full_name', 'unknown')}: {e}")
            return False
    
    def sync_from_ldap(self, ldap_service, clear_existing: bool = False) -> Dict[str, int]:
        """
        Sync employees from LDAP/AD to database
        
        Args:
            ldap_service: LdapPhonebookSync instance
            clear_existing: If True, clear all existing records before sync
            
        Returns:
            Dictionary with sync statistics: {'inserted': count, 'updated': count, 'total': count}
        """
        stats = {'inserted': 0, 'updated': 0, 'total': 0, 'errors': 0}
        
        try:
            # Get all employees from LDAP
            logger.info("Fetching employees from LDAP...")
            ldap_employees = ldap_service.get_all_employees()
            stats['total'] = len(ldap_employees)
            
            logger.info(f"Retrieved {stats['total']} employees from LDAP")
            
            # Clear existing if requested
            if clear_existing:
                with self.get_session() as session:
                    deleted = session.query(Employee).delete()
                    session.commit()
                    logger.info(f"Cleared {deleted} existing employee records")
            
            # Upsert each employee
            with self.get_session() as session:
                for emp_data in ldap_employees:
                    try:
                        # Check if exists
                        existing = None
                        if emp_data.get('employee_id'):
                            existing = session.query(Employee).filter(
                                Employee.employee_id == emp_data['employee_id']
                            ).first()
                        elif emp_data.get('email'):
                            existing = session.query(Employee).filter(
                                Employee.email == emp_data['email']
                            ).first()
                        
                        if existing:
                            # Update
                            for key, value in emp_data.items():
                                if hasattr(existing, key) and value is not None:
                                    setattr(existing, key, value)
                            stats['updated'] += 1
                        else:
                            # Insert
                            employee = Employee(**emp_data)
                            session.add(employee)
                            stats['inserted'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to sync employee {emp_data.get('full_name', 'unknown')}: {e}")
                        stats['errors'] += 1
                        continue
                
                session.commit()
            
            logger.info(
                f"LDAP sync completed: {stats['inserted']} inserted, "
                f"{stats['updated']} updated, {stats['errors']} errors, "
                f"{stats['total']} total from LDAP"
            )
            
        except Exception as e:
            logger.error(f"Error syncing from LDAP: {e}", exc_info=True)
            raise
        
        return stats
    
    def search_by_name(self, name: str, limit: int = 10) -> List[Dict]:
        """Search employees by name using full-text search"""
        with self.get_session() as session:
            # Use PostgreSQL full-text search with @@ operator
            search_query = func.plainto_tsquery('english', name)
            query = session.query(Employee).filter(
                Employee.search_vector.op('@@')(search_query)
            ).order_by(
                func.ts_rank(Employee.search_vector, search_query).desc()
            ).limit(limit)
            
            results = []
            for emp in query.all():
                results.append({
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                })
            return results
    
    def search_by_exact_name(self, name: str) -> Optional[Dict]:
        """Search for exact name match (case-insensitive)"""
        with self.get_session() as session:
            emp = session.query(Employee).filter(
                func.lower(Employee.full_name) == func.lower(name)
            ).first()
            
            if emp:
                return {
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                }
            return None
    
    def search_by_partial_name(self, name_part: str, limit: int = 10) -> List[Dict]:
        """Search by partial name match"""
        with self.get_session() as session:
            name_lower = name_part.lower()
            query = session.query(Employee).filter(
                (func.lower(Employee.full_name).like(f'%{name_lower}%')) |
                (func.lower(Employee.first_name).like(f'%{name_lower}%')) |
                (func.lower(Employee.last_name).like(f'%{name_lower}%'))
            ).limit(limit)
            
            results = []
            for emp in query.all():
                results.append({
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                })
            return results
    
    def search_by_employee_id(self, emp_id: str) -> Optional[Dict]:
        """Search by employee ID (case-insensitive)"""
        if not emp_id or not emp_id.strip():
            return None
        emp_id_clean = emp_id.strip()
        with self.get_session() as session:
            # Use case-insensitive search for employee IDs
            emp = session.query(Employee).filter(
                func.lower(Employee.employee_id) == func.lower(emp_id_clean)
            ).first()
            if emp:
                logger.debug(f"Found employee by ID '{emp_id_clean}': {emp.full_name}")
            else:
                logger.debug(f"No employee found with ID '{emp_id_clean}'")
            if emp:
                return {
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                }
            return None
    
    def search_by_email(self, email: str) -> Optional[Dict]:
        """Search by email address"""
        with self.get_session() as session:
            emp = session.query(Employee).filter(
                func.lower(Employee.email) == func.lower(email)
            ).first()
            if emp:
                return {
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                }
            return None
    
    def search_by_mobile(self, mobile: str) -> Optional[Dict]:
        """Search by mobile number"""
        with self.get_session() as session:
            mobile_clean = re.sub(r'[\s-]', '', mobile)
            emp = session.query(Employee).filter(
                func.regexp_replace(Employee.mobile, r'[\s-]', '', 'g') == mobile_clean
            ).first()
            if emp:
                return {
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                }
            return None
    
    def search_by_designation(self, designation: str, limit: int = 20, location: str = None) -> List[Dict]:
        """
        Search by designation, optionally filtered by location/branch (in department field)
        
        Args:
            designation: Job title/role (e.g., "branch manager", "manager")
            limit: Maximum number of results
            location: Optional location/branch name to filter by (searches in department field)
        """
        with self.get_session() as session:
            stop_words = ['of', 'the', 'and', '&', 'a', 'an', 'in', 'on', 'at', 'to', 'for']
            keywords = [k.strip() for k in designation.lower().split() 
                       if len(k.strip()) > 2 and k.strip() not in stop_words]
            
            query = session.query(Employee)
            
            # Build designation filter
            if not keywords:
                query = query.filter(
                    func.lower(Employee.designation).like(f'%{designation.lower()}%')
                )
            else:
                # Build query with all keywords
                conditions = []
                for keyword in keywords:
                    conditions.append(func.lower(Employee.designation).like(f'%{keyword}%'))
                for condition in conditions:
                    query = query.filter(condition)
            
            # If location is provided, also filter by department/division (branch names are often in department)
            if location:
                location_clean = location.strip().lower()
                # Remove common branch suffixes
                location_clean = re.sub(r'\s+branch\s*$', '', location_clean, flags=re.IGNORECASE)
                query = query.filter(
                    (func.lower(Employee.department).like(f'%{location_clean}%')) |
                    (func.lower(Employee.division).like(f'%{location_clean}%'))
                )
            
            query = query.limit(limit)
            
            results = []
            for emp in query.all():
                results.append({
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                })
            return results
    
    def search_by_department(self, department: str, limit: int = 50) -> List[Dict]:
        """Search by department"""
        with self.get_session() as session:
            query = session.query(Employee).filter(
                (func.lower(Employee.department).like(f'%{department.lower()}%')) |
                (func.lower(Employee.division).like(f'%{department.lower()}%'))
            ).limit(limit)
            
            results = []
            for emp in query.all():
                results.append({
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'full_name': emp.full_name,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'designation': emp.designation,
                    'department': emp.department,
                    'division': emp.division,
                    'email': emp.email,
                    'telephone': emp.telephone,
                    'pabx': emp.pabx,
                    'ip_phone': emp.ip_phone,
                    'mobile': emp.mobile,
                    'group_email': emp.group_email
                })
            return results
    
    def count_search_results(self, query: str) -> int:
        """Count total matching results for a search query"""
        with self.get_session() as session:
            query_clean = query.strip()
            if not query_clean:
                return 0
            
            query_lower = query_clean.lower()
            
            # Strategy 1: Exact name match
            count = session.query(Employee).filter(
                func.lower(Employee.full_name) == query_lower
            ).count()
            if count > 0:
                return count
            
            # Strategy 2: Employee ID
            if query_clean.isdigit():
                count = session.query(Employee).filter(Employee.employee_id == query_clean).count()
                if count > 0:
                    return count
            
            # Strategy 3: Email
            if '@' in query_clean:
                count = session.query(Employee).filter(
                    func.lower(Employee.email) == query_lower
                ).count()
                if count > 0:
                    return count
            
            # Strategy 4: Designation (if role keywords present)
            role_keywords = ['head of', 'head', 'manager', 'director', 'officer', 'executive',
                            'president', 'ceo', 'cfo', 'coo', 'svp', 'avp', 'vp', 'evp',
                            'chief', 'senior', 'assistant', 'junior', 'representative', 'rep']
            has_role_keyword = any(keyword in query_lower for keyword in role_keywords)
            
            if has_role_keyword:
                stop_words = ['of', 'the', 'and', '&', 'a', 'an', 'in', 'on', 'at', 'to', 'for']
                keywords = [k.strip() for k in query_lower.split() 
                           if len(k.strip()) > 2 and k.strip() not in stop_words]
                
                if keywords:
                    query_obj = session.query(Employee)
                    for keyword in keywords:
                        query_obj = query_obj.filter(
                            func.lower(Employee.designation).like(f'%{keyword}%')
                        )
                    count = query_obj.count()
                    if count > 0:
                        return count
            
            # Strategy 5: Name (partial match)
            count = session.query(Employee).filter(
                (func.lower(Employee.full_name).like(f'%{query_lower}%')) |
                (func.lower(Employee.first_name).like(f'%{query_lower}%')) |
                (func.lower(Employee.last_name).like(f'%{query_lower}%'))
            ).count()
            
            return count
    
    def smart_search(self, query: str, limit: int = 10) -> List[Dict]:
        """Smart search that tries multiple strategies"""
        query_clean = query.strip()
        if not query_clean:
            logger.debug("smart_search: Empty query")
            return []
        
        logger.debug(f"smart_search: Searching for '{query_clean}'")
        
        # Strategy 1: Exact name match
        exact = self.search_by_exact_name(query_clean)
        if exact:
            logger.debug(f"smart_search: Found exact name match")
            return [exact]
        
        # Strategy 2: Employee ID (try both numeric and alphanumeric IDs)
        # First try exact employee ID match (works for both numeric and alphanumeric IDs like "cr_app5_test")
        logger.debug(f"smart_search: Trying employee ID search")
        emp = self.search_by_employee_id(query_clean)
        if emp:
            logger.debug(f"smart_search: Found employee ID match: {emp.get('full_name')}")
            return [emp]
        else:
            logger.debug(f"smart_search: No employee ID match")
        
        # Also try if it's all digits (legacy support)
        if query_clean.isdigit():
            # Already tried above, but keep for clarity
            pass
        
        # Strategy 3: Email (exact match or email-like format)
        if '@' in query_clean:
            emp = self.search_by_email(query_clean)
            if emp:
                return [emp]
        
        # Strategy 3b: Email-like format (firstname.lastname pattern) - search in email field
        # Pattern: contains a dot and looks like firstname.lastname (e.g., "rajib.bhowmik")
        if '.' in query_clean and not query_clean.startswith('.') and not query_clean.endswith('.'):
            # Check if it looks like an email format (alphanumeric with dot)
            if re.match(r'^[a-z0-9_]+\.[a-z0-9_]+$', query_clean.lower()):
                logger.debug(f"smart_search: Detected email-like format '{query_clean}', searching in email field")
                with self.get_session() as session:
                    # Search for email containing this pattern
                    emp = session.query(Employee).filter(
                        func.lower(Employee.email).like(f'%{query_clean.lower()}%')
                    ).first()
                    if emp:
                        logger.debug(f"smart_search: Found employee by email pattern: {emp.full_name}")
                        return [{
                            'id': emp.id,
                            'employee_id': emp.employee_id,
                            'full_name': emp.full_name,
                            'first_name': emp.first_name,
                            'last_name': emp.last_name,
                            'designation': emp.designation,
                            'department': emp.department,
                            'division': emp.division,
                            'email': emp.email,
                            'telephone': emp.telephone,
                            'pabx': emp.pabx,
                            'ip_phone': emp.ip_phone,
                            'mobile': emp.mobile,
                            'group_email': emp.group_email
                        }]
        
        # Strategy 4: Mobile number
        if re.match(r'^[\d\s-]+$', query_clean) and len(re.sub(r'[\s-]', '', query_clean)) >= 10:
            emp = self.search_by_mobile(query_clean)
            if emp:
                return [emp]
        
        # Strategy 5: Designation search (with optional location/branch filtering)
        role_keywords = [
            'head of', 'head', 'manager', 'director', 'officer', 'executive',
            'president', 'ceo', 'cfo', 'coo', 'svp', 'avp', 'vp', 'evp',
            'chief', 'senior', 'assistant', 'junior', 'representative', 'rep'
        ]
        query_lower = query_clean.lower()
        has_role_keyword = any(keyword in query_lower for keyword in role_keywords)
        
        if has_role_keyword:
            # Try to parse role + location pattern (e.g., "branch manager gulshan avenue")
            # Common patterns: "role location", "role of location", "role at location"
            location = None
            designation_part = query_clean
            
            # Pattern 1: "branch manager gulshan avenue" - location after role
            # Pattern 2: "manager of gulshan" - location after "of"
            # Pattern 3: "manager at gulshan" - location after "at"
            location_patterns = [
                r'(branch\s+)?manager\s+(of|at)\s+(.+?)(?:\s+branch)?$',
                r'(.*\s+)?manager\s+(of|at)\s+(.+?)(?:\s+branch)?$',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    location = match.group(3).strip() if match.lastindex >= 3 else None
                    if location:
                        # Extract just the role part (before "of" or "at")
                        role_match = re.search(r'^(.+?)\s+(of|at)\s+', query_clean, re.IGNORECASE)
                        if role_match:
                            designation_part = role_match.group(1).strip()
                        logger.info(f"[PHONEBOOK] Parsed role+location: designation='{designation_part}', location='{location}'")
                        break
            
            # If no explicit "of/at" pattern, try to detect location-like words after role
            if not location:
                # Common location/branch indicators
                location_indicators = ['gulshan', 'dhanmondi', 'uttara', 'banani', 'motijheel', 
                                      'branch', 'avenue', 'road', 'street', 'dhaka', 'chittagong']
                words = query_clean.lower().split()
                role_end_idx = None
                for i, word in enumerate(words):
                    if any(role_kw in ' '.join(words[:i+1]) for role_kw in role_keywords):
                        role_end_idx = i
                
                if role_end_idx is not None and role_end_idx + 1 < len(words):
                    # Check if remaining words look like a location
                    remaining = ' '.join(words[role_end_idx + 1:])
                    if any(indicator in remaining for indicator in location_indicators):
                        location = ' '.join(words[role_end_idx + 1:])
                        designation_part = ' '.join(words[:role_end_idx + 1])
                        logger.info(f"[PHONEBOOK] Detected location from remaining words: designation='{designation_part}', location='{location}'")
            
            # Search by designation with optional location filter
            designation_results = self.search_by_designation(designation_part, limit, location=location)
            if designation_results:
                dept_keywords = ['payment', 'banking', 'operations', 'ict', 'it', 'hr', 'finance']
                has_dept_keyword = any(keyword in query_lower for keyword in dept_keywords)
                if has_dept_keyword:
                    dept_results = self.search_by_department(query_clean, limit)
                    if dept_results:
                        # Combine and deduplicate
                        all_results = designation_results + dept_results
                        seen_ids = set()
                        combined = []
                        for r in all_results:
                            if r['employee_id'] not in seen_ids:
                                seen_ids.add(r['employee_id'])
                                combined.append(r)
                        return combined[:limit]
                return designation_results
        
        # Strategy 6: Full-text search
        results = self.search_by_name(query_clean, limit)
        if results:
            return results
        
        # Strategy 7: Partial name match
        return self.search_by_partial_name(query_clean, limit)
    
    def format_contact_info(self, employee: Dict) -> str:
        """Format employee contact information for display"""
        lines = []
        
        if employee.get('full_name'):
            lines.append(f"Name: {employee['full_name']}")
        
        if employee.get('designation'):
            lines.append(f"Designation: {employee['designation']}")
        
        if employee.get('department'):
            lines.append(f"Department: {employee['department']}")
        
        if employee.get('division'):
            lines.append(f"Division: {employee['division']}")
        
        if employee.get('email'):
            lines.append(f"Email: {employee['email']}")
        
        if employee.get('employee_id'):
            lines.append(f"Employee ID: {employee['employee_id']}")
        
        if employee.get('telephone'):
            lines.append(f"Telephone: {employee['telephone']}")
        
        if employee.get('pabx'):
            lines.append(f"PABX: {employee['pabx']}")
        
        if employee.get('mobile'):
            lines.append(f"Mobile: {employee['mobile']}")
        
        if employee.get('ip_phone'):
            lines.append(f"IP Phone: {employee['ip_phone']}")
        
        if employee.get('group_email'):
            lines.append(f"Group Email: {employee['group_email']}")
        
        return "\n".join(lines)


# Global instance
_phonebook_db = None

def get_phonebook_db(database_url: str = None) -> PhoneBookDB:
    """Get or create global phone book database instance"""
    global _phonebook_db
    if _phonebook_db is None:
        _phonebook_db = PhoneBookDB(database_url)
    return _phonebook_db


if __name__ == "__main__":
    # Test the database
    import sys
    
    db = PhoneBookDB()
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Importing phone book from: {file_path}")
        count = db.import_phonebook(file_path)
        print(f"✅ Imported {count} employees")
    else:
        # Test search
        print("Testing search...")
        results = db.smart_search("Tanvir Jubair")
        for emp in results:
            print("\n" + "="*50)
            print(db.format_contact_info(emp))

