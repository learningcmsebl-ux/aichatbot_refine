"""
Test the actual query that's failing
"""
import sys
import os

# Add the bank_chatbot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.services.chat_orchestrator import ChatOrchestrator

def test_actual_query():
    """Test the exact query that's failing"""
    orchestrator = ChatOrchestrator()
    
    query = "In the case of corporate customers, processing is subject to prior email confirmation."
    
    print("=" * 70)
    print(f"Testing Query: '{query}'")
    print("=" * 70)
    print()
    
    # Test all detection methods in the order they're checked
    print("1. Banking Product Query Check:")
    is_banking_product = orchestrator._is_banking_product_query(query)
    print(f"   Result: {is_banking_product}")
    print()
    
    print("2. Compliance Query Check:")
    is_compliance = orchestrator._is_compliance_query(query)
    print(f"   Result: {is_compliance}")
    print()
    
    print("3. Contact Query Check:")
    is_contact = orchestrator._is_contact_info_query(query)
    print(f"   Result: {is_contact}")
    if is_contact:
        # Debug why it's detected as contact
        query_lower = query.lower().strip()
        email_process_keywords = [
            'email confirmation', 'email verification', 'email requirement',
            'email required', 'email process', 'email policy', 'email procedure',
            'email workflow', 'email approval', 'email notification',
            'send email', 'email sent', 'email received', 'email delivery',
            'email template', 'email format', 'email content',
            'prior email confirmation', 'prior confirmation', 'subject to prior',
            'subject to email', 'processing subject to', 'confirmation required',
            'prior email', 'email prior'
        ]
        print(f"   Query lower: '{query_lower}'")
        for keyword in email_process_keywords:
            if keyword in query_lower:
                print(f"   ✓ Matches email process keyword: '{keyword}'")
        print()
    
    print("4. Phonebook Query Check:")
    is_phonebook = orchestrator._is_phonebook_query(query)
    print(f"   Result: {is_phonebook}")
    print()
    
    print("5. Employee Query Check:")
    is_employee = orchestrator._is_employee_query(query)
    print(f"   Result: {is_employee}")
    print()
    
    print("6. Small Talk Check:")
    is_small_talk = orchestrator._is_small_talk(query)
    print(f"   Result: {is_small_talk}")
    print()
    
    # Determine routing based on actual code logic
    print("=" * 70)
    print("ROUTING DECISION:")
    print("=" * 70)
    
    if is_banking_product or is_compliance:
        print("=> Should route to: LIGHTRAG (banking product/compliance detected)")
    elif is_contact or is_phonebook or is_employee:
        print("=> Should route to: PHONEBOOK (contact/phonebook/employee detected)")
        if is_contact:
            print("   ⚠ PROBLEM: Query incorrectly detected as contact query!")
    elif is_small_talk:
        print("=> Should route to: OPENAI (small talk)")
    else:
        print("=> Should route to: LIGHTRAG (default)")
    print()

if __name__ == "__main__":
    test_actual_query()





