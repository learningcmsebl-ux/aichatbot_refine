"""Test script to debug interest rate search"""

import json
import re
from pathlib import Path

JSON_PATH = Path(__file__).parent / "card_charges.json"

def _normalize(text: str) -> str:
    """Normalize text for matching"""
    if not text:
        return ""
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return ' '.join(text.split())

# Load data
data = json.loads(JSON_PATH.read_text(encoding='utf-8'))
CARD_CHARGES = data.get('records', [])

query = "interest rate visa classic"
query_norm = _normalize(query)
query_lower = query_norm.lower()
is_interest_rate_query = "interest" in query_lower and "rate" in query_lower

print(f"Query: {query}")
print(f"Query normalized: {query_norm}")
print(f"Is interest rate query: {is_interest_rate_query}")
print()

# Find Interest Rate records for Classic card
matches = []
for record in CARD_CHARGES:
    charge_type = record.get('charge_type', '')
    card_name = record.get('full_name', '')
    product = record.get('product')
    network = record.get('network')
    category = record.get('category')
    
    charge_norm = _normalize(charge_type)
    
    # Check if it's an Interest Rate charge type
    if "interest" in charge_norm and "rate" in charge_norm:
        # Check if card matches
        product_norm = _normalize(product or "")
        network_norm = _normalize(network or "")
        
        print(f"Found Interest Rate record:")
        print(f"  Charge Type: {charge_type}")
        print(f"  Card: {card_name}")
        print(f"  Product: {product}, Network: {network}")
        print(f"  Product norm: '{product_norm}'")
        print(f"  Network norm: '{network_norm}'")
        print(f"  Query norm: '{query_norm}'")
        print(f"  Product in query: {product_norm in query_norm if product_norm else False}")
        print(f"  Network in query: {network_norm in query_norm if network_norm else False}")
        
        if "classic" in card_name.lower() or (product_norm and product_norm in query_norm) or (network_norm and network_norm in query_norm):
            matches.append(record)
            print(f"  -> MATCH!")
        else:
            print(f"  -> NO MATCH")
        print()

print(f"\nTotal matches: {len(matches)}")
for m in matches:
    print(f"  - {m['full_name']}: {m['charge_type']} = {m['amount_raw']}")

