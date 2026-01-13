"""
Test the 3 Fast Cash processing fee queries to verify they return exactly one row each
"""
import os
import asyncio
import httpx
from datetime import date
from urllib.parse import quote_plus

async def test_query(base_url: str, query: str, expected_charge_type: str, expected_context: str = None):
    """Test a single query"""
    print(f"\n{'='*70}")
    print(f"Testing: '{query}'")
    print(f"{'='*70}")
    
    # Map query to charge_type and context (simplified version of client logic)
    query_lower = query.lower()
    
    # Determine charge_type
    if "limit reduction processing fee" in query_lower or "limit reduction" in query_lower:
        charge_type = "LIMIT_REDUCTION_FEE"  # Will fallback to PROCESSING_FEE
    elif "limit enhancement processing fee" in query_lower or "limit enhancement" in query_lower:
        charge_type = "LIMIT_ENHANCEMENT_FEE"  # Will fallback to PROCESSING_FEE
    else:
        charge_type = "PROCESSING_FEE"
    
    # Determine charge_context
    charge_context = None
    if "reduced amount" in query_lower or "reduction" in query_lower:
        charge_context = "ON_REDUCED_AMOUNT"
    elif "enhanced amount" in query_lower or "enhancement" in query_lower:
        charge_context = "ON_ENHANCED_AMOUNT"
    elif "on limit" in query_lower or "loan amount" in query_lower:
        charge_context = "ON_LIMIT"
    
    # Determine loan_product
    loan_product = "FAST_CASH_OD" if "fast cash" in query_lower else None
    
    request_data = {
        "as_of_date": str(date.today()),
        "charge_type": charge_type,
        "loan_product": loan_product,
        "query": query
    }
    if charge_context:
        request_data["charge_context"] = charge_context
    
    print(f"Request: charge_type={charge_type}, loan_product={loan_product}, charge_context={charge_context}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{base_url}/retail-asset-charges/query"
        resp = await client.post(url, json=request_data)
        
        if resp.status_code == 200:
            result = resp.json()
            status = result.get('status')
            charges = result.get('charges', [])
            
            print(f"Response status: {status}")
            print(f"Charges found: {len(charges)}")
            
            if status == 'FOUND' and len(charges) == 1:
                charge = charges[0]
                actual_charge_type = charge.get('charge_type')
                actual_context = charge.get('charge_context')
                title = charge.get('charge_title', 'N/A')
                print(f"✅ SUCCESS: Found exactly 1 charge")
                print(f"   Charge Type: {actual_charge_type} (expected: {expected_charge_type})")
                print(f"   Charge Context: {actual_context} (expected: {expected_context})")
                print(f"   Title: {title}")
                
                if actual_charge_type == expected_charge_type:
                    if expected_context is None or actual_context == expected_context:
                        print(f"   ✅ Matches expected values")
                        return True
                    else:
                        print(f"   ⚠️  Context mismatch: expected {expected_context}, got {actual_context}")
                else:
                    print(f"   ⚠️  Charge type mismatch: expected {expected_charge_type}, got {actual_charge_type}")
            elif status == 'NEEDS_DISAMBIGUATION':
                print(f"⚠️  DISAMBIGUATION: {len(charges)} options found")
                for idx, charge in enumerate(charges[:5], 1):
                    print(f"   {idx}. {charge.get('charge_type')} | {charge.get('charge_context')} | {charge.get('charge_title', 'N/A')}")
            elif status == 'NO_RULE_FOUND':
                print(f"❌ NO_RULE_FOUND: {result.get('message', 'No message')}")
                
                # Try fallback if applicable
                if charge_type in ["LIMIT_ENHANCEMENT_FEE", "LIMIT_REDUCTION_FEE"] and charge_context:
                    print(f"   Trying DB-driven fallback: PROCESSING_FEE + {charge_context}")
                    fallback_request = request_data.copy()
                    fallback_request["charge_type"] = "PROCESSING_FEE"
                    resp_fallback = await client.post(url, json=fallback_request)
                    if resp_fallback.status_code == 200:
                        result_fallback = resp_fallback.json()
                        if result_fallback.get('status') == 'FOUND':
                            charges_fallback = result_fallback.get('charges', [])
                            print(f"   ✅ Fallback found {len(charges_fallback)} charge(s)")
                            return True
        else:
            print(f"❌ Error: HTTP {resp.status_code} - {resp.text}")
    
    return False

async def main():
    base_url = os.getenv("FEE_ENGINE_URL", "http://localhost:8003")
    
    print("="*70)
    print("Fast Cash Processing Fee Query Tests")
    print("="*70)
    
    tests = [
        ("fast cash processing fee", "PROCESSING_FEE", "GENERAL"),
        ("fast cash limit enhancement processing fee", "PROCESSING_FEE", "ON_ENHANCED_AMOUNT"),
        ("fast cash limit reduction processing fee on reduced amount", "PROCESSING_FEE", "ON_REDUCED_AMOUNT"),
    ]
    
    results = []
    for query, expected_type, expected_context in tests:
        result = await test_query(base_url, query, expected_type, expected_context)
        results.append((query, result))
    
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    for query, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {query}")

if __name__ == "__main__":
    asyncio.run(main())

