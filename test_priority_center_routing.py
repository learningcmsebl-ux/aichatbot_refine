"""
Test script to verify priority center queries are routed to location service
"""
import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.services.chat_orchestrator import ChatOrchestrator

def test_priority_center_detection():
    """Test that priority center queries are detected as location queries"""
    orchestrator = ChatOrchestrator()
    
    test_queries = [
        "how many priority center does ebl have",
        "how many priority centers does ebl have",
        "how many priority center does eastern bank have",
        "number of priority centers",
        "count of priority centers",
        "total priority centers",
        "priority center count",
        "priority centers in dhaka",
        "where are priority centers",
        "location of priority centers",
        "address of priority center",
        "tell me about priority center",
        "priority center information",
        "priority center locations"
    ]
    
    print("=" * 70)
    print("Testing Priority Center Query Detection")
    print("=" * 70)
    print()
    
    location_queries = []
    non_location_queries = []
    
    for query in test_queries:
        is_location = orchestrator._is_location_query(query)
        status = "[LOCATION]" if is_location else "[NOT LOCATION]"
        
        if is_location:
            location_queries.append(query)
            print(f"{status}: '{query}'")
        else:
            non_location_queries.append(query)
            print(f"{status}: '{query}'")
    
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total queries tested: {len(test_queries)}")
    print(f"Detected as location queries: {len(location_queries)}")
    print(f"NOT detected as location queries: {len(non_location_queries)}")
    print()
    
    if non_location_queries:
        print("WARNING: These queries were NOT detected as location queries:")
        for q in non_location_queries:
            print(f"  - '{q}'")
        print()
        print("These queries may be routed to LightRAG instead of location service!")
    else:
        print("SUCCESS: All priority center queries are correctly detected as location queries!")
        print("  They will be routed to the location service, not LightRAG.")
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    test_priority_center_detection()








