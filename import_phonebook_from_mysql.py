"""
Import Phonebook Data from MySQL to PostgreSQL
Connects to MySQL database, executes query, and imports into PostgreSQL phonebook
"""

import pymysql
import logging
import os
import html
from typing import List, Dict, Optional
from datetime import datetime

# Import PostgreSQL phonebook
try:
    from phonebook_postgres import get_phonebook_db, PhoneBookDB
except ImportError:
    # Try bank_chatbot version
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot', 'app', 'services'))
    from phonebook_postgres import get_phonebook_db, PhoneBookDB

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MySQLPhonebookImporter:
    """Import phonebook data from MySQL to PostgreSQL"""
    
    def __init__(self, mysql_config: Dict, postgres_db: Optional[PhoneBookDB] = None):
        """
        Initialize MySQL importer
        
        Args:
            mysql_config: Dictionary with MySQL connection details
                {
                    'host': '192.168.3.57',
                    'port': 3306,
                    'user': 'tanvir',
                    'password': 'tanvir',
                    'database': 'ebl_home'
                }
            postgres_db: Optional PhoneBookDB instance (creates new if None)
        """
        self.mysql_config = mysql_config
        self.mysql_connection = None
        self.postgres_db = postgres_db or get_phonebook_db()
        
    def connect_mysql(self) -> bool:
        """Establish MySQL connection"""
        try:
            self.mysql_connection = pymysql.connect(
                host=self.mysql_config['host'],
                port=self.mysql_config.get('port', 3306),
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                database=self.mysql_config['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10
            )
            logger.info(f"Connected to MySQL at {self.mysql_config['host']}:{self.mysql_config.get('port', 3306)}/{self.mysql_config['database']}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            return False
    
    def disconnect_mysql(self):
        """Close MySQL connection"""
        if self.mysql_connection:
            self.mysql_connection.close()
            logger.info("MySQL connection closed")
    
    def fetch_mysql_data(self) -> List[Dict]:
        """
        Fetch employee data from MySQL using the provided query
        
        Returns:
            List of employee records as dictionaries
        """
        query = """
        SELECT DISTINCT
            t2.meta_value AS Employee_Name,
            t1.post_title AS Employee_ID,
            t14.name AS Department,
            COALESCE(
                t_root.name,      -- Level 1 parent
                t_parent.name,    -- Level 2 parent
                t14.name          -- Level 3 (original category)
            ) AS Division,
            t3.meta_value AS Designation,
            t4.meta_value AS Email,
            TRIM(t7.meta_value) AS IP_EXT,
            t8.meta_value AS Mobile
        FROM ebl_posts t1
        LEFT JOIN ebl_postmeta t2 ON t1.ID = t2.post_id AND t2.meta_key = 'employee_name'
        LEFT JOIN ebl_postmeta t3 ON t1.ID = t3.post_id AND t3.meta_key = 'designation'
        LEFT JOIN ebl_postmeta t4 ON t1.ID = t4.post_id AND t4.meta_key = 'email_address'
        LEFT JOIN ebl_postmeta t7 ON t1.ID = t7.post_id AND t7.meta_key = 'ip'
        LEFT JOIN ebl_postmeta t8 ON t1.ID = t8.post_id AND t8.meta_key = 'mobile'
        LEFT JOIN ebl_term_relationships tr ON t1.ID = tr.object_id
        LEFT JOIN ebl_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id
        LEFT JOIN ebl_terms t14 ON t14.term_id = tt.term_id
        LEFT JOIN ebl_term_taxonomy tt_parent ON tt.parent = tt_parent.term_taxonomy_id
        LEFT JOIN ebl_terms t_parent ON t_parent.term_id = tt_parent.term_id
        LEFT JOIN ebl_term_taxonomy tt_root ON tt_parent.parent = tt_root.term_taxonomy_id
        LEFT JOIN ebl_terms t_root ON t_root.term_id = tt_root.term_id
        WHERE t1.post_status = 'publish'
          AND t1.post_title <> ''
          AND t1.post_title NOT IN ('000.', '0000')
          AND TRIM(t7.meta_value) <> ''
          AND TRIM(t7.meta_value) <> '-'
          AND LENGTH(TRIM(t1.post_title)) > 1
          AND LENGTH(t1.post_title) = 4
          AND t14.name NOT LIKE '%Uncategorized%'
        """
        
        try:
            with self.mysql_connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                # Normalize and transform data
                employees = []
                for row in results:
                    # Extract name parts and decode HTML entities
                    full_name = html.unescape((row.get('Employee_Name') or '').strip())
                    name_parts = full_name.split() if full_name else []
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    employee = {
                        'employee_id': (row.get('Employee_ID') or '').strip(),
                        'full_name': full_name,
                        'first_name': first_name,
                        'last_name': last_name,
                        'designation': html.unescape((row.get('Designation') or '').strip()),
                        'department': html.unescape((row.get('Department') or '').strip()),
                        'division': html.unescape((row.get('Division') or '').strip()),
                        'email': (row.get('Email') or '').strip(),
                        'ip_phone': (row.get('IP_EXT') or '').strip(),
                        'mobile': (row.get('Mobile') or '').strip(),
                        'telephone': '',  # Not in MySQL query
                        'pabx': '',  # Not in MySQL query
                        'group_email': ''  # Not in MySQL query
                    }
                    
                    # Only add if we have at least name and employee_id
                    if employee['full_name'] and employee['employee_id']:
                        employees.append(employee)
                
                logger.info(f"Fetched {len(employees)} employee records from MySQL")
                return employees
                
        except Exception as e:
            logger.error(f"Error fetching data from MySQL: {e}")
            return []
    
    def import_to_postgres(self, employees: List[Dict], clear_existing: bool = False) -> Dict[str, int]:
        """
        Import employees into PostgreSQL phonebook
        
        Args:
            employees: List of employee dictionaries
            clear_existing: If True, clear existing data before import
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'total': len(employees),
            'inserted': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
        
        try:
            with self.postgres_db.get_session() as session:
                # Clear existing if requested
                if clear_existing:
                    deleted = session.query(self.postgres_db.Employee).delete()
                    session.commit()
                    logger.info(f"Cleared {deleted} existing employee records")
                
                # Import employees
                for emp_data in employees:
                    try:
                        # Check if employee exists (by employee_id or email)
                        existing = None
                        if emp_data.get('employee_id'):
                            existing = session.query(self.postgres_db.Employee).filter(
                                self.postgres_db.Employee.employee_id == emp_data['employee_id']
                            ).first()
                        elif emp_data.get('email'):
                            existing = session.query(self.postgres_db.Employee).filter(
                                self.postgres_db.Employee.email == emp_data['email']
                            ).first()
                        
                        if existing:
                            # Update existing record
                            for key, value in emp_data.items():
                                if hasattr(existing, key) and value:
                                    setattr(existing, key, value)
                            stats['updated'] += 1
                        else:
                            # Insert new record
                            employee = self.postgres_db.Employee(**emp_data)
                            session.add(employee)
                            stats['inserted'] += 1
                            
                    except Exception as e:
                        logger.warning(f"Error importing employee {emp_data.get('full_name', 'unknown')}: {e}")
                        stats['errors'] += 1
                        continue
                
                session.commit()
            
            logger.info(
                f"Import complete: {stats['inserted']} inserted, "
                f"{stats['updated']} updated, {stats['errors']} errors, "
                f"{stats['total']} total from MySQL"
            )
            
        except Exception as e:
            logger.error(f"Error importing to PostgreSQL: {e}")
            raise
        
        return stats
    
    def sync(self, clear_existing: bool = False) -> Dict[str, int]:
        """
        Complete sync process: fetch from MySQL and import to PostgreSQL
        
        Args:
            clear_existing: If True, clear existing PostgreSQL data before import
            
        Returns:
            Dictionary with sync statistics
        """
        try:
            # Connect to MySQL
            if not self.connect_mysql():
                raise Exception("Failed to connect to MySQL")
            
            # Fetch data
            logger.info("Fetching data from MySQL...")
            employees = self.fetch_mysql_data()
            
            if not employees:
                logger.warning("No employees fetched from MySQL")
                return {'total': 0, 'inserted': 0, 'updated': 0, 'errors': 0, 'skipped': 0}
            
            # Import to PostgreSQL
            logger.info("Importing data to PostgreSQL...")
            stats = self.import_to_postgres(employees, clear_existing=clear_existing)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error during sync: {e}", exc_info=True)
            raise
        finally:
            self.disconnect_mysql()


def main():
    """Main execution function"""
    # MySQL configuration
    mysql_config = {
        'host': '192.168.3.57',
        'port': 3306,
        'user': 'tanvir',
        'password': 'tanvir',
        'database': 'ebl_home'
    }
    
    # PostgreSQL connection (uses environment variables or defaults)
    postgres_db = get_phonebook_db()
    
    # Create importer
    importer = MySQLPhonebookImporter(mysql_config, postgres_db)
    
    try:
        # Perform sync
        logger.info("Starting phonebook sync from MySQL to PostgreSQL...")
        stats = importer.sync(clear_existing=True)  # Clear existing data
        
        # Print summary
        print("\n" + "=" * 80)
        print("PHONEBOOK SYNC SUMMARY")
        print("=" * 80)
        print(f"Total Records from MySQL: {stats['total']}")
        print(f"Inserted: {stats['inserted']}")
        print(f"Updated: {stats['updated']}")
        print(f"Errors: {stats['errors']}")
        print("=" * 80 + "\n")
        
        logger.info("Phonebook sync completed successfully!")
        
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        print(f"\n❌ Sync failed: {e}\n")


if __name__ == "__main__":
    main()

