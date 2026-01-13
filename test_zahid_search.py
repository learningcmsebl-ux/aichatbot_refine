"""Test phonebook search for 'zahid'"""
from phonebook_postgres import get_phonebook_db
from dotenv import load_dotenv
import os

load_dotenv()

# Get phonebook database
db = get_phonebook_db()

# Search for "zahid"
search_term = "zahid"
results = db.smart_search(search_term, limit=10)

print(f"\n{'='*70}")
print(f"Search Results for: '{search_term}'")
print(f"{'='*70}")
print(f"Found {len(results)} results:\n")

for i, emp in enumerate(results, 1):
    print(f"{i}. {emp['full_name']}")
    if emp.get('designation'):
        print(f"   Designation: {emp['designation']}")
    if emp.get('department'):
        print(f"   Department: {emp['department']}")
    if emp.get('email'):
        print(f"   Email: {emp['email']}")
    if emp.get('mobile'):
        print(f"   Mobile: {emp['mobile']}")
    if emp.get('telephone'):
        print(f"   Telephone: {emp['telephone']}")
    if emp.get('ip_phone'):
        print(f"   IP Phone: {emp['ip_phone']}")
    print()

# Get total count
total_count = db.count_search_results(search_term)
print(f"Total matches: {total_count}")
print(f"{'='*70}\n")

