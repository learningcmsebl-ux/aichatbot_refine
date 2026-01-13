"""
Script to find Priority Center data from various sources
Checks phonebook, documents, and provides guidance on adding data to LightRAG
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from bank_chatbot.app.services.phonebook_postgres import PhoneBookDB
    from bank_chatbot.app.core.config import settings
    PHONEBOOK_AVAILABLE = True
except ImportError:
    PHONEBOOK_AVAILABLE = False
    print("⚠ Phonebook module not available")

def search_phonebook_for_priority_centers(city: str = None):
    """Search phonebook for Priority Center related entries"""
    if not PHONEBOOK_AVAILABLE:
        print("Phonebook not available")
        return []
    
    try:
        phonebook = PhoneBookDB()
        
        # Search by unit/department containing "Priority Center"
        results = phonebook.search_by_department("Priority Center", limit=100)
        
        if city:
            # Filter by city if provided
            city_lower = city.lower()
            results = [
                r for r in results 
                if city_lower in r.get('unit', '').lower() or 
                   city_lower in r.get('division', '').lower() or
                   city_lower in r.get('address', '').lower()
            ]
        
        return results
    except Exception as e:
        print(f"Error searching phonebook: {e}")
        return []

def analyze_priority_center_data(city: str = "Narayanganj"):
    """Analyze Priority Center data for a specific city"""
    print("=" * 60)
    print(f"Finding Priority Center Data for {city} City")
    print("=" * 60)
    print()
    
    # Step 1: Check phonebook
    print("1. Checking phonebook for Priority Center entries...")
    phonebook_results = search_phonebook_for_priority_centers(city)
    
    if phonebook_results:
        print(f"   ✓ Found {len(phonebook_results)} Priority Center related entries in phonebook")
        
        # Group by unit/division
        units = {}
        for result in phonebook_results:
            unit = result.get('unit', 'Unknown')
            if unit not in units:
                units[unit] = []
            units[unit].append(result)
        
        print(f"\n   Priority Center Units/Divisions found:")
        for unit, employees in units.items():
            print(f"      - {unit}: {len(employees)} employee(s)")
            if city.lower() in unit.lower():
                print(f"        ✓ This unit appears to be in {city}")
    else:
        print("   ✗ No Priority Center entries found in phonebook")
    print()
    
    # Step 2: Provide guidance
    print("2. Data Sources to Check:")
    print("   - EBL website (branch locator)")
    print("   - Annual reports (may have Priority Center counts)")
    print("   - Internal branch database")
    print("   - Customer service department")
    print()
    
    # Step 3: Instructions for adding data
    print("3. To Add Priority Center Data to LightRAG:")
    print(f"   a. Edit add_priority_centers_to_lightrag.py")
    print(f"   b. Update PRIORITY_CENTERS_DATA dictionary with {city} data:")
    print(f"      PRIORITY_CENTERS_DATA['{city}'] = {{")
    print(f"          'count': <actual_count>,  # e.g., 1, 2, 3")
    print(f"          'centers': [")
    print(f"              {{")
    print(f"                  'name': 'Priority Center Name',")
    print(f"                  'address': 'Full address in {city}',")
    print(f"                  'phone': 'Phone number',")
    print(f"                  'email': 'Email if available'")
    print(f"              }}")
    print(f"          ],")
    print(f"          'notes': 'Description'")
    print(f"      }}")
    print(f"   c. Run: python add_priority_centers_to_lightrag.py --city {city}")
    print()
    
    return phonebook_results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Find Priority Center data from various sources")
    parser.add_argument(
        "--city",
        type=str,
        default="Narayanganj",
        help="City to search for (default: Narayanganj)"
    )
    
    args = parser.parse_args()
    
    results = analyze_priority_center_data(args.city)
    
    print("=" * 60)
    print("Analysis Complete")
    print("=" * 60)
    print(f"\nNext Steps:")
    print(f"1. Gather actual Priority Center data for {args.city} City")
    print(f"2. Update add_priority_centers_to_lightrag.py with the data")
    print(f"3. Run the script to add data to LightRAG")
    print(f"4. Test with: 'How many Priority centers are there in {args.city} City?'")









