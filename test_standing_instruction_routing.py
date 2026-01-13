"""
Test script to verify Standing Instruction queries are routed correctly
"""

import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.services.chat_orchestrator import ChatOrchestrator

def test_standing_instruction_routing():
    """Test that Standing Instruction queries are detected as banking product queries"""
    
    orchestrator = ChatOrchestrator()
    
    test_queries = [
        "How can a Standing Instruction be cancelled?",
        "How to cancel standing instruction?",
        "What is standing instruction?",
        "How to setup SI?",
        "Can I cancel my SI?",
        "How do I cancel standing instructions?",
        "Tell me about standing instruction cancellation",
        "What is SI cancellation process?",
        "How to set up recurring payment?",
        "How to cancel automatic transfer?",
    ]
    
    print("=" * 70)
    print("Testing Standing Instruction Query Routing")
    print("=" * 70)
    print()
    
    all_passed = True
    
    for query in test_queries:
        is_banking_product = orchestrator._is_banking_product_query(query)
        is_contact = orchestrator._is_contact_info_query(query)
        
        status = "✓ PASS" if is_banking_product and not is_contact else "✗ FAIL"
        if not (is_banking_product and not is_contact):
            all_passed = False
        
        print(f"Query: {query}")
        print(f"  Banking Product: {is_banking_product}")
        print(f"  Contact Query: {is_contact}")
        print(f"  Status: {status}")
        print()
    
    print("=" * 70)
    if all_passed:
        print("✓ All tests PASSED - Standing Instruction queries route to LightRAG")
    else:
        print("✗ Some tests FAILED - Check routing logic")
    print("=" * 70)
    
    return all_passed

if __name__ == "__main__":
    try:
        # Set UTF-8 encoding for Windows
        if sys.platform == 'win32':
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        
        success = test_standing_instruction_routing()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




