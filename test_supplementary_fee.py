"""
Test script to verify VISA Platinum supplementary card fee response
"""
import requests
import json

def test_supplementary_fee():
    url = "http://localhost:8001/api/chat/stream"
    
    payload = {
        "query": "Credit Card VISA Platinum supplementary annual fee",
        "session_id": "test-supplementary-fee",
        "knowledge_base": None,
        "stream": True
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("Testing VISA Platinum supplementary card fee query...")
        print(f"URL: {url}")
        print(f"Query: {payload['query']}")
        print("\n" + "="*70)
        print("RESPONSE:")
        print("="*70 + "\n")
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            # Read streaming response
            full_response = ""
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    full_response += chunk
                    print(chunk, end='', flush=True)
            
            print("\n\n" + "="*70)
            print("VERIFICATION:")
            print("="*70)
            
            # Check if response includes both pieces of information
            has_first_two = any(phrase in full_response.lower() for phrase in [
                "first 2", "first two", "1st and 2nd", "first and second"
            ])
            has_free = any(phrase in full_response.lower() for phrase in [
                "free", "bdt 0", "no annual fee"
            ])
            has_third_plus = any(phrase in full_response.lower() for phrase in [
                "3rd", "third", "2,300", "2300", "starting from the 3rd"
            ])
            
            print(f"✓ Mentions first 2 cards: {has_first_two}")
            print(f"✓ Mentions free/BDT 0: {has_free}")
            print(f"✓ Mentions 3rd+ cards fee (BDT 2,300): {has_third_plus}")
            
            if has_first_two and has_free and has_third_plus:
                print("\n✅ SUCCESS: Response includes both fee tiers!")
            else:
                print("\n❌ INCOMPLETE: Response is missing some information:")
                if not has_first_two:
                    print("  - Missing: mention of first 2 cards")
                if not has_free:
                    print("  - Missing: mention of free/BDT 0")
                if not has_third_plus:
                    print("  - Missing: mention of 3rd+ card fee (BDT 2,300)")
        else:
            print(f"\n❌ Error: Status code {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")

if __name__ == "__main__":
    test_supplementary_fee()

