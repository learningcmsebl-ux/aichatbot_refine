"""
Script to get the total count of Priority Centers from the location service
"""
import httpx
import asyncio
import os
from typing import Optional

# Location service URL
LOCATION_SERVICE_URL = os.getenv("LOCATION_SERVICE_URL", "http://localhost:8004").rstrip("/")

async def get_priority_centers_count() -> Optional[int]:
    """Get total count of Priority Centers from location service"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{LOCATION_SERVICE_URL}/locations"
            params = {
                "type": "priority_center",
                "limit": 1000  # Get all priority centers
            }
            
            print(f"Querying location service: {url}")
            print(f"Parameters: {params}")
            print()
            
            resp = await client.get(url, params=params)
            
            if resp.status_code == 200:
                result = resp.json()
                total = result.get("total", 0)
                locations = result.get("locations", [])
                
                print("=" * 60)
                print("Priority Centers Information")
                print("=" * 60)
                print(f"Total Priority Centers: {total}")
                print()
                
                if locations:
                    print("Priority Centers by City:")
                    print("-" * 60)
                    
                    # Group by city
                    by_city = {}
                    for loc in locations:
                        city = loc.get("address", {}).get("city", "Unknown")
                        if city not in by_city:
                            by_city[city] = []
                        by_city[city].append(loc)
                    
                    for city, centers in sorted(by_city.items()):
                        print(f"{city}: {len(centers)} Priority Center(s)")
                        for center in centers:
                            name = center.get("name", "Unknown")
                            print(f"  - {name}")
                    print()
                    
                    print("=" * 60)
                    print(f"Summary: EBL has {total} Priority Center(s) in total")
                    print("=" * 60)
                else:
                    print("No Priority Centers found in the database.")
                
                return total
            else:
                print(f"Error: Status code {resp.status_code}")
                print(f"Response: {resp.text}")
                return None
                
    except httpx.TimeoutException:
        print("Error: Timeout connecting to location service")
        return None
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Getting Priority Centers count from location service...")
    print()
    count = asyncio.run(get_priority_centers_count())
    
    if count is not None:
        print()
        print("Query completed successfully!")
    else:
        print()
        print("Failed to get Priority Centers count.")








