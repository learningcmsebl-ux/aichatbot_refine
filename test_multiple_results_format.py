"""Test multiple results formatting"""
from app.services.phonebook_postgres import get_phonebook_db

db = get_phonebook_db()
results = db.smart_search('tanvir', limit=5)

print('Sample multiple results format:')
print('=' * 60)
for i, emp in enumerate(results[:3], 1):
    print(f"{i}. {emp['full_name']}")
    if emp.get('designation'):
        print(f"   Designation: {emp['designation']}")
    if emp.get('department'):
        print(f"   Department: {emp['department']}")
    if emp.get('email'):
        print(f"   Email: {emp['email']}")
    if emp.get('employee_id'):
        print(f"   Employee ID: {emp['employee_id']}")
    if emp.get('mobile'):
        print(f"   Mobile: {emp['mobile']}")
    if emp.get('ip_phone'):
        print(f"   IP Phone: {emp['ip_phone']}")
    print()

