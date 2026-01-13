"""
Import Credit Card fees from Card_Fees_From_TXT.xlsx
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
    """Parse date string"""
    if not date_str or pd.isna(date_str):
        return datetime(2026, 1, 1).date()  # Default effective date
    
    if isinstance(date_str, datetime):
        return date_str.date()
    
    date_str = str(date_str).strip()
    formats = ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    
    return datetime(2026, 1, 1).date()  # Default

def truncate_string(value, max_length):
    """Truncate string to max_length if needed"""
    if value is None:
        return None
    value_str = str(value).strip()
    if len(value_str) > max_length:
        return value_str[:max_length]
    return value_str

def parse_fee_amount(fee_str):
    """Parse fee amount from string like 'BDT 1,725' or '1,725'"""
    if pd.isna(fee_str) or not fee_str:
        return Decimal('0')
    
    fee_str = str(fee_str).strip()
    
    # Remove currency symbols and text
    fee_str = fee_str.replace('BDT', '').replace('USD', '').replace('$', '').strip()
    
    # Remove commas
    fee_str = fee_str.replace(',', '').strip()
    
    try:
        return Decimal(fee_str)
    except:
        return Decimal('0')

def normalize_card_category(category):
    """Normalize card category"""
    if pd.isna(category):
        return 'ANY'
    
    category = str(category).strip().upper()
    if 'CREDIT' in category:
        return 'CREDIT'
    elif 'DEBIT' in category:
        return 'DEBIT'
    elif 'PREPAID' in category:
        return 'PREPAID'
    return 'ANY'

def normalize_card_network(network):
    """Normalize card network"""
    if pd.isna(network):
        return 'ANY'
    
    network = str(network).strip().upper()
    networks = ['VISA', 'MASTERCARD', 'DINERS', 'UNIONPAY', 'FX', 'TAKAPAY']
    for n in networks:
        if n in network:
            return n
    return 'ANY'

def normalize_charge_type(charge_type):
    """Normalize charge type to standard format"""
    if pd.isna(charge_type):
        return 'UNKNOWN'
    
    charge_type = str(charge_type).strip().upper()
    
    # Map common charge types
    if 'ANNUAL' in charge_type or 'RENEWAL' in charge_type or 'ISSUANCE' in charge_type:
        if 'SUPPLEMENTARY' in charge_type:
            return 'ISSUANCE_ANNUAL_SUPPLEMENTARY'
        else:
            return 'ISSUANCE_ANNUAL_PRIMARY'
    elif 'CASH WITHDRAWAL' in charge_type or 'ATM' in charge_type:
        return 'CASH_WITHDRAWAL_EBL_ATM'
    elif 'LOUNGE' in charge_type:
        return 'GLOBAL_LOUNGE_ACCESS_FEE'
    elif 'TRANSACTION ALERT' in charge_type:
        return 'TRANSACTION_ALERT_ANNUAL'
    
    # Return normalized version
    return charge_type.replace(' ', '_').replace('/', '_')

def import_credit_cards():
    """Import credit card fees from Excel file"""
    
    excel_path = Path(__file__).parent.parent.parent / "xls" / "Card_Fees_From_TXT.xlsx"
    
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        return
    
    print(f"\n{'='*70}")
    print("Importing Credit Card Fees")
    print(f"{'='*70}")
    print(f"Reading: {excel_path.name}")
    
    try:
        df = pd.read_excel(excel_path, sheet_name='Card Fees')
        print(f"Found {len(df)} rows")
        
        db = SessionLocal()
        imported = 0
        skipped = 0
        
        try:
            for idx, row in df.iterrows():
                try:
                    # Skip empty rows
                    if pd.isna(row.get('Charge Type')) or not str(row.get('Charge Type')).strip():
                        continue
                    
                    charge_type = normalize_charge_type(row.get('Charge Type', ''))
                    card_category = normalize_card_category(row.get('Card Category', ''))
                    card_network = normalize_card_network(row.get('Card Network', ''))
                    card_product = str(row.get('Card Product', 'ANY')).strip() if not pd.isna(row.get('Card Product')) else 'ANY'
                    full_card_name = str(row.get('Full Card Name', '')).strip() if not pd.isna(row.get('Full Card Name')) else None
                    fee_amount = parse_fee_amount(row.get('Charge Amount/Fee ', ''))
                    
                    # Determine fee_basis from charge_type
                    if 'ANNUAL' in charge_type or 'RENEWAL' in charge_type:
                        fee_basis = 'PER_YEAR'
                    else:
                        fee_basis = 'PER_TXN'
                    
                    # Create fee record (with truncation to prevent data errors)
                    fee_record = CardFeeMaster(
                        effective_from=datetime(2026, 1, 1).date(),  # Default
                        effective_to=None,
                        charge_type=truncate_string(charge_type, 255),
                        card_category=card_category,
                        card_network=card_network,
                        card_product=truncate_string(card_product, 100),
                        full_card_name=truncate_string(full_card_name, 200),
                        fee_value=fee_amount,
                        fee_unit='BDT',
                        fee_basis=fee_basis,
                        min_fee_value=None,
                        min_fee_unit=None,
                        max_fee_value=None,
                        free_entitlement_count=None,
                        condition_type='NONE',
                        note_reference=None,
                        priority=100,
                        status='ACTIVE',
                        remarks=None,
                        product_line='CREDIT_CARDS'
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
    import_credit_cards()


