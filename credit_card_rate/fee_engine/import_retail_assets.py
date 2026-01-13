"""
Import Retail Assets/Loans fees from Retail Asset Schedule of Charges.xlsx
"""
import pandas as pd
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from fee_engine_service import CardFeeMaster, SessionLocal

def parse_date(date_value):
    """Parse date from various formats"""
    if pd.isna(date_value):
        return datetime(2025, 11, 27).date()  # Default from file
    
    if isinstance(date_value, datetime):
        return date_value.date()
    
    date_str = str(date_value).strip()
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    
    return datetime(2025, 11, 27).date()  # Default

def truncate_string(value, max_length):
    """Truncate string to max_length if needed"""
    if value is None:
        return None
    value_str = str(value).strip()
    if len(value_str) > max_length:
        return value_str[:max_length]
    return value_str

def parse_complex_fee(fee_text):
    """
    Parse complex fee descriptions like:
    - "Up to Tk. 50 lakh → 0.575% or max Tk. 17,250; Above Tk. 50 lakh → 0.345% or max Tk. 23,000"
    - "0.575% on reduced amount; Min Tk. 575, Max Tk. 5,750"
    - "Free"
    """
    if pd.isna(fee_text) or not fee_text:
        return None, None, None, None, 'NONE'
    
    fee_text = str(fee_text).strip()
    
    # Check for "Free"
    if 'free' in fee_text.lower():
        return Decimal('0'), None, None, None, 'NONE'
    
    # Pattern 1: "X% or max Tk. Y" (whichever higher)
    pattern1 = r'(\d+\.?\d*)\s*%\s*(?:or|/)\s*max\s*Tk\.?\s*([\d,]+)'
    match1 = re.search(pattern1, fee_text, re.IGNORECASE)
    if match1:
        percent = Decimal(match1.group(1))
        max_amount = Decimal(match1.group(2).replace(',', ''))
        return percent, 'PERCENT', None, max_amount, 'WHICHEVER_HIGHER'
    
    # Pattern 2: "X% on amount; Min Tk. Y, Max Tk. Z"
    pattern2 = r'(\d+\.?\d*)\s*%\s*(?:on|of).*?Min\s*Tk\.?\s*([\d,]+).*?Max\s*Tk\.?\s*([\d,]+)'
    match2 = re.search(pattern2, fee_text, re.IGNORECASE)
    if match2:
        percent = Decimal(match2.group(1))
        min_amount = Decimal(match2.group(2).replace(',', ''))
        max_amount = Decimal(match2.group(3).replace(',', ''))
        return percent, 'PERCENT', min_amount, max_amount, 'WHICHEVER_HIGHER'
    
    # Pattern 3: "Up to X → Y%; Above X → Z%"
    pattern3 = r'Up\s+to\s+Tk\.?\s*([\d,]+)\s*[→-]\s*(\d+\.?\d*)\s*%\s*or\s*max\s*Tk\.?\s*([\d,]+).*?Above\s*Tk\.?\s*([\d,]+)\s*[→-]\s*(\d+\.?\d*)\s*%\s*or\s*max\s*Tk\.?\s*([\d,]+)'
    match3 = re.search(pattern3, fee_text, re.IGNORECASE)
    if match3:
        # For tiered structures, we'll create one record for the first tier
        # The second tier would need a separate record or complex logic
        percent = Decimal(match3.group(2))
        max_amount = Decimal(match3.group(3).replace(',', ''))
        return percent, 'PERCENT', None, max_amount, 'WHICHEVER_HIGHER'
    
    # Pattern 4: Simple percentage "X%"
    pattern4 = r'(\d+\.?\d*)\s*%'
    match4 = re.search(pattern4, fee_text)
    if match4:
        percent = Decimal(match4.group(1))
        return percent, 'PERCENT', None, None, 'NONE'
    
    # Pattern 5: Fixed amount "Tk. X" or "BDT X"
    pattern5 = r'(?:Tk\.?|BDT)\s*([\d,]+)'
    match5 = re.search(pattern5, fee_text, re.IGNORECASE)
    if match5:
        amount = Decimal(match5.group(1).replace(',', ''))
        return amount, 'BDT', None, None, 'NONE'
    
    # If no pattern matches, store as 0 with note
    return Decimal('0'), 'BDT', None, None, 'NOTE_BASED'

def normalize_charge_type(description):
    """Normalize charge type from description"""
    if pd.isna(description) or not description:
        return 'UNKNOWN'
    
    desc = str(description).strip().upper()
    # Replace spaces and special chars with underscores
    desc = re.sub(r'[^A-Z0-9_]', '_', desc)
    # Remove multiple underscores
    desc = re.sub(r'_+', '_', desc)
    # Limit length
    if len(desc) > 100:
        desc = desc[:100]
    return desc

def import_retail_assets():
    """Import Retail Assets/Loans fees from Excel file"""
    
    excel_path = Path(__file__).parent.parent.parent / "xls" / "Retail Asset Schedule of Charges.xlsx"
    
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        return
    
    print(f"\n{'='*70}")
    print("Importing Retail Assets/Loans Fees")
    print(f"{'='*70}")
    print(f"Reading: {excel_path.name}")
    
    try:
        df = pd.read_excel(excel_path, sheet_name='Retail Loan SOC')
        print(f"Found {len(df)} rows")
        
        db = SessionLocal()
        imported = 0
        skipped = 0
        
        try:
            for idx, row in df.iterrows():
                try:
                    # Skip empty rows
                    product_loan_type = row.get('Product / Loan Type', '')
                    if pd.isna(product_loan_type) or not str(product_loan_type).strip():
                        continue
                    
                    product_loan_type_str = str(product_loan_type).strip()
                    description = str(row.get('Description', '')).strip() if not pd.isna(row.get('Description')) else ''
                    charge_amount_text = row.get('Charge Amount (Including 15% VAT)', '')
                    effective_from = parse_date(row.get('Effective from', ''))
                    
                    charge_type = normalize_charge_type(description)
                    
                    # Parse complex fee structure
                    fee_value, fee_unit, min_fee_value, max_fee_value, condition_type = parse_complex_fee(charge_amount_text)
                    
                    # Determine fee_basis
                    fee_basis = 'PER_TXN'  # Default for loan processing fees
                    if 'processing' in description.lower():
                        fee_basis = 'PER_TXN'
                    elif 'annual' in description.lower() or 'yearly' in description.lower():
                        fee_basis = 'PER_YEAR'
                    elif 'monthly' in description.lower():
                        fee_basis = 'PER_MONTH'
                    
                    # Store original fee text in remarks if complex
                    remarks = None
                    if condition_type == 'NOTE_BASED' or ';' in str(charge_amount_text):
                        remarks = str(charge_amount_text).strip()
                    
                    # Create fee record (with truncation to prevent data errors)
                    fee_record = CardFeeMaster(
                        effective_from=effective_from,
                        effective_to=None,
                        charge_type=truncate_string(charge_type, 255),
                        card_category='ANY',  # Not applicable for Retail Assets
                        card_network='ANY',   # Not applicable for Retail Assets
                        card_product=truncate_string(product_loan_type_str, 100),
                        full_card_name=truncate_string(f"{product_loan_type_str} - {description}", 200),
                        fee_value=fee_value if fee_value is not None else Decimal('0'),
                        fee_unit=fee_unit if fee_unit else 'BDT',
                        fee_basis=fee_basis,
                        min_fee_value=min_fee_value,
                        min_fee_unit='BDT' if min_fee_value else None,
                        max_fee_value=max_fee_value,
                        free_entitlement_count=None,
                        condition_type=condition_type,
                        note_reference=None,
                        priority=100,
                        status='ACTIVE',
                        remarks=remarks,
                        product_line='RETAIL_ASSETS'
                    )
                    
                    db.add(fee_record)
                    imported += 1
                    
                    if imported % 10 == 0:
                        db.commit()
                        print(f"  Imported {imported} records...")
                        
                except Exception as e:
                    print(f"  Error importing row {idx}: {e}")
                    skipped += 1
                    continue
            
            db.commit()
            print(f"\nImport complete!")
            print(f"  Imported: {imported} records")
            print(f"  Skipped: {skipped} records")
            
        except Exception as e:
            db.rollback()
            print(f"Error during import: {e}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import_retail_assets()


