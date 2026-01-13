"""
Data Migration Script
Import card charges from card_charges.json into card_fee_master table.
"""

import json
import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid
import re

# Add parent directory to path to import fee_engine_service
sys.path.insert(0, str(Path(__file__).parent))
from fee_engine_service import CardFeeMaster, DATABASE_URL, engine, SessionLocal

# Charge type mapping from document format to standardized format
CHARGE_TYPE_MAPPING = {
    "Issuance/Renewal/Annual Fee Primary Card": "ISSUANCE_ANNUAL_PRIMARY",
    "Supplementary Card - Issuance/Renewal/Annual Fee (Number of Free cards)": "SUPPLEMENTARY_FREE_ENTITLEMENT",
    "Supplementary Card - Issuance/Renewal/Annual Fee (from 2nd and 3rd card)": "SUPPLEMENTARY_ANNUAL",
    "Card Replacement Fee": "CARD_REPLACEMENT",
    "PIN Replacement Fee": "PIN_REPLACEMENT",
    "Late Payment Fee": "LATE_PAYMENT",
    "Cash Withdrawal/Advance Fee (whichever higher) - EBL ATM": "CASH_WITHDRAWAL_EBL_ATM",
    "Cash Withdrawal/Advance Fee (whichever higher) - Other Bank ATM": "CASH_WITHDRAWAL_OTHER_ATM",
    "ATM Receipt Fee (EBL)": "ATM_RECEIPT_EBL",
    "Global Lounge Access Fee (per individual)": "GLOBAL_LOUNGE_ACCESS_FEE",
    "Number of Global Lounge Free Visit (Annual)": "GLOBAL_LOUNGE_FREE_VISITS_ANNUAL",
    "Number of Internatinoal SkyLounge Free Visit (Annual)": "SKYLOUNGE_FREE_VISITS_INTL_ANNUAL",
    "Number of Domestic SkyLounge Free Visit (Annual)": "SKYLOUNGE_FREE_VISITS_DOM_ANNUAL",
    "Overlimit Fee": "OVERLIMIT",
    "Duplicate E-Statement Fee (per month)": "DUPLICATE_ESTATEMENT",
    "Sales Voucher Retrieval Fee": "SALES_VOUCHER_RETRIEVAL",
    "Certificate Fee": "CERTIFICATE_FEE",
    "Risk Assurance Fee - on outstanding*": "RISK_ASSURANCE_FEE",
    "Card Chequebook Fee - (10 leaves)": "CARD_CHEQUBOOK",
    "Card Cheque Processing Fee (whichever higher)": "CARD_CHEQUE_PROCESSING",
    "Customer Verification/CIB Fee": "CUSTOMER_VERIFICATION_CIB",
    "Transaction Alert Fee (annual)": "TRANSACTION_ALERT_ANNUAL",
    "Interest Rate (Annual)": "INTEREST_RATE",
    "Fund Transfer Fee (EBL Skybanking App)": "FUND_TRANSFER_FEE",
    "Wallet Transfer Fee (Add Money from app - MFS & PSP)": "WALLET_TRANSFER_FEE",
    "Want2Buy/EasyCredit Adjustment Fee (whichever higher)***": "WANT2BUY_EASYCREDIT_FEE",
    "Return Cheque Fee": "RETURN_CHEQUE_FEE",
    "Undelivered Card/PIN Destruction Fee": "UNDELIVERED_CARD_FEE",
    "ATM CCTV Footage Fee (EBL Card)-Inside Dhaka": "ATM_CCTV_FOOTAGE_INSIDE_DHAKA",
    "ATM CCTV Footage Fee (EBL Card)-Outside Dhaka": "ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA",
}

def parse_amount(amount_str: str) -> tuple[Decimal, str, str]:
    """
    Parse amount string like "BDT 1,725" or "$11.5" or "0.25"
    Returns: (value, unit, basis)
    """
    if not amount_str:
        return Decimal("0"), "BDT", "PER_TXN"
    
    amount_str = amount_str.strip()
    
    # Check for "According to Note X"
    note_match = re.search(r'[Nn]ote\s+(\d+)', amount_str)
    if note_match:
        return None, None, note_match.group(1)
    
    # Check for currency
    unit = "BDT"
    if "$" in amount_str or "USD" in amount_str.upper():
        unit = "USD"
        amount_str = amount_str.replace("$", "").replace("USD", "").replace("usd", "")
    elif "BDT" in amount_str.upper():
        amount_str = amount_str.replace("BDT", "").replace("bdt", "")
    
    # Remove commas and extract number
    amount_str = amount_str.replace(",", "").strip()
    
    # Check if it's a percentage
    if "%" in amount_str:
        value = Decimal(re.sub(r'[^\d.]', '', amount_str))
        return value, "PERCENT", "PER_TXN"
    
    # Try to extract decimal number
    try:
        value = Decimal(re.sub(r'[^\d.]', '', amount_str))
        return value, unit, "PER_TXN"
    except:
        return Decimal("0"), unit, "PER_TXN"

def determine_fee_basis(charge_type: str, amount_str: str) -> str:
    """Determine fee basis from charge type"""
    charge_lower = charge_type.lower()
    
    if "annual" in charge_lower or "yearly" in charge_lower:
        return "PER_YEAR"
    elif "month" in charge_lower:
        return "PER_MONTH"
    elif "visit" in charge_lower:
        return "PER_VISIT"
    elif "outstanding" in charge_lower:
        return "ON_OUTSTANDING"
    else:
        return "PER_TXN"

def determine_condition_type(charge_type: str, amount_str: str) -> tuple[str, int, str]:
    """
    Determine condition type from charge type and amount string.
    Returns: (condition_type, free_entitlement_count, note_reference)
    """
    charge_lower = charge_type.lower()
    amount_lower = amount_str.lower() if amount_str else ""
    
    # Check for note-based
    note_match = re.search(r'[Nn]ote\s+(\d+)', amount_str or "")
    if note_match:
        return "NOTE_BASED", None, note_match.group(1)
    
    # Check for free entitlement
    if "free" in charge_lower or "number of free" in charge_lower:
        # Extract number of free items
        free_match = re.search(r'(\d+)\s*(?:st|nd|rd|th)?\s*(?:card|visit|item)', charge_lower)
        if free_match:
            return "FREE_UPTO_N", int(free_match.group(1)), None
        # Check for "1st card free" pattern
        if "1st" in charge_lower or "first" in charge_lower:
            return "FREE_UPTO_N", 1, None
    
    # Check for "whichever higher"
    if "whichever higher" in charge_lower or "whichever higher" in amount_lower:
        return "WHICHEVER_HIGHER", None, None
    
    return "NONE", None, None

def normalize_card_category(category: str) -> str:
    """Normalize card category"""
    if not category:
        return "ANY"
    category_upper = category.upper()
    if "CREDIT" in category_upper:
        return "CREDIT"
    elif "DEBIT" in category_upper:
        return "DEBIT"
    elif "PREPAID" in category_upper:
        return "PREPAID"
    return "ANY"

def normalize_card_network(network: str) -> str:
    """
    Normalize card network to canonical values used for lookups.
    """
    if not network:
        return "ANY"
    
    # NOTE:
    # - For deterministic matching, store canonical network values where possible.
    # - We intentionally collapse UnionPay variants (e.g., "UnionPay International", "Union Pay Classic",
    #   "UnionPay/Mastercard/VISA Prepaid Card") to "UNIONPAY" per project convention.
    network_clean = network.strip()
    n_upper = network_clean.upper()
    
    # Standardize common variations but keep the structure
    if "UNIONPAY" in n_upper or "UNION PAY" in n_upper:
        return "UNIONPAY"
    if "DINERS" in n_upper:
        return "DINERS"
    if "TAKAPAY" in n_upper or "TAKA PAY" in n_upper:
        return "TAKAPAY"
    if "MASTER" in n_upper:
        return "MASTERCARD"
    if "VISA" in n_upper:
        return "VISA"
    else:
        # Keep within canonical set; default VISA for unknown
        return "VISA"

def migrate_data():
    """Migrate data from card_charges.json to card_fee_master table"""
    
    # Load JSON data
    # Try multiple possible paths
    json_path = Path("/app/card_charges.json")  # Try /app first (when running in container)
    if not json_path.exists():
        json_path = Path(__file__).parent.parent / "card_charges.json"  # Try relative to script
    if not json_path.exists():
        print(f"Error: card_charges.json not found. Tried:")
        print(f"  - /app/card_charges.json")
        print(f"  - {Path(__file__).parent.parent / 'card_charges.json'}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = data.get("records", [])
    print(f"Found {len(records)} records to migrate")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Clear existing data to re-import with updated network normalization
        print("Clearing existing data...")
        db.query(CardFeeMaster).delete()
        db.commit()
        print("Cleared existing data")
        
        effective_from = date(2026, 1, 1)  # Effective from 01st January, 2026
        imported_count = 0
        skipped_count = 0
        
        for record in records:
            try:
                charge_type_doc = record.get("charge_type", "")
                charge_type = CHARGE_TYPE_MAPPING.get(charge_type_doc, charge_type_doc.upper().replace(" ", "_"))
                
                amount_str = record.get("amount_raw", "")
                amount_info = parse_amount(amount_str)
                
                if amount_info[0] is None:  # Note-based
                    fee_value = Decimal("0")
                    fee_unit = "TEXT"
                    note_ref = amount_info[2]
                else:
                    fee_value, fee_unit, _ = amount_info
                    note_ref = None
                
                fee_basis = determine_fee_basis(charge_type_doc, amount_str)
                condition_type, free_count, note_ref_from_condition = determine_condition_type(charge_type_doc, amount_str)
                
                if note_ref_from_condition:
                    note_ref = note_ref_from_condition
                
                # Handle "whichever higher" - need to extract min_fee_value
                min_fee_value = None
                min_fee_unit = None
                if condition_type == "WHICHEVER_HIGHER" and fee_unit == "PERCENT":
                    # For "whichever higher", we need both percentage and minimum
                    # This might need manual adjustment based on the schedule
                    # For now, set a placeholder
                    min_fee_value = Decimal("0")  # Should be extracted from schedule
                    min_fee_unit = "BDT"
                
                # Normalize network - preserve exact dropdown values
                normalized_network = normalize_card_network(record.get("network", ""))
                
                # Handle product - use "ANY" if null or empty
                card_product = record.get("product")
                if not card_product or card_product.strip() == "":
                    card_product = "ANY"
                
                fee_record = CardFeeMaster(
                    effective_from=effective_from,
                    effective_to=None,  # No expiry
                    charge_type=charge_type,
                    card_category=normalize_card_category(record.get("category", "")),
                    card_network=normalized_network,
                    card_product=card_product,
                    full_card_name=record.get("full_name", ""),
                    fee_value=fee_value,
                    fee_unit=fee_unit,
                    fee_basis=fee_basis,
                    min_fee_value=min_fee_value,
                    min_fee_unit=min_fee_unit,
                    free_entitlement_count=free_count,
                    condition_type=condition_type,
                    note_reference=note_ref,
                    priority=100,  # Default priority
                    status="ACTIVE",
                    remarks=f"Migrated from card_charges.json - Original: {charge_type_doc}"
                )
                
                db.add(fee_record)
                imported_count += 1
                
                if imported_count % 100 == 0:
                    db.commit()
                    print(f"Imported {imported_count} records...")
                    
            except Exception as e:
                print(f"Error importing record: {record.get('full_name', 'Unknown')} - {e}")
                skipped_count += 1
                continue
        
        db.commit()
        print(f"\nMigration complete!")
        print(f"Imported: {imported_count} records")
        print(f"Skipped: {skipped_count} records")
        
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_data()
