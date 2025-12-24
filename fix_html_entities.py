"""
Fix HTML entities in phonebook database - Run inside Docker container
"""
import html
import sys
import os
sys.path.insert(0, '/app')
from app.services.phonebook_postgres import get_phonebook_db, Employee

db = get_phonebook_db()
session = db.get_session().__enter__()

try:
    employees = session.query(Employee).all()
    updated_count = 0
    
    for emp in employees:
        updated = False
        
        # Fix department
        if emp.department and '&amp;' in emp.department:
            emp.department = html.unescape(emp.department)
            updated = True
        
        # Fix division
        if emp.division and '&amp;' in emp.division:
            emp.division = html.unescape(emp.division)
            updated = True
        
        # Fix designation
        if emp.designation and '&amp;' in emp.designation:
            emp.designation = html.unescape(emp.designation)
            updated = True
        
        # Fix full_name
        if emp.full_name and '&amp;' in emp.full_name:
            emp.full_name = html.unescape(emp.full_name)
            updated = True
        
        if updated:
            updated_count += 1
            print(f"Fixed: {emp.full_name} - Department: {emp.department}")
    
    session.commit()
    print(f"\n✅ Fixed HTML entities in {updated_count} employee records")
    
except Exception as e:
    session.rollback()
    print(f"Error: {e}")
    raise
finally:
    session.close()

