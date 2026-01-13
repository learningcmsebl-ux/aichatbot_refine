"""
Test script to simulate how fee_engine_client processes Union Pay Debit query
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the settings module
class MockSettings:
    FEE_ENGINE_URL = "http://localhost:8003"

# Mock the app.core.config module
sys.modules['app'] = type(sys)('app')
sys.modules['app.core'] = type(sys)('app.core')
sys.modules['app.core.config'] = type(sys)('app.core.config')
sys.modules['app.core.config'].settings = MockSettings()

from bank_chatbot.app.services.fee_engine_client import FeeEngineClient

async def test_unionpay_debit():
    """Test Union Pay Debit card issuance fee query"""
    client = FeeEngineClient()
    
    # Test query
    query = "What is the issuance fee for a Union pay Debit card ?"
    print(f"Testing query: '{query}'")
    print("-" * 70)
    
    result = await client.calculate_fee(query)
    
    if result:
        print("[SUCCESS] Fee calculation successful!")
        print(f"Status: {result.get('status')}")
        print(f"Fee Amount: {result.get('fee_amount')}")
        print(f"Fee Currency: {result.get('fee_currency')}")
        print(f"Fee Basis: {result.get('fee_basis')}")
        print(f"Charge Type: {result.get('charge_type')}")
        print("-" * 70)
        
        # Format response
        formatted = client.format_fee_response(result, query)
        print("Formatted Response:")
        print(formatted)
    else:
        print("[ERROR] Fee calculation failed - no result returned")

if __name__ == "__main__":
    asyncio.run(test_unionpay_debit())

