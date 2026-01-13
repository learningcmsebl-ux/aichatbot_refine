"""
Test script to check if Visa Platinum annual fee can be retrieved
"""
import requests
import json
from datetime import date

def test_visa_platinum_annual_fee():
    """Test retrieving Visa Platinum annual fee directly from fee engine API"""
    # Fee engine URL
    url = "http://localhost:8003/fees/calculate"
    
    # Build request based on how fee_engine_client would process "tell me visa platinum card annual fee"
    today = date.today()
    if today.month < 1 or (today.month == 1 and today.day < 1):
        query_date = date(today.year, 1, 1)
    else:
        query_date = date(today.year, 1, 1)
        if today.month >= 7:
            query_date = date(today.year + 1, 1, 1)
    
    request_data = {
        "as_of_date": str(query_date),
        "charge_type": "ISSUANCE_ANNUAL_PRIMARY",
        "card_category": "CREDIT",
        "card_network": "VISA",
        "card_product": "Platinum",
        "currency": "BDT",
        "product_line": "CREDIT_CARDS"
    }
    
    print("Testing Visa Platinum Card Annual Fee")
    print("=" * 70)
    print(f"Request URL: {url}")
    print(f"Request Data:")
    print(json.dumps(request_data, indent=2))
    print("-" * 70)
    
    try:
        response = requests.post(url, json=request_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("[SUCCESS] Fee calculation successful!")
            print(f"\nResponse:")
            print(json.dumps(result, indent=2))
            print("-" * 70)
            
            if result.get("status") == "CALCULATED":
                fee_amount = result.get("fee_amount")
                fee_currency = result.get("fee_currency", "BDT")
                fee_basis = result.get("fee_basis", "PER_YEAR")
                
                print(f"\n[SUCCESS] RESULT: Visa Platinum Card Annual Fee")
                print(f"   Amount: {fee_amount} {fee_currency}")
                print(f"   Basis: {fee_basis}")
                try:
                    fee_decimal = float(fee_amount)
                    print(f"\n   Formatted: The primary card annual fee is {fee_decimal:,.0f} {fee_currency} (per year).")
                except:
                    print(f"\n   Formatted: The primary card annual fee is {fee_amount} {fee_currency} (per year).")
            else:
                print(f"\n[WARNING] Status: {result.get('status')}")
                print(f"   Message: {result.get('message', 'No message')}")
        else:
            print(f"[ERROR] Status code {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("[ERROR] Connection Error: Could not connect to fee engine service")
        print("   Make sure the fee engine is running on http://localhost:8003")
    except requests.exceptions.Timeout:
        print("[ERROR] Timeout: Fee engine service did not respond in time")
    except Exception as e:
        print(f"[ERROR] Error: {e}")

if __name__ == "__main__":
    test_visa_platinum_annual_fee()

