"""Direct test of search logic"""

import json
import re
from pathlib import Path

JSON_PATH = Path(__file__).parent / "card_charges.json"

def _normalize(text: str) -> str:
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
print(f"Is interest rate query: {is_interest_rate_query}")
print()

matches = []
for record in CARD_CHARGES:
    charge_type = record.get('charge_type', '')
    card_name = record.get('full_name', '')
    product = record.get('product')
    network = record.get('network')
    category = record.get('category')
    
    charge_norm = _normalize(charge_type)
    
    # For interest rate queries, ONLY include Interest Rate charge types
    if is_interest_rate_query:
        if "interest" not in charge_norm or "rate" not in charge_norm:
            continue
        charge_type_matches = True
    else:
        charge_type_matches = True  # Simplified for test
    
    if not charge_type_matches:
        continue
    
    # Simple card matching
    product_norm = _normalize(product or "")
    network_norm = _normalize(network or "")
    
    card_matches = False
    if product_norm and product_norm in query_norm:
        card_matches = True
    elif network_norm and network_norm in query_norm:
        card_matches = True
    
    if not card_matches and "classic" not in card_name.lower():
        continue
    
    if "classic" in card_name.lower() and "interest" in charge_norm and "rate" in charge_norm:
        matches.append(record)
        print(f"MATCH: {card_name} - {charge_type} = {record.get('amount_raw')}")

print(f"\nTotal matches: {len(matches)}")

