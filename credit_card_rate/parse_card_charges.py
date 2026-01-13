"""
Parser script to convert card charges schedule text file to structured JSON.
Run this script whenever the source text file is updated.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional

# File paths
TEXT_FILE = Path(__file__).parent / "CARD_CHARGES_AND_FEES_SCHEDULE_UPDATE_18.12.2025.txt"
JSON_OUTPUT = Path(__file__).parent / "card_charges.json"


def normalize_text(text: str) -> str:
    """Normalize text by removing extra spaces and newlines"""
    if not text:
        return ""
    return " ".join(text.split())


def parse_card_charges_file(file_path: Path) -> Dict:
    """Parse the card charges text file into structured data"""
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    records: List[Dict] = []
    current_charge_type: Optional[str] = None
    current_card: Optional[Dict] = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and separators
        if not line or line.startswith('='):
            i += 1
            continue
        
        # Detect charge type
        if line.startswith('CHARGE TYPE:'):
            current_charge_type = line.replace('CHARGE TYPE:', '').strip()
            current_card = None
            i += 1
            continue
        
        # Skip header lines
        if any(x in line for x in ['CARD CHARGES AND FEES SCHEDULE', 'Effective from']):
            i += 1
            continue
        
        # Parse card information
        if line.startswith('Card Category:'):
            # Save previous card if exists
            if current_card and current_charge_type:
                records.append(current_card.copy())
            
            category = line.replace('Card Category:', '').strip()
            current_card = {
                'category': category,
                'network': None,
                'product': None,
                'full_name': None,
                'charge_type': current_charge_type,
                'amount_raw': None,
            }
            i += 1
            continue
        
        if current_card is None:
            i += 1
            continue
        
        # Parse card network (can appear multiple times)
        if line.startswith('Card Network:'):
            network = line.replace('Card Network:', '').strip()
            # If network already exists, append (for cases like "Diners Club International" + "Diners Club")
            if current_card['network']:
                current_card['network'] = f"{current_card['network']}/{network}"
            else:
                current_card['network'] = network
            i += 1
            continue
        
        # Parse card product
        if line.startswith('Card Product:'):
            product = line.replace('Card Product:', '').strip()
            current_card['product'] = product
            i += 1
            continue
        
        # Parse full card name
        if line.startswith('Full Card Name:'):
            full_name = line.replace('Full Card Name:', '').strip()
            current_card['full_name'] = full_name
            i += 1
            continue
        
        # Parse charge amount/fee
        if line.startswith('Charge Amount/Fee:'):
            amount = line.replace('Charge Amount/Fee:', '').strip()
            current_card['amount_raw'] = amount
            
            # Save this card record
            if current_charge_type:
                records.append(current_card.copy())
                current_card = None
            i += 1
            continue
        
        i += 1
    
    # Save last card if exists
    if current_card and current_charge_type:
        records.append(current_card.copy())
    
    # Build structured output
    output = {
        'metadata': {
            'source_file': str(file_path.name),
            'total_records': len(records),
            'charge_types': sorted(set(r['charge_type'] for r in records if r.get('charge_type'))),
            'card_categories': sorted(set(r['category'] for r in records if r.get('category'))),
        },
        'records': records
    }
    
    return output


def main():
    """Main function to parse and save JSON"""
    print(f"Parsing card charges from: {TEXT_FILE}")
    
    try:
        data = parse_card_charges_file(TEXT_FILE)
        
        # Save to JSON
        JSON_OUTPUT.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        print(f"[OK] Successfully parsed {data['metadata']['total_records']} records")
        print(f"[OK] Found {len(data['metadata']['charge_types'])} charge types")
        print(f"[OK] JSON saved to: {JSON_OUTPUT}")
        print(f"[OK] File size: {JSON_OUTPUT.stat().st_size / 1024:.2f} KB")
        
    except Exception as e:
        print(f"[ERROR] Error parsing file: {e}")
        raise


if __name__ == "__main__":
    main()

