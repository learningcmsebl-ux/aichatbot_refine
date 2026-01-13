"""
Test routing detection for corporate customer queries
"""
import sys
import os

# Add the bank_chatbot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.services.chat_orchestrator import ChatOrchestrator

def test_query(query: str):
    """Test a query against the routing logic"""
    orchestrator = ChatOrchestrator()
    
    print("=" * 60)
    print(f"Testing Query: '{query}'")
    print("=" * 60)
    print()
    
    # Test all detection methods
    is_banking_product = orchestrator._is_banking_product_query(query)
    is_compliance = orchestrator._is_compliance_query(query)
    is_contact = orchestrator._is_contact_info_query(query)
    is_phonebook = orchestrator._is_phonebook_query(query)
    is_employee = orchestrator._is_employee_query(query)
    is_small_talk = orchestrator._is_small_talk(query)
    
    print(f"Banking Product Query: {is_banking_product}")
    print(f"Compliance Query: {is_compliance}")
    print(f"Contact Query: {is_contact}")
    print(f"Phonebook Query: {is_phonebook}")
    print(f"Employee Query: {is_employee}")
    print(f"Small Talk: {is_small_talk}")
    print()
    
    # Determine routing
    if is_banking_product or is_compliance:
        print("=> Should route to: LIGHTRAG")
    elif is_contact or is_phonebook or is_employee:
        print("=> Should route to: PHONEBOOK")
    elif is_small_talk:
        print("=> Should route to: OPENAI (no LightRAG)")
    else:
        print("=> Should route to: LIGHTRAG (default)")
    print()

if __name__ == "__main__":
    test_queries = [
        "In the case of corporate customers, processing is subject to prior email confirmation.",
        "For corporate customers, whose email confirmation is required before processing?",
        "corporate customers email confirmation",
        "tell me about corporate customers",
    ]
    
    for query in test_queries:
        test_query(query)
        print()

