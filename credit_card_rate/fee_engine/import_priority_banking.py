"""
Import Priority Banking fees from Priority_SOC_Converted.xlsx
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

def parse_date(date_str):
    """Parse date from sheet title or default"""
    # Default from sheet title: "Effective July 2025"
    return datetime(2025, 7, 1).date()

def truncate_string(value, max_length):
    """Truncate string to max_length if needed"""
    if value is None:
        return None
    value_str = str(value).strip()
    if len(value_str) > max_length:
        return value_str[:max_length]
    return value_str

def parse_fee(fee_str):
    """Parse fee from string like 'Free', 'BDT 500', '500', etc."""
    if pd.isna(fee_str) or not fee_str:
        return Decimal('0'), 'BDT'
    
    fee_str = str(fee_str).strip()
    
    # Check for "Free"
    if 'free' in fee_str.lower():
        return Decimal('0'), 'BDT'
    
    # Extract currency
    currency = 'BDT'
    if 'USD' in fee_str.upper() or '$' in fee_str:
        currency = 'USD'
    
    # Extract number
    fee_str = re.sub(r'[^\d.,]', '', fee_str)
    fee_str = fee_str.replace(',', '').strip()
    
    try:
        return Decimal(fee_str), currency
    except:
        return Decimal('0'), 'BDT'

def normalize_charge_type(service_category, service_item):
    """Normalize charge type from service category and item"""
    if pd.isna(service_item) or not str(service_item).strip():
        return 'UNKNOWN'
    
    charge_type = str(service_item).strip().upper()
    # Replace spaces and special chars with underscores
    charge_type = re.sub(r'[^A-Z0-9_]', '_', charge_type)
    # Remove multiple underscores
    charge_type = re.sub(r'_+', '_', charge_type)
    return charge_type

def import_priority_banking():
    """Import Priority Banking fees from Excel file"""
    
    excel_path = Path(__file__).parent.parent.parent / "xls" / "Priority_SOC_Converted.xlsx"
    
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        return
    
    print(f"\n{'='*70}")
    print("Importing Priority Banking Fees")
    print(f"{'='*70}")
    print(f"Reading: {excel_path.name}")
    
    try:
        df = pd.read_excel(excel_path, sheet_name='Priority SOC', header=None)
        print(f"Found {len(df)} rows (raw)")
        
        # Find header row (usually row 1)
        header_row = None
        for idx in range(min(5, len(df))):
            row_values = df.iloc[idx].values
            if any('Service Category' in str(v) for v in row_values if pd.notna(v)):
                header_row = idx
                break
        
        if header_row is None:
            print("Error: Could not find header row")
            return
        
        # Re-read with proper header
        df = pd.read_excel(excel_path, sheet_name='Priority SOC', header=header_row)
        
        # Rename columns based on what we found
        expected_cols = ['Service Category', 'Service Item', 'Details or condtions', 'Fee']
        if len(df.columns) >= 4:
            df.columns = expected_cols[:len(df.columns)]
        else:
            print("Error: Unexpected column structure")
            return
        
        print(f"Processing {len(df)} data rows")
        
        db = SessionLocal()
        imported = 0
        skipped = 0
        
        try:
            for idx, row in df.iterrows():
                try:
                    # Skip empty rows
                    service_item = row.get('Service Item', '')
                    if pd.isna(service_item) or not str(service_item).strip():
                        continue
                    
                    service_category = str(row.get('Service Category', '')).strip() if not pd.isna(row.get('Service Category')) else ''
                    service_item_str = str(service_item).strip()
                    details = str(row.get('Details or condtions', '')).strip() if not pd.isna(row.get('Details or condtions')) else None
                    fee_str = row.get('Fee', '')
                    
                    charge_type = normalize_charge_type(service_category, service_item_str)
                    fee_value, fee_unit = parse_fee(fee_str)
                    
                    # Determine fee_basis (default to PER_YEAR for Priority Banking services)
                    fee_basis = 'PER_YEAR'
                    if 'transaction' in service_item_str.lower() or 'transfer' in service_item_str.lower():
                        fee_basis = 'PER_TXN'
                    elif 'monthly' in details.lower() if details else False:
                        fee_basis = 'PER_MONTH'
                    
                    # Create fee record (with truncation to prevent data errors)
                    fee_record = CardFeeMaster(
                        effective_from=parse_date(None),
                        effective_to=None,
                        charge_type=truncate_string(charge_type, 255),
                        card_category='ANY',  # Not applicable for Priority Banking
                        card_network='ANY',   # Not applicable for Priority Banking
                        card_product=truncate_string('Priority Banking', 100),
                        full_card_name=truncate_string(f"Priority Banking - {service_item_str}", 200),
                        fee_value=fee_value,
                        fee_unit=fee_unit,
                        fee_basis=fee_basis,
                        min_fee_value=None,
                        min_fee_unit=None,
                        max_fee_value=None,
                        free_entitlement_count=None,
                        condition_type='NONE',
                        note_reference=None,
                        priority=100,
                        status='ACTIVE',
                        remarks=details,
                        product_line='PRIORITY_BANKING'
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
    import_priority_banking()


