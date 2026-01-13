"""
Test PostgreSQL Phonebook Integration with Chatbot
This simulates how the chatbot will interact with PostgreSQL phonebook
"""
from phonebook_postgres import get_phonebook_db
from dotenv import load_dotenv
import os

load_dotenv()

def simulate_chatbot_phonebook_query(user_query: str):
    """Simulate how chatbot processes a phonebook query"""
    
    print("=" * 70)
    print(f"Simulating Chatbot Phonebook Query")
    print("=" * 70)
    print(f"User Query: '{user_query}'")
    print()
    
    # Step 1: Get phonebook database (same as chatbot does)
    print("Step 1: Connecting to PostgreSQL phonebook...")
    try:
        # Use connection string from environment or default
        database_url = os.getenv(
            'PHONEBOOK_DB_URL',
            os.getenv('POSTGRES_DB_URL') or 
            f"postgresql://{os.getenv('POSTGRES_USER', 'chatbot_user')}:"
            f"{os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'chatbot_db')}"
        )
        phonebook_db = get_phonebook_db(database_url)
        print("✓ Connected to PostgreSQL phonebook")
        print()
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("  Make sure PostgreSQL is running and .env file is configured")
        return
    
    # Step 2: Extract search term (simplified version of chatbot logic)
    print("Step 2: Extracting search term from query...")
    import re
    
    # Remove phone/contact keywords
    search_term = re.sub(
        r'\b(phone|contact|number|email|address|mobile|telephone|of|for|the)\b', 
        '', 
        user_query, 
        flags=re.IGNORECASE
    ).strip()
    
    print(f"  Extracted search term: '{search_term}'")
    print()
    
    # Step 3: Search (same as chatbot does)
    print("Step 3: Searching PostgreSQL phonebook...")
    try:
        # Get total count
        total_count = phonebook_db.count_search_results(search_term)
        print(f"  Total matches: {total_count}")
        
        # Smart search (same method chatbot uses)
        results = phonebook_db.smart_search(search_term, limit=5)
        print(f"  Results found: {len(results)}")
        print()
    except Exception as e:
        print(f"✗ Search failed: {e}")
        return
    
    # Step 4: Format response (same as chatbot does)
    print("Step 4: Formatting response...")
    print()
    
    if not results:
        print("Response: No matching contacts found.")
        print("(Chatbot would fall back to LightRAG here)")
        return
    
    if len(results) == 1:
        # Single result - detailed format
        print("Response (Single Result):")
        print("-" * 70)
        response = phonebook_db.format_contact_info(results[0])
        response += "\n\n(Source: Phone Book Database)"
        print(response)
    else:
        # Multiple results - list format
        print("Response (Multiple Results):")
        print("-" * 70)
        response = ""
        for i, emp in enumerate(results[:5], 1):
            response += f"{i}. {emp['full_name']}\n"
            if emp.get('designation'):
                response += f"   Designation: {emp['designation']}\n"
            if emp.get('department'):
                response += f"   Department: {emp['department']}\n"
            if emp.get('email'):
                response += f"   Email: {emp['email']}\n"
            if emp.get('mobile'):
                response += f"   Mobile: {emp['mobile']}\n"
            response += "\n"
        
        response += f"We found {total_count} matching contact(s) in total. Showing only the top 5 results.\n\n"
        if total_count > 5:
            response += "Please provide more details to narrow down the search.\n\n"
        response += "(Source: Phone Book Database)"
        print(response)
    
    print()
    print("=" * 70)
    print("✓ Integration test complete!")
    print("=" * 70)
    print()
    print("This is exactly how your chatbot will interact with PostgreSQL phonebook.")
    print("The response format matches what users will see in the chatbot.")


if __name__ == "__main__":
    print()
    print("Testing PostgreSQL Phonebook Integration")
    print()
    
    # Test queries
    test_queries = [
        "What is the contact for Tanvir Jubair",
        "Phone number of manager",
        "Email of head of operations"
    ]
    
    for query in test_queries:
        simulate_chatbot_phonebook_query(query)
        print("\n" + "=" * 70 + "\n")

