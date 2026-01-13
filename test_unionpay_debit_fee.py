"""
Test script to check Union Pay Debit card issuance fee
"""
import requests
import json
from datetime import date

def test_unionpay_debit_fee():
    """Test retrieving Union Pay Debit card issuance fee"""
    url = "http://localhost:8003/fees/calculate"
    
    today = date.today()
    if today.month < 1 or (today.month == 1 and today.day < 1):
        query_date = date(today.year, 1, 1)
    else:
        query_date = date(today.year, 1, 1)
        if today.month >= 7:
            query_date = date(today.year + 1, 1, 1)
    
    # Try different network variations
    network_variations = [
        "UnionPay International",  # Database value
        "UNIONPAY",  # What client extracts
        "UnionPay",
        "Union Pay"
    ]
    
    print("Testing Union Pay Debit Card Issuance Fee")
    print("=" * 70)
    
    for network in network_variations:
        request_data = {
            "as_of_date": str(query_date),
            "charge_type": "ISSUANCE_ANNUAL_PRIMARY",
            "card_category": "DEBIT",
            "card_network": network,
            "card_product": "UnionPay Classic",
            "currency": "BDT",
            "product_line": "CREDIT_CARDS"
        }
        
        print(f"\nTrying network: '{network}'")
        print(f"Request: {json.dumps(request_data, indent=2)}")
        
        try:
            response = requests.post(url, json=request_data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"Status: {result.get('status')}")
                if result.get("status") == "CALCULATED":
                    print(f"[SUCCESS] Found fee: {result.get('fee_amount')} {result.get('fee_currency')}")
                    print(f"Full response: {json.dumps(result, indent=2)}")
                    return
                else:
                    print(f"Message: {result.get('message')}")
            else:
                print(f"[ERROR] Status code {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"[ERROR] {e}")
    
    print("\n[FAILED] Could not find fee with any network variation")

if __name__ == "__main__":
    test_unionpay_debit_fee()

