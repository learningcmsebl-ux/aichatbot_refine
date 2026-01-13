"""
Data Migration Script - Import from CSV
Import card fees from credit_card_rates.csv into card_fee_master table.
This CSV is the primary source and is already in the correct format.
"""

import csv
import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Add parent directory to path to import fee_engine_service
sys.path.insert(0, str(Path(__file__).parent))
from fee_engine_service import CardFeeMaster, DATABASE_URL, engine, SessionLocal

def parse_date(date_str: str):
    """Parse date string like '1/1/2026' or '2026-01-01'"""
    if not date_str or date_str.strip() == '':
        return None
    
    date_str = date_str.strip()
    
    # Try different formats
    formats = ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    
    # If all fail, return None
    return None

def parse_decimal(value_str: str):
    """Parse decimal value, handling empty strings"""
    if not value_str or value_str.strip() == '':
        return None
    
    try:
        return Decimal(value_str.strip())
    except:
        return None

def parse_int(value_str: str):
    """Parse integer value, handling empty strings"""
    if not value_str or value_str.strip() == '':
        return None
    
    try:
        return int(value_str.strip())
    except:
        return None

def migrate_from_csv():
    """Migrate data from credit_card_rates.csv to card_fee_master table"""
    
    # Load CSV data
    csv_path = Path(__file__).parent.parent / "credit_card_rates.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        return
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Clear existing data (optional - comment out if you want to keep existing)
        # db.query(CardFeeMaster).delete()
        # db.commit()
        # print("Cleared existing data")
        
        imported_count = 0
        skipped_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Skip empty rows
                    if not row.get('charge_type') or row.get('charge_type').strip() == '':
                        continue
                    
                    # Parse date
                    effective_from = parse_date(row.get('effective_from', ''))
                    if not effective_from:
                        print(f"Skipping row with invalid date: {row.get('charge_type', 'Unknown')}")
                        skipped_count += 1
                        continue
                    
                    effective_to = parse_date(row.get('effective_to', ''))
                    
                    # Parse fee value
                    fee_value = parse_decimal(row.get('fee_value', ''))
                    fee_unit = row.get('fee_unit', 'BDT').strip().upper()
                    
                    # Handle COUNT unit - fee_value can be empty for COUNT units
                    if fee_value is None:
                        if fee_unit in ['COUNT', 'TEXT']:
                            fee_value = Decimal("0")  # COUNT/TEXT units can have 0 fee_value
                        elif row.get('condition_type', '').upper() == 'NOTE_BASED':
                            fee_value = Decimal("0")  # Note-based can have 0 fee_value
                        else:
                            # For other units, fee_value should exist
                            fee_value = Decimal("0")  # Default to 0 if missing
                    
                    # Parse min_fee_value
                    min_fee_value = parse_decimal(row.get('min_fee_value', ''))
                    min_fee_unit = row.get('min_fee_unit', '').strip() if row.get('min_fee_unit') else None
                    
                    # Parse free_entitlement_count
                    free_entitlement_count = parse_int(row.get('free_entitlement_count', ''))
                    
                    # Parse priority
                    priority = parse_int(row.get('priority', ''))
                    if priority is None:
                        priority = 100  # Default priority
                    
                    # Get status
                    status = row.get('status', 'ACTIVE').strip().upper()
                    if status not in ['ACTIVE', 'INACTIVE']:
                        status = 'ACTIVE'
                    
                    fee_record = CardFeeMaster(
                        effective_from=effective_from,
                        effective_to=effective_to,
                        charge_type=row.get('charge_type', '').strip(),
                        card_category=row.get('card_category', 'ANY').strip().upper(),
                        card_network=row.get('card_network', 'ANY').strip().upper(),
                        card_product=row.get('card_product', 'ANY').strip(),
                        full_card_name=row.get('full_card_name', '').strip(),
                        fee_value=fee_value,
                        fee_unit=fee_unit,
                        fee_basis=row.get('fee_basis', 'PER_TXN').strip().upper(),
                        min_fee_value=min_fee_value,
                        min_fee_unit=min_fee_unit,
                        max_fee_value=parse_decimal(row.get('max_fee_value', '')),
                        free_entitlement_count=free_entitlement_count,
                        condition_type=row.get('condition_type', 'NONE').strip().upper(),
                        note_reference=row.get('note_reference', '').strip() if row.get('note_reference') else None,
                        priority=priority,
                        status=status,
                        remarks=row.get('remarks', '').strip() if row.get('remarks') else None
                    )
                    
                    db.add(fee_record)
                    imported_count += 1
                    
                    if imported_count % 100 == 0:
                        db.commit()
                        print(f"Imported {imported_count} records...")
                        
                except Exception as e:
                    print(f"Error importing row: {row.get('charge_type', 'Unknown')} - {e}")
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
    migrate_from_csv()
