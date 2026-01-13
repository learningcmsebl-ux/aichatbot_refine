"""
Import Retail Asset Charges from Excel
Parses and normalizes data from Retail Asset Schedule of Charges.xlsx
"""

import pandas as pd
import re
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import sys
from typing import Dict, Optional, Tuple
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fee_engine_service import get_database_url

# Product name mapping
PRODUCT_MAPPING = {
    'Fast Cash (Overdraft - OD)': 'FAST_CASH_OD',
    'Fast Loan (Secured EMI Loan)': 'FAST_LOAN_SECURED_EMI',
    'Edu Loan Secured / Edu Loan Unsecured': 'EDU_LOAN_SECURED',
    'Edu Loan Secured / Edu Loan Unsecured ': 'EDU_LOAN_SECURED',
    'Other EMI Loans': 'OTHER_EMI_LOANS',
    'Other EMI Loans ': 'OTHER_EMI_LOANS',
    'Executive Loan / Assure / Women\'s Loan': 'EXECUTIVE_LOAN',
    'Auto Loan / Two Wheeler Loan': 'AUTO_LOAN',
    'Home Loan / Home Credit / Mortgage Loan Payment Protection': 'HOME_LOAN_PAYMENT_PROTECTION',
    'Home Loan / Home Credit / Mortgage Loan': 'HOME_LOAN',
    'Other Charges': 'OTHER_CHARGES',
}

# Charge type mapping
CHARGE_TYPE_MAPPING = {
    'Processing Fee': 'PROCESSING_FEE',
    'Fast Cash Processing Fee': 'PROCESSING_FEE',
    'Fast Cash Limit Enhancement Processing Fee': 'LIMIT_ENHANCEMENT_FEE',
    'Fast Cash Limit Reduction Processing Fee': 'LIMIT_REDUCTION_FEE',
    'Fast Cash Limit Cancellation / Closing Fee': 'LIMIT_CANCELLATION_FEE',
    'Fast Cash Renewal Fee': 'RENEWAL_FEE',
    'Partial Payment Fee': 'PARTIAL_PAYMENT_FEE',
    'Early Settlement Fee': 'EARLY_SETTLEMENT_FEE',
    'Other Bank Security Lien Confirmation & Encashment': 'SECURITY_LIEN_CONFIRMATION',
    'Fee for changing car quotation after loan approval': 'QUOTATION_CHANGE_FEE',
    'Notarization Fee': 'NOTARIZATION_FEE',
    'Loan Repayment Certificate (NOC)': 'NOC_FEE',
    'Penal Interest': 'PENAL_INTEREST',
    'CIB Charge': 'CIB_CHARGE',
    'CPV Charge': 'CPV_CHARGE',
    'Vetting & Valuation Charge': 'VETTING_VALUATION_CHARGE',
    'Security Replacement Fee': 'SECURITY_REPLACEMENT_FEE',
    'Stamp Charge': 'STAMP_CHARGE',
    'Loan Outstanding Certificate Fee': 'LOAN_OUTSTANDING_CERTIFICATE_FEE',
    'Reschedule & Restructure Fee': 'RESCHEDULE_RESTRUCTURE_FEE',
    'Reschedule & Restructure Exit Fee': 'RESCHEDULE_RESTRUCTURE_EXIT_FEE',
}

def parse_amount(amount_str: str) -> Optional[Decimal]:
    """Parse amount string like 'Tk. 2,300' or '17,250' to Decimal"""
    if not amount_str or pd.isna(amount_str):
        return None
    
    # Remove currency symbols and text
    amount_str = str(amount_str).replace('Tk.', '').replace('Tk', '').strip()
    # Remove commas
    amount_str = amount_str.replace(',', '').strip()
    
    # Extract numbers
    match = re.search(r'(\d+\.?\d*)', amount_str)
    if match:
        return Decimal(match.group(1))
    return None

def parse_percentage(percent_str: str) -> Optional[Decimal]:
    """Parse percentage string like '0.575%' to Decimal"""
    if not percent_str or pd.isna(percent_str):
        return None
    
    match = re.search(r'(\d+\.?\d*)%', str(percent_str))
    if match:
        return Decimal(match.group(1))
    return None

def parse_lakh(amount_str: str) -> Optional[Decimal]:
    """Parse '50 lakh' to Decimal (50,00,000)"""
    if not amount_str or pd.isna(amount_str):
        return None
    
    match = re.search(r'(\d+\.?\d*)\s*lakh', str(amount_str), re.IGNORECASE)
    if match:
        lakh_value = Decimal(match.group(1))
        return lakh_value * Decimal('100000')  # Convert lakh to actual amount
    return None

def parse_charge_amount(charge_text: str) -> Dict:
    """
    Parse complex charge amount strings into structured data.
    
    Examples:
    - "Up to Tk. 50 lakh – 0.575% or max Tk. 17,250; Above Tk. 50 lakh – 0.345% or max Tk. 23,000"
    - "0.575% on reduced amount; Min Tk. 575, Max Tk. 5,750"
    - "Tk. 2,300"
    - "0.575% on loan amount"
    - "Not applicable"
    - "Actual expense basis***"
    """
    if not charge_text or pd.isna(charge_text):
        return {'fee_unit': 'TEXT', 'original_text': str(charge_text) if charge_text else None}
    
    charge_text = str(charge_text).strip()
    result = {
        'fee_value': None,
        'fee_unit': 'TEXT',
        'fee_basis': 'PER_AMOUNT',
        'tier_1_threshold': None,
        'tier_1_fee_value': None,
        'tier_1_fee_unit': None,
        'tier_1_max_fee': None,
        'tier_2_threshold': None,
        'tier_2_fee_value': None,
        'tier_2_fee_unit': None,
        'tier_2_max_fee': None,
        'min_fee_value': None,
        'max_fee_value': None,
        'condition_type': 'NONE',
        'original_text': charge_text
    }
    
    # Check for "Not applicable"
    if 'not applicable' in charge_text.lower():
        result['fee_unit'] = 'TEXT'
        return result
    
    # Check for "Actual expense basis"
    if 'actual expense' in charge_text.lower():
        result['fee_unit'] = 'ACTUAL_COST'
        return result
    
    # Check for tiered structure (Up to X amount; Above X amount)
    tiered_match = re.search(
        r'Up to.*?(\d+\.?\d*)\s*lakh.*?(\d+\.?\d*)%.*?max.*?(\d+[,\d]*).*?Above.*?(\d+\.?\d*)\s*lakh.*?(\d+\.?\d*)%.*?max.*?(\d+[,\d]*)',
        charge_text,
        re.IGNORECASE
    )
    
    if tiered_match:
        tier_1_lakh = Decimal(tiered_match.group(1))
        tier_1_percent = Decimal(tiered_match.group(2))
        tier_1_max = parse_amount(tiered_match.group(3))
        tier_2_lakh = Decimal(tiered_match.group(4))
        tier_2_percent = Decimal(tiered_match.group(5))
        tier_2_max = parse_amount(tiered_match.group(6))
        
        result['tier_1_threshold'] = tier_1_lakh * Decimal('100000')
        result['tier_1_fee_value'] = tier_1_percent
        result['tier_1_fee_unit'] = 'PERCENT'
        result['tier_1_max_fee'] = tier_1_max
        result['tier_2_threshold'] = tier_2_lakh * Decimal('100000')
        result['tier_2_fee_value'] = tier_2_percent
        result['tier_2_fee_unit'] = 'PERCENT'
        result['tier_2_max_fee'] = tier_2_max
        result['condition_type'] = 'TIERED'
        result['fee_unit'] = 'PERCENT'  # Default for tiered
        return result
    
    # Check for percentage with min/max
    min_max_match = re.search(
        r'(\d+\.?\d*)%.*?Min.*?(\d+[,\d]*).*?Max.*?(\d+[,\d]*)',
        charge_text,
        re.IGNORECASE
    )
    
    if min_max_match:
        percent = Decimal(min_max_match.group(1))
        min_fee = parse_amount(min_max_match.group(2))
        max_fee = parse_amount(min_max_match.group(3))
        
        result['fee_value'] = percent
        result['fee_unit'] = 'PERCENT'
        result['min_fee_value'] = min_fee
        result['max_fee_value'] = max_fee
        result['condition_type'] = 'WHICHEVER_HIGHER'
        return result
    
    # Check for simple percentage
    percent_match = re.search(r'(\d+\.?\d*)%\s*on', charge_text, re.IGNORECASE)
    if percent_match:
        percent = Decimal(percent_match.group(1))
        result['fee_value'] = percent
        result['fee_unit'] = 'PERCENT'
        return result
    
    # Check for fixed amount
    fixed_match = re.search(r'Tk\.?\s*(\d+[,\d]*)', charge_text, re.IGNORECASE)
    if fixed_match:
        amount = parse_amount(fixed_match.group(1))
        if amount:
            result['fee_value'] = amount
            result['fee_unit'] = 'BDT'
            return result
    
    # Check for "whichever is higher"
    higher_match = re.search(r'(\d+[,\d]*\.?\d*)\s*or.*?whichever.*?higher', charge_text, re.IGNORECASE)
    if higher_match:
        amount = parse_amount(higher_match.group(1))
        if amount:
            result['fee_value'] = amount
            result['fee_unit'] = 'BDT'
            result['condition_type'] = 'WHICHEVER_HIGHER'
            return result
    
    # Default: store as text
    return result

def normalize_product_name(product_name: str) -> Tuple[str, str]:
    """Normalize product name and return (enum_value, original_name)"""
    if not product_name or pd.isna(product_name):
        return ('OTHER_CHARGES', str(product_name) if product_name else 'Unknown')
    
    product_name = str(product_name).strip()
    
    # Check mapping
    for key, enum_value in PRODUCT_MAPPING.items():
        if key.lower() in product_name.lower() or product_name.lower() in key.lower():
            return (enum_value, product_name)
    
    # Default
    return ('OTHER_CHARGES', product_name)

def normalize_charge_type(description: str) -> Tuple[str, str]:
    """Normalize charge description and return (enum_value, original_description)"""
    if not description or pd.isna(description):
        return ('OTHER', str(description) if description else 'Unknown')
    
    description = str(description).strip()
    
    # Check mapping
    for key, enum_value in CHARGE_TYPE_MAPPING.items():
        if key.lower() in description.lower():
            return (enum_value, description)
    
    # Default
    return ('OTHER', description)

def parse_employee_fee(employee_fee_text: str) -> Dict:
    """Parse employee fee information"""
    if not employee_fee_text or pd.isna(employee_fee_text):
        return {'employee_fee_value': None, 'employee_fee_unit': None, 'employee_fee_description': None}
    
    employee_fee_text = str(employee_fee_text).strip()
    
    if 'free' in employee_fee_text.lower():
        return {
            'employee_fee_value': Decimal('0'),
            'employee_fee_unit': 'BDT',
            'employee_fee_description': 'Free'
        }
    
    # Check for discount
    discount_match = re.search(r'(\d+)%\s*discount', employee_fee_text, re.IGNORECASE)
    if discount_match:
        return {
            'employee_fee_value': None,
            'employee_fee_unit': None,
            'employee_fee_description': employee_fee_text
        }
    
    return {
        'employee_fee_value': None,
        'employee_fee_unit': None,
        'employee_fee_description': employee_fee_text
    }

def extract_condition(charge_text: str, description: str) -> Optional[str]:
    """Extract condition text like 'minimum 30% of outstanding must be paid', 'after 6 months'"""
    combined = f"{description} {charge_text}".lower()
    
    conditions = []
    
    # Check for minimum percentage
    min_match = re.search(r'minimum\s+(\d+\.?\d*)%\s+of\s+outstanding', combined, re.IGNORECASE)
    if min_match:
        conditions.append(f"Minimum {min_match.group(1)}% of outstanding must be paid")
    
    # Check for after X months
    months_match = re.search(r'after\s+(\d+)\s+months?', combined, re.IGNORECASE)
    if months_match:
        conditions.append(f"After {months_match.group(1)} months")
    
    # Check for after X installments
    installments_match = re.search(r'after\s+(\d+)\s+installments?', combined, re.IGNORECASE)
    if installments_match:
        conditions.append(f"After {installments_match.group(1)} installments")
    
    # Check for minimum amount
    min_amount_match = re.search(r'min\s+(\d+[,\d]*\.?\d*)\s+(lakh|taka|tk)', combined, re.IGNORECASE)
    if min_amount_match:
        amount = min_amount_match.group(1).replace(',', '')
        unit = min_amount_match.group(2)
        conditions.append(f"Minimum {amount} {unit} must be paid")
    
    return '; '.join(conditions) if conditions else None

def import_retail_asset_charges(excel_path: str, db_url: str = None):
    """Import retail asset charges from Excel file"""
    
    if db_url is None:
        db_url = get_database_url()
    
    print(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else 'localhost'}")
    engine = create_engine(db_url, pool_pre_ping=True)
    
    # Read Excel file
    print(f"Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Filter out empty rows
    df = df[df['Product / Loan Type'].notna()]
    df = df[df['Description'].notna()]
    
    print(f"Found {len(df)} rows to import")
    
    # Schema should already exist - skip creation
    # If you need to create the schema, run create_retail_schema_complete.py first
    print("Note: Assuming schema already exists. If you get table errors, create the schema first.")
    
    # Prepare data for insertion
    records = []
    
    for idx, row in df.iterrows():
        product_name = row['Product / Loan Type']
        description = row['Description']
        charge_amount = row['Charge Amount (Including 15% VAT)']
        employee_fee = row['Fee for EBL Employees']
        effective_from = row['Effective from']
        
        # Skip invalid rows
        if pd.isna(product_name) or pd.isna(description):
            continue
        
        # Normalize product
        loan_product, loan_product_name = normalize_product_name(product_name)
        
        # Normalize charge type
        charge_type, charge_description = normalize_charge_type(description)
        
        # Parse charge amount
        charge_data = parse_charge_amount(charge_amount)
        
        # Parse employee fee
        employee_data = parse_employee_fee(employee_fee)
        
        # Extract conditions
        condition_desc = extract_condition(charge_amount, description)
        
        # Parse effective date
        if pd.isna(effective_from):
            effective_date = datetime.now().date()
        else:
            if isinstance(effective_from, str):
                effective_date = datetime.strptime(effective_from, '%Y-%m-%d').date()
            else:
                effective_date = effective_from.date() if hasattr(effective_from, 'date') else datetime.now().date()
        
        # Build record
        record = {
            'charge_id': uuid.uuid4(),
            'effective_from': effective_date,
            'effective_to': None,
            'loan_product': loan_product,
            'loan_product_name': loan_product_name,
            'charge_type': charge_type,
            'charge_description': charge_description,
            'fee_value': charge_data.get('fee_value'),
            'fee_unit': charge_data.get('fee_unit', 'TEXT'),
            'fee_basis': charge_data.get('fee_basis', 'PER_AMOUNT'),
            'tier_1_threshold': charge_data.get('tier_1_threshold'),
            'tier_1_fee_value': charge_data.get('tier_1_fee_value'),
            'tier_1_fee_unit': charge_data.get('tier_1_fee_unit'),
            'tier_1_max_fee': charge_data.get('tier_1_max_fee'),
            'tier_2_threshold': charge_data.get('tier_2_threshold'),
            'tier_2_fee_value': charge_data.get('tier_2_fee_value'),
            'tier_2_fee_unit': charge_data.get('tier_2_fee_unit'),
            'tier_2_max_fee': charge_data.get('tier_2_max_fee'),
            'min_fee_value': charge_data.get('min_fee_value'),
            'min_fee_unit': charge_data.get('min_fee_unit'),
            'max_fee_value': charge_data.get('max_fee_value'),
            'max_fee_unit': charge_data.get('max_fee_unit'),
            'condition_type': charge_data.get('condition_type', 'NONE'),
            'condition_description': condition_desc,
            'employee_fee_value': employee_data.get('employee_fee_value'),
            'employee_fee_unit': employee_data.get('employee_fee_unit'),
            'employee_fee_description': employee_data.get('employee_fee_description'),
            'original_charge_text': charge_data.get('original_text'),
            'status': 'ACTIVE',
            'priority': 100
        }
        
        records.append(record)
    
    # Insert records
    print(f"\nInserting {len(records)} records...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        for record in records:
            insert_sql = text("""
                INSERT INTO retail_asset_charge_master (
                    charge_id, effective_from, effective_to,
                    loan_product, loan_product_name, charge_type, charge_description,
                    fee_value, fee_unit, fee_basis,
                    tier_1_threshold, tier_1_fee_value, tier_1_fee_unit, tier_1_max_fee,
                    tier_2_threshold, tier_2_fee_value, tier_2_fee_unit, tier_2_max_fee,
                    min_fee_value, min_fee_unit, max_fee_value, max_fee_unit,
                    condition_type, condition_description,
                    employee_fee_value, employee_fee_unit, employee_fee_description,
                    original_charge_text, status, priority
                ) VALUES (
                    :charge_id, :effective_from, :effective_to,
                    :loan_product, :loan_product_name, :charge_type, :charge_description,
                    :fee_value, :fee_unit, :fee_basis,
                    :tier_1_threshold, :tier_1_fee_value, :tier_1_fee_unit, :tier_1_max_fee,
                    :tier_2_threshold, :tier_2_fee_value, :tier_2_fee_unit, :tier_2_max_fee,
                    :min_fee_value, :min_fee_unit, :max_fee_value, :max_fee_unit,
                    :condition_type, :condition_description,
                    :employee_fee_value, :employee_fee_unit, :employee_fee_description,
                    :original_charge_text, :status, :priority
                )
            """)
            
            session.execute(insert_sql, record)
        
        session.commit()
        print(f"✓ Successfully imported {len(records)} records")
        
        # Print summary
        summary_sql = text("""
            SELECT 
                loan_product,
                COUNT(*) as count
            FROM retail_asset_charge_master
            GROUP BY loan_product
            ORDER BY count DESC
        """)
        
        result = session.execute(summary_sql)
        print("\nImport Summary:")
        print("-" * 50)
        for row in result:
            print(f"  {row[0]}: {row[1]} charges")
        
    except Exception as e:
        session.rollback()
        print(f"✗ Error importing data: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    excel_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                              'xls', 'Retail Asset Schedule of Charges.xlsx')
    
    if not os.path.exists(excel_path):
        print(f"Error: Excel file not found at {excel_path}")
        sys.exit(1)
    
    import_retail_asset_charges(excel_path)

