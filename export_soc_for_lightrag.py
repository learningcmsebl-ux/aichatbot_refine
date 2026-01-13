import pandas as pd
import sys
from pathlib import Path
import json

# Set UTF-8 encoding for output
sys.stdout.reconfigure(encoding='utf-8')

# Read the Excel file
file_path = r'E:\Chatbot_refine\xls\soc.xlsx'
df = pd.read_excel(file_path)

# Output files
text_output_file = r'E:\Chatbot_refine\xls\card_charges_schedule.txt'
json_output_file = r'E:\Chatbot_refine\xls\card_charges.json'

# Extract header information
header_row = df.iloc[0, 0] if pd.notna(df.iloc[0, 0]) else ""
effective_date = header_row if "Effective" in str(header_row) else ""

# Extract card categories from row 1 (index 1)
card_categories = {}
for idx in range(1, len(df.columns)):
    val = df.iloc[1, idx]
    if pd.notna(val) and str(val).strip():
        val_str = str(val).strip()
        if val_str in ["Credit Card", "Debit Card", "Prepaid Card"]:
            card_categories[idx] = val_str

# Extract card networks/variants from row 2 (index 2)
card_networks = {}
for idx in range(1, len(df.columns)):
    val = df.iloc[2, idx]
    if pd.notna(val) and str(val).strip():
        val_str = str(val).strip().replace('\n', ' ')
        card_networks[idx] = val_str

# Extract card product names from row 3 (index 3)
card_products = {}
for idx in range(1, len(df.columns)):
    val = df.iloc[3, idx]
    if pd.notna(val) and str(val).strip():
        val_str = str(val).strip().replace('\n', ' ')
        card_products[idx] = val_str

# Build card information mapping
card_info = {}
for col_idx in range(1, len(df.columns)):
    # Find category
    category = None
    for cat_idx in sorted(card_categories.keys()):
        if col_idx >= cat_idx:
            category = card_categories[cat_idx]
        else:
            break
    
    network = card_networks.get(col_idx, "")
    product = card_products.get(col_idx, "")
    
    # Build full card name
    card_name_parts = []
    if category:
        card_name_parts.append(category)
    if network:
        card_name_parts.append(network)
    if product:
        card_name_parts.append(product)
    
    full_card_name = " ".join(card_name_parts).strip()
    if not full_card_name:
        full_card_name = f"Card Column {col_idx}"
    
    card_info[col_idx] = {
        'category': category or "Unknown",
        'network': network,
        'product': product,
        'full_name': full_card_name
    }

# Start building the text output and JSON records
output_lines = []
records = []

# Header (text)
output_lines.append("=" * 80)
output_lines.append("CARD CHARGES AND FEES SCHEDULE")
output_lines.append("=" * 80)
if effective_date:
    output_lines.append(f"\n{effective_date}\n")
output_lines.append("")

# Process each charge/fee row (starting from row 4, index 4)
for row_idx in range(4, len(df)):
    charge_type = df.iloc[row_idx, 0]
    
    if pd.isna(charge_type) or str(charge_type).strip() == "":
        continue
    
    charge_type_str = str(charge_type).strip()
    
    # Skip if it's a header or separator
    if any(x in charge_type_str for x in ["Effective", "Credit Card", "Debit Card", "Prepaid Card", "VISA", "Mastercard"]):
        continue
    
    # Start a new section for this charge type in text output
    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append(f"CHARGE TYPE: {charge_type_str}")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # Extract values for each card column
    for col_idx in range(1, len(df.columns)):
        value = df.iloc[row_idx, col_idx]
        
        if pd.isna(value) or str(value).strip() == "" or str(value).strip() == "-":
            continue
        
        card = card_info.get(col_idx, {})
        value_str = str(value).strip()
        
        # Text output
        output_lines.append(f"Card Category: {card.get('category', 'Unknown')}")
        if card.get('network'):
            output_lines.append(f"Card Network: {card['network']}")
        if card.get('product'):
            output_lines.append(f"Card Product: {card['product']}")
        output_lines.append(f"Full Card Name: {card.get('full_name', 'Unknown Card')}")
        output_lines.append(f"Charge Amount/Fee: {value_str}")
        output_lines.append("")

        # JSON record for microservice
        record = {
            "card_full_name": card.get("full_name", "Unknown Card"),
            "category": card.get("category", "Unknown"),
            "network": card.get("network") or None,
            "product": card.get("product") or None,
            "charge_type": charge_type_str,
            "amount_raw": value_str,
        }
        records.append(record)
    
    output_lines.append("")

# Write text file (for LightRAG)
with open(text_output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

# Write JSON file
with open(json_output_file, 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

text_size_kb = Path(text_output_file).stat().st_size / 1024
json_size_kb = Path(json_output_file).stat().st_size / 1024

print(f"✓ Exported text schedule to: {text_output_file} ({text_size_kb:.2f} KB)")
print(f"✓ Exported JSON data to: {json_output_file} ({json_size_kb:.2f} KB)")
print(f"✓ Total JSON records: {len(records)}")
print("\nFiles are ready for LightRAG ingestion.")
