"""Debug what context is being sent to LLM for Army/Air Force/Navy Platinum query"""
import asyncio
import sys
sys.path.insert(0, 'bank_chatbot')

async def test_fee_engine_and_context():
    from app.services.fee_engine_client import FeeEngineClient
    from app.services.chat_orchestrator import ChatOrchestrator
    
    query = "How many free Supplementary credit card for Army/Air Force/ Navy Platinum"
    
    print("="*70)
    print("Testing Fee Engine Client")
    print("="*70)
    
    fee_client = FeeEngineClient()
    fee_result = await fee_client.calculate_fee(query)
    
    if fee_result:
        print(f"\nFee Engine Result:")
        print(f"  Status: {fee_result.get('status')}")
        print(f"  Charge Type: {fee_result.get('charge_type')}")
        print(f"  Card Product: {fee_result.get('card_product')}")
        print(f"  Fee Amount: {fee_result.get('fee_amount')}")
        
        formatted = fee_client.format_fee_response(fee_result, query)
        print(f"\nFormatted Response:")
        print("-"*70)
        print(formatted)
        print("-"*70)
    else:
        print("\n[ERROR] Fee engine returned None")
        return
    
    print("\n" + "="*70)
    print("Testing Chat Orchestrator Context Generation")
    print("="*70)
    
    orchestrator = ChatOrchestrator()
    context = await orchestrator._get_card_rates_context(query)
    
    print(f"\nContext sent to LLM:")
    print("-"*70)
    try:
        print(context.encode('utf-8', errors='replace').decode('utf-8'))
    except:
        print(repr(context))
    print("-"*70)
    
    # Check if context mentions "2" or "two"
    context_lower = context.lower()
    if "2" in context or "two" in context_lower or "first 2" in context_lower:
        print("\n[OK] Context correctly mentions 2 free supplementary cards")
    elif "1" in context or "one" in context_lower:
        print("\n[ERROR] Context incorrectly mentions 1 free supplementary card")
    else:
        print("\n[WARNING] Context doesn't clearly state the number of free cards")

if __name__ == "__main__":
    asyncio.run(test_fee_engine_and_context())

