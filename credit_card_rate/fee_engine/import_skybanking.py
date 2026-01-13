"""
Import Skybanking fees from Fees and Charges against issuing Certificates through EBL Skybanking...xlsx
"""
import pandas as pd
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from fee_engine_service import CardFeeMaster, SessionLocal

def parse_date(date_str):
    """Parse date string like '27/11/2025'"""
    if pd.isna(date_str) or not date_str:
        return datetime(2025, 11, 27).date()  # Default from file
    
    if isinstance(date_str, datetime):
        return date_str.date()
    
    date_str = str(date_str).strip()
    formats = ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y']
    
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

def parse_fee_amount(fee_value):
    """Parse fee amount, handling 'Variable' and numeric values"""
    if pd.isna(fee_value):
        return Decimal('0')
    
    fee_str = str(fee_value).strip().upper()
    
    if 'VARIABLE' in fee_str:
        return None  # Will be stored as 0 but condition_type will indicate variable
    
    # Remove currency symbols
    fee_str = fee_str.replace('BDT', '').replace('USD', '').replace('$', '').strip()
    fee_str = fee_str.replace(',', '').strip()
    
    try:
        return Decimal(fee_str)
    except:
        return Decimal('0')

def normalize_fee_basis(basis):
    """Normalize fee basis"""
    if pd.isna(basis):
        return 'PER_TXN'
    
    basis = str(basis).strip().upper()
    
    if 'YEARLY' in basis or 'YEAR' in basis or 'ANNUAL' in basis:
        return 'PER_YEAR'
    elif 'MONTHLY' in basis or 'MONTH' in basis:
        return 'PER_MONTH'
    elif 'TRANSACTION' in basis or 'TXN' in basis or 'REQUEST' in basis:
        return 'PER_TXN'
    elif 'VISIT' in basis:
        return 'PER_VISIT'
    elif 'OUTSTANDING' in basis:
        return 'ON_OUTSTANDING'
    
    return 'PER_TXN'  # Default

def normalize_charge_type(charge_type):
    """Normalize charge type"""
    if pd.isna(charge_type):
        return 'UNKNOWN'
    
    charge_type = str(charge_type).strip().upper()
    return charge_type.replace(' ', '_')

def parse_condition(conditional, condition_desc):
    """Parse condition type and description"""
    if pd.isna(conditional) or str(conditional).strip().upper() == 'NO':
        return 'NONE', None
    
    # Check if it's a free entitlement
    condition_desc_str = str(condition_desc).strip().lower() if not pd.isna(condition_desc) else ''
    
    if 'free' in condition_desc_str:
        # Try to extract number of free items
        # For now, set as NOTE_BASED if there's a condition description
        return 'NOTE_BASED', str(condition_desc).strip() if not pd.isna(condition_desc) else None
    
    return 'NOTE_BASED', str(condition_desc).strip() if not pd.isna(condition_desc) else None

def import_skybanking():
    """Import Skybanking fees from Excel file"""
    
    excel_path = Path(__file__).parent.parent.parent / "xls" / "Fees and Charges against issuing Certificates through EBL Skybanking in Schedule of Charges (SOC) (Effective from 27th November 2025.).xlsx"
    
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        return
    
    print(f"\n{'='*70}")
    print("Importing Skybanking Fees")
    print(f"{'='*70}")
    print(f"Reading: {excel_path.name}")
    
    try:
        df = pd.read_excel(excel_path, sheet_name='Skybanking_Fees')
        print(f"Found {len(df)} rows")
        
        db = SessionLocal()
        imported = 0
        skipped = 0
        
        try:
            for idx, row in df.iterrows():
                try:
                    # Skip empty rows
                    if pd.isna(row.get('CHARGE TYPE')) or not str(row.get('CHARGE TYPE')).strip():
                        continue
                    
                    charge_type = normalize_charge_type(row.get('CHARGE TYPE', ''))
                    product = str(row.get(' PRODUCT', 'Skybanking')).strip() if not pd.isna(row.get(' PRODUCT')) else 'Skybanking'
                    product_name = str(row.get('PRODUCT NAME', '')).strip() if not pd.isna(row.get('PRODUCT NAME')) else None
                    fee_amount = parse_fee_amount(row.get('FEE AMOUNT', ''))
                    fee_unit = str(row.get('FEE UNIT', 'BDT')).strip().upper() if not pd.isna(row.get('FEE UNIT')) else 'BDT'
                    fee_basis = normalize_fee_basis(row.get('FEE BASIS', ''))
                    effective_from = parse_date(row.get('EFFECTIVE FROM', ''))
                    effective_to = parse_date(row.get('EFFECTIVE TO', '')) if not pd.isna(row.get('EFFECTIVE TO')) else None
                    status = str(row.get('STATUS', 'ACTIVE')).strip().upper() if not pd.isna(row.get('STATUS')) else 'ACTIVE'
                    conditional = row.get('CONDITIONAL', 'NO')
                    condition_desc = row.get('CONDITION DESCRIPTION', '')
                    
                    condition_type, note_ref = parse_condition(conditional, condition_desc)
                    
                    # Handle variable fees
                    if fee_amount is None:
                        fee_amount = Decimal('0')
                        # Store condition in remarks
                        condition_desc_str = str(condition_desc).strip() if not pd.isna(condition_desc) else 'Variable fee'
                    else:
                        condition_desc_str = str(condition_desc).strip() if not pd.isna(condition_desc) else None
                    
                    # Create fee record (with truncation to prevent data errors)
                    fee_record = CardFeeMaster(
                        effective_from=effective_from,
                        effective_to=effective_to,
                        charge_type=truncate_string(charge_type, 255),
                        card_category='ANY',  # Not applicable for Skybanking
                        card_network='ANY',   # Not applicable for Skybanking
                        card_product=truncate_string(product, 100),
                        full_card_name=truncate_string(product_name, 200),
                        fee_value=fee_amount,
                        fee_unit=fee_unit,
                        fee_basis=fee_basis,
                        min_fee_value=None,
                        min_fee_unit=None,
                        max_fee_value=None,
                        free_entitlement_count=None,
                        condition_type=condition_type,
                        note_reference=truncate_string(note_ref, 20) if note_ref else None,
                        priority=100,
                        status=status,
                        remarks=condition_desc_str,
                        product_line='SKYBANKING'
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
    import_skybanking()


