"""
Script to add Priority Center information to LightRAG knowledge base
Supports multiple cities including Narayanganj, Sylhet, Dhaka, Chittagong, etc.
"""
import sys
from connect_lightrag import LightRAGClient

# LightRAG configuration
BASE_URL = "http://localhost:9262"
API_KEY = "MyCustomLightRagKey456"
KNOWLEDGE_BASE = "ebl_website"  # Default knowledge base

# Priority Center data for different cities
# Updated with actual data from location service
PRIORITY_CENTERS_DATA = {
    "Narayanganj": {
        "count": None,  # Part of "Sylhet and Narayangonj" combined center
        "centers": [],
        "notes": "Priority Centers in Narayanganj City provide premium banking services to Priority Banking customers."
    },
    "Sylhet": {
        "count": None,  # Part of "Sylhet and Narayangonj" combined center
        "centers": [],
        "notes": "Priority Centers in Sylhet City provide premium banking services to Priority Banking customers."
    },
    "Dhaka": {
        "count": 1,
        "centers": [
            {
                "name": "Dhaka Priority Center",
                "address": "Dhaka",
                "phone": "Contact Eastern Bank PLC. for phone number",
                "email": "Contact Eastern Bank PLC. for email"
            }
        ],
        "notes": "Priority Centers in Dhaka City provide premium banking services to Priority Banking customers."
    },
    "Chittagong": {
        "count": 1,
        "centers": [
            {
                "name": "Chittagong Priority Center",
                "address": "Chittagong",
                "phone": "Contact Eastern Bank PLC. for phone number",
                "email": "Contact Eastern Bank PLC. for email"
            }
        ],
        "notes": "Priority Centers in Chittagong City provide premium banking services to Priority Banking customers."
    }
}

# Total Priority Centers count for EBL
TOTAL_PRIORITY_CENTERS_COUNT = 4
TOTAL_PRIORITY_CENTERS_INFO = f"""
EBL Priority Centers - Total Count

Eastern Bank PLC. has a total of {TOTAL_PRIORITY_CENTERS_COUNT} Priority Centers across Bangladesh.

Priority Centers are located in the following cities/regions:
1. Dhaka - 1 Priority Center
2. Chittagong - 1 Priority Center
3. North and South - 1 Priority Center
4. Sylhet and Narayangonj - 1 Priority Center

Priority Centers provide premium banking services to Priority Banking customers, offering personalized service, dedicated relationship managers, and exclusive banking privileges.

For specific addresses, contact information, or to find the nearest Priority Center, please contact Eastern Bank PLC. directly or visit the bank's website.
"""

def format_priority_center_info(city_data: dict, city_name: str) -> str:
    """Format Priority Center information for a specific city"""
    count = city_data.get("count")
    centers = city_data.get("centers", [])
    notes = city_data.get("notes", "")
    
    info = f"""
EBL Priority Centers Information - {city_name} City

{notes}

"""
    
    if count is not None:
        info += f"There are {count} Priority Center(s) in {city_name} City.\n\n"
    else:
        info += f"Priority Centers in {city_name} City:\n\n"
    
    if centers:
        info += "Priority Center Details:\n"
        for i, center in enumerate(centers, 1):
            info += f"\n{i}. {center.get('name', 'Priority Center')}\n"
            if center.get('address'):
                info += f"   Address: {center['address']}\n"
            if center.get('phone'):
                info += f"   Phone: {center['phone']}\n"
            if center.get('email'):
                info += f"   Email: {center['email']}\n"
    else:
        info += f"Please contact Eastern Bank PLC. directly for the most accurate and up-to-date information about Priority Centers in {city_name} City.\n"
    
    return info.strip()

def add_priority_center_info(city: str = None):
    """
    Add Priority Center information to LightRAG
    
    Args:
        city: Specific city to add (e.g., "Narayanganj", "Sylhet"). 
              If None, adds information for all cities.
    """
    # Check LightRAG health first
    client = LightRAGClient(base_url=BASE_URL, api_key=API_KEY)
    
    print("Checking LightRAG connection...")
    try:
        health = client.health_check()
        print(f"LightRAG Health: {health}")
        if health.get("status") != "ok":
            print("⚠ Warning: LightRAG health check did not return 'ok' status")
    except Exception as e:
        print(f"⚠ Warning: Could not check LightRAG health: {e}")
        return None
    
    # Determine which cities to process
    cities_to_process = [city] if city and city in PRIORITY_CENTERS_DATA else list(PRIORITY_CENTERS_DATA.keys())
    
    results = []
    for city_name in cities_to_process:
        print(f"\n{'='*60}")
        print(f"Processing Priority Centers for {city_name} City")
        print(f"{'='*60}")
        
        city_data = PRIORITY_CENTERS_DATA[city_name]
        priority_centers_info = format_priority_center_info(city_data, city_name)
        
        print(f"\nFormatted information:\n{priority_centers_info[:200]}...\n")
        
        try:
            # Insert the information with knowledge base specified
            result = client.insert_text(
                text=priority_centers_info,
                file_source=f"priority_centers_{city_name.lower()}.txt",
                knowledge_base=KNOWLEDGE_BASE
            )
            print(f"✓ Successfully added Priority Center information for {city_name} to LightRAG")
            print(f"   Knowledge Base: {KNOWLEDGE_BASE}")
            results.append((city_name, True, result))
        except Exception as e:
            print(f"✗ Error adding information for {city_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((city_name, False, str(e)))
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add Priority Center information to LightRAG")
    parser.add_argument(
        "--city",
        type=str,
        help="Specific city to add (e.g., Narayanganj, Sylhet). If not specified, adds all cities.",
        choices=list(PRIORITY_CENTERS_DATA.keys()) + [None],
        default=None
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Adding Priority Center information to LightRAG")
    print("=" * 60)
    print(f"Knowledge Base: {KNOWLEDGE_BASE}")
    print(f"LightRAG URL: {BASE_URL}")
    if args.city:
        print(f"City: {args.city}")
    else:
        print("Cities: All cities")
    print()
    
    results = add_priority_center_info(city=args.city)
    
    if results:
        print("\n" + "=" * 60)
        print("Upload Summary")
        print("=" * 60)
        
        success_count = sum(1 for _, success, _ in results if success)
        total_count = len(results)
        
        for city_name, success, result in results:
            status = "✓ SUCCESS" if success else "✗ FAILED"
            print(f"{status}: {city_name}")
            if not success:
                print(f"   Error: {result}")
        
        print(f"\nTotal: {success_count}/{total_count} cities processed successfully")
        
        if success_count > 0:
            print("\n" + "=" * 60)
            print("✓ Upload completed!")
            print("=" * 60)
            print("\nNote: LightRAG will automatically process and index the data.")
            print("It may take a few moments for the data to become searchable.")
            print("\nYou can test queries like:")
            if args.city:
                print(f'  "How many Priority centers are there in {args.city} City?"')
            else:
                print('  "How many Priority centers are there in Narayanganj City?"')
                print('  "How many Priority centers are there in Sylhet City?"')
        else:
            print("\n" + "=" * 60)
            print("✗ All uploads failed")
            print("=" * 60)
            print("\nPlease check:")
            print("  1. LightRAG is running on port 9262")
            print("  2. API key is correct")
            print("  3. Knowledge base name is correct")
            print("  4. Network connectivity to LightRAG")
    else:
        print("\n" + "=" * 60)
        print("✗ Upload failed")
        print("=" * 60)
        print("\nPlease check:")
        print("  1. LightRAG is running on port 9262")
        print("  2. API key is correct")
        print("  3. Knowledge base name is correct")
        print("  4. Network connectivity to LightRAG")

