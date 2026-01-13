"""
Test the actual server to see if routing is working
"""
import requests
import json

def test_server_routing():
    """Test the server's routing for corporate customer queries"""
    
    url = "http://localhost:8001/api/chat"
    
    query = "In the case of corporate customers, processing is subject to prior email confirmation."
    
    payload = {
        "query": query,
        "session_id": "test-routing-check",
        "stream": False
    }
    
    print("=" * 70)
    print(f"Testing Server Routing")
    print("=" * 70)
    print(f"Query: '{query}'")
    print(f"URL: {url}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        server_response = result.get("response", "")
        
        print("Server Response:")
        print("-" * 70)
        print(server_response)
        print("-" * 70)
        print()
        
        # Check if it's the phonebook error message
        if "employee directory" in server_response.lower() or "phone book database" in server_response.lower():
            print("PROBLEM: Query was routed to PHONEBOOK (incorrect)")
            print("   The server is NOT using the updated routing code.")
            print("   Please ensure:")
            print("   1. Server was fully restarted (not just reloaded)")
            print("   2. All old processes were killed")
            print("   3. Server logs show the new version message")
        elif "corporate" in server_response.lower() or "email confirmation" in server_response.lower():
            print("SUCCESS: Query was routed to LIGHTRAG (correct)")
            print("   The server is using the updated routing code.")
        else:
            print("UNKNOWN: Response doesn't clearly indicate routing")
            print("   Check server logs for routing decisions")
            
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")
        print("   Make sure the server is running on port 8001")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_server_routing()

