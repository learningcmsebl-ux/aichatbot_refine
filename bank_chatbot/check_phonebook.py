#!/usr/bin/env python3
"""Quick script to check phonebook database"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from app.services.phonebook_postgres import get_phonebook_db, Employee
from sqlalchemy import func

def main():
    search_term = sys.argv[1] if len(sys.argv) > 1 else "cr_app5_test"
    
    db = get_phonebook_db()
    
    print("="*60)
    print(f"Checking phonebook database for: '{search_term}'")
    print("="*60)
    print()
    
    # Direct employee ID search
    print("1. Direct employee ID search:")
    result = db.search_by_employee_id(search_term)
    if result:
        print(f"   FOUND: {result['full_name']} (ID: {result['employee_id']})")
        print(f"   Email: {result.get('email', 'N/A')}")
        print(f"   Department: {result.get('department', 'N/A')}")
    else:
        print(f"   NOT FOUND")
    print()
    
    # Smart search
    print("2. Smart search:")
    results = db.smart_search(search_term, limit=10)
    print(f"   Found {len(results)} results")
    for r in results:
        print(f"   - {r['full_name']} (ID: {r['employee_id']})")
    print()
    
    # List all employees
    print("3. All employees in database:")
    with db.get_session() as session:
        total = session.query(Employee).count()
        print(f"   Total employees: {total}")
        print()
        print("   First 20 employees:")
        all_emps = session.query(Employee).limit(20).all()
        for i, e in enumerate(all_emps, 1):
            print(f"   {i}. {e.full_name} (ID: {e.employee_id})")
        print()
        
        # Check for similar IDs
        print("4. Employees with similar IDs (containing 'cr_app'):")
        similar = session.query(Employee).filter(
            Employee.employee_id.ilike('%cr_app%')
        ).all()
        for e in similar:
            print(f"   - {e.full_name} (ID: {e.employee_id})")
        print()
        
        # Search by name parts
        print("5. Searching by name parts:")
        name_parts = search_term.split('.')
        if len(name_parts) > 1:
            first_name = name_parts[0]
            last_name = name_parts[1]
            print(f"   Searching for first name: '{first_name}', last name: '{last_name}'")
            name_results = session.query(Employee).filter(
                (func.lower(Employee.first_name).like(f'%{first_name.lower()}%')) |
                (func.lower(Employee.last_name).like(f'%{last_name.lower()}%')) |
                (func.lower(Employee.full_name).like(f'%{first_name.lower()}%')) |
                (func.lower(Employee.full_name).like(f'%{last_name.lower()}%'))
            ).limit(10).all()
            if name_results:
                print(f"   Found {len(name_results)} employees with similar names:")
                for e in name_results:
                    print(f"   - {e.full_name} (ID: {e.employee_id}, Email: {e.email or 'N/A'})")
            else:
                print(f"   No employees found with name parts '{first_name}' or '{last_name}'")
        
        # Check if it might be an email format
        if '@' not in search_term and '.' in search_term:
            print()
            print("6. Checking if it might be an email format (searching in email field):")
            email_results = session.query(Employee).filter(
                func.lower(Employee.email).like(f'%{search_term.lower()}%')
            ).limit(5).all()
            if email_results:
                print(f"   Found {len(email_results)} employees with matching email:")
                for e in email_results:
                    print(f"   - {e.full_name} (ID: {e.employee_id}, Email: {e.email})")
            else:
                print(f"   No employees found with email containing '{search_term}'")

if __name__ == "__main__":
    main()
