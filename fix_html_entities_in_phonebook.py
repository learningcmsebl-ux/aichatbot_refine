"""
Fix HTML entities in phonebook database
Removes &amp; and other HTML entities from employee records
"""

import html
import logging
import os
import sys

# Try to import from bank_chatbot first (has proper config)
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot', 'app', 'services'))
    from phonebook_postgres import get_phonebook_db
except ImportError:
    # Fallback to root phonebook_postgres
    from phonebook_postgres import get_phonebook_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fix_html_entities():
    """Fix HTML entities in phonebook database"""
    db = get_phonebook_db()
    
    try:
        with db.get_session() as session:
            # Get all employees
            employees = session.query(db.Employee).all()
            
            updated_count = 0
            
            for emp in employees:
                updated = False
                
                # Fix department field
                if emp.department and '&amp;' in emp.department:
                    emp.department = html.unescape(emp.department)
                    updated = True
                    logger.info(f"Fixed department for {emp.full_name}: {emp.department}")
                
                # Fix division field
                if emp.division and '&amp;' in emp.division:
                    emp.division = html.unescape(emp.division)
                    updated = True
                    logger.info(f"Fixed division for {emp.full_name}: {emp.division}")
                
                # Fix designation field
                if emp.designation and '&amp;' in emp.designation:
                    emp.designation = html.unescape(emp.designation)
                    updated = True
                    logger.info(f"Fixed designation for {emp.full_name}: {emp.designation}")
                
                # Fix full_name field
                if emp.full_name and '&amp;' in emp.full_name:
                    emp.full_name = html.unescape(emp.full_name)
                    updated = True
                    logger.info(f"Fixed full_name for {emp.full_name}")
                
                if updated:
                    updated_count += 1
            
            session.commit()
            
            logger.info(f"Fixed HTML entities in {updated_count} employee records")
            print(f"\n✅ Fixed HTML entities in {updated_count} employee records")
            
            # Show example of fixed record
            if updated_count > 0:
                print("\nExample fixes:")
                example = session.query(db.Employee).filter(
                    db.Employee.department.like('%&%')
                ).first()
                if not example:
                    # Find one that was fixed
                    example = session.query(db.Employee).filter(
                        db.Employee.department.like('%Digital Technology%')
                    ).first()
                    if example:
                        print(f"  Name: {example.full_name}")
                        print(f"  Department: {example.department}")
                        print(f"  Designation: {example.designation}")
            
    except Exception as e:
        logger.error(f"Error fixing HTML entities: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    print("=" * 80)
    print("Fixing HTML Entities in Phonebook Database")
    print("=" * 80)
    print()
    
    fix_html_entities()
    
    print("\n" + "=" * 80)
    print("Fix Complete!")
    print("=" * 80)

