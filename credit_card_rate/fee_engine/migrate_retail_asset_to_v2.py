"""
Migrate data from retail_asset_charge_master (v1) to retail_asset_charge_master_v2
Extracts charge_context from charge_description using keyword matching
"""

import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import fee_engine_service
sys.path.insert(0, str(Path(__file__).parent))

def get_database_url():
    """Construct database URL from environment variables"""
    url = os.getenv("FEE_ENGINE_DB_URL")
    if url:
        return url
    
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'postgres')
    
    from urllib.parse import quote_plus
    password_encoded = quote_plus(password) if password else ''
    
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

DATABASE_URL = get_database_url()

def extract_charge_context(charge_description: str, charge_type: Optional[str] = None) -> str:
    """
    Extract charge_context from charge_description using keyword matching.
    Also uses charge_type for deterministic override when available.
    
    Args:
        charge_description: Charge description text
        charge_type: Charge type (e.g., LIMIT_ENHANCEMENT_FEE, LIMIT_REDUCTION_FEE)
    
    Returns:
        charge_context: ON_LIMIT, ON_ENHANCED_AMOUNT, ON_REDUCED_AMOUNT, or GENERAL
    """
    # Charge type-based override (most deterministic)
    if charge_type:
        if charge_type == "LIMIT_ENHANCEMENT_FEE":
            return 'ON_ENHANCED_AMOUNT'
        if charge_type == "LIMIT_REDUCTION_FEE":
            return 'ON_REDUCED_AMOUNT'
    
    if not charge_description:
        return 'GENERAL'
    
    desc_lower = charge_description.lower()
    
    # Check for enhancement keywords first (before generic limit)
    if any(keyword in desc_lower for keyword in ["enhancement", "enhance", "limit enhancement", "enhance limit"]):
        return 'ON_ENHANCED_AMOUNT'
    
    # Check for reduction keywords
    if any(keyword in desc_lower for keyword in ["reduction", "reduce", "limit reduction", "reduce limit"]):
        return 'ON_REDUCED_AMOUNT'
    
    # Check for explicit limit/loan amount phrases only (NOT standalone "limit")
    if any(keyword in desc_lower for keyword in ["on limit", "on loan amount", "loan amount"]):
        return 'ON_LIMIT'
    
    # Default to GENERAL
    return 'GENERAL'

def migrate_data():
    """Migrate data from v1 to v2 table"""
    
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    with engine.begin() as conn:
        # Check if v1 table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'retail_asset_charge_master'
            );
        """))
        v1_exists = result.scalar()
        
        if not v1_exists:
            print("ERROR: retail_asset_charge_master (v1) table does not exist!")
            return
        
        # Check if v2 table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'retail_asset_charge_master_v2'
            );
        """))
        v2_exists = result.scalar()
        
        if not v2_exists:
            print("ERROR: retail_asset_charge_master_v2 table does not exist!")
            print("Please run schema_retail_asset_v2.sql first to create the v2 table.")
            return
        
        # Check if v2 table already has data
        result = conn.execute(text("SELECT COUNT(*) FROM retail_asset_charge_master_v2"))
        v2_count = result.scalar()
        
        if v2_count > 0:
            print(f"WARNING: retail_asset_charge_master_v2 already contains {v2_count} records.")
            response = input("Do you want to continue and add to existing data? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                return
        
        # Get all records from v1 (note: charge_type is at index 5, charge_description is at index 6)
        print("Reading records from retail_asset_charge_master (v1)...")
        result = conn.execute(text("""
            SELECT 
                charge_id, effective_from, effective_to,
                loan_product, loan_product_name,
                charge_type, charge_description,
                fee_value, fee_unit, fee_basis,
                tier_1_threshold, tier_1_fee_value, tier_1_fee_unit, tier_1_max_fee,
                tier_2_threshold, tier_2_fee_value, tier_2_fee_unit, tier_2_max_fee,
                min_fee_value, min_fee_unit, max_fee_value, max_fee_unit,
                condition_type, condition_description,
                employee_fee_value, employee_fee_unit, employee_fee_description,
                category_a_fee_value, category_a_fee_unit,
                category_b_fee_value, category_b_fee_unit,
                category_c_fee_value, category_c_fee_unit,
                original_charge_text, note_reference,
                priority, status, remarks,
                created_at, updated_at
            FROM retail_asset_charge_master
            ORDER BY effective_from, loan_product, charge_type
        """))
        
        records = result.fetchall()
        total_records = len(records)
        print(f"Found {total_records} records to migrate.")
        
        if total_records == 0:
            print("No records to migrate.")
            return
        
        # Migrate records
        migrated = 0
        skipped = 0
        skipped_conflict = 0  # Records skipped due to ON CONFLICT
        errors = []
        
        print("\nMigrating records...")
        
        for idx, row in enumerate(records, 1):
            try:
                # Extract charge_context from description and charge_type
                charge_description = row[6] or ""
                charge_type = row[5]  # charge_type is at index 5
                charge_context = extract_charge_context(charge_description, charge_type)
                
                # Generate charge_title (short version of description, or use description if short)
                charge_title = charge_description[:200] if charge_description else row[5]  # charge_type as fallback
                
                # Map min_fee_unit/max_fee_unit to currency (must be BDT or USD, not PERCENT)
                min_fee_unit = row[19]
                min_fee_currency = 'BDT'  # Default
                if min_fee_unit:
                    min_fee_currency = 'USD' if min_fee_unit.upper() == 'USD' else 'BDT'
                
                max_fee_unit = row[21]
                max_fee_currency = 'BDT'  # Default
                if max_fee_unit:
                    max_fee_currency = 'USD' if max_fee_unit.upper() == 'USD' else 'BDT'
                
                # Map tier fee units to currency
                tier_1_fee_unit = row[12]
                tier_1_rate_unit = tier_1_fee_unit if tier_1_fee_unit else 'PERCENT'  # Default to PERCENT for rates
                if tier_1_rate_unit and tier_1_rate_unit.upper() in ['BDT', 'USD']:
                    tier_1_rate_unit = 'PERCENT'  # Tier rates should be PERCENT, currency is separate
                
                tier_1_threshold_currency = 'BDT'  # Threshold amounts are always currency
                
                tier_2_fee_unit = row[16]
                tier_2_rate_unit = tier_2_fee_unit if tier_2_fee_unit else 'PERCENT'
                if tier_2_rate_unit and tier_2_rate_unit.upper() in ['BDT', 'USD']:
                    tier_2_rate_unit = 'PERCENT'
                
                tier_2_threshold_currency = 'BDT'
                
                # Insert into v2 table
                # Use CAST in SQL to convert string values to enum types
                insert_sql = text("""
                    INSERT INTO retail_asset_charge_master_v2 (
                        charge_id, effective_from, effective_to,
                        loan_product, loan_product_name,
                        charge_type, charge_context,
                        charge_title, charge_description,
                        fee_value, fee_unit, fee_basis,
                        min_fee_value, min_fee_currency,
                        max_fee_value, max_fee_currency,
                        tier_1_threshold_amount, tier_1_threshold_currency,
                        tier_1_rate_value, tier_1_rate_unit,
                        tier_1_max_fee_value, tier_1_max_fee_currency,
                        tier_2_threshold_amount, tier_2_threshold_currency,
                        tier_2_rate_value, tier_2_rate_unit,
                        tier_2_max_fee_value, tier_2_max_fee_currency,
                        condition_type, condition_description,
                        employee_fee_value, employee_fee_unit, employee_fee_description,
                        category_a_fee_value, category_a_fee_unit,
                        category_b_fee_value, category_b_fee_unit,
                        category_c_fee_value, category_c_fee_unit,
                        original_charge_text, note_reference,
                        priority, status, remarks,
                        created_at, updated_at
                    ) VALUES (
                        :charge_id, :effective_from, :effective_to,
                        CAST(:loan_product AS loan_product_enum), :loan_product_name,
                        CAST(:charge_type AS retail_charge_type_enum), CAST(:charge_context AS charge_context_enum),
                        :charge_title, :charge_description,
                        :fee_value, CAST(:fee_unit AS fee_unit_enum), CAST(:fee_basis AS fee_basis_enum),
                        :min_fee_value, CAST(:min_fee_currency AS fee_unit_enum),
                        :max_fee_value, CAST(:max_fee_currency AS fee_unit_enum),
                        :tier_1_threshold, CAST(:tier_1_threshold_currency AS fee_unit_enum),
                        :tier_1_fee_value, CAST(:tier_1_rate_unit AS fee_unit_enum),
                        :tier_1_max_fee, CAST(:tier_1_max_fee_currency AS fee_unit_enum),
                        :tier_2_threshold, CAST(:tier_2_threshold_currency AS fee_unit_enum),
                        :tier_2_fee_value, CAST(:tier_2_rate_unit AS fee_unit_enum),
                        :tier_2_max_fee, CAST(:tier_2_max_fee_currency AS fee_unit_enum),
                        CAST(:condition_type AS condition_type_enum), :condition_description,
                        :employee_fee_value, CAST(:employee_fee_unit AS fee_unit_enum), :employee_fee_description,
                        :category_a_fee_value, CAST(:category_a_fee_unit AS fee_unit_enum),
                        :category_b_fee_value, CAST(:category_b_fee_unit AS fee_unit_enum),
                        :category_c_fee_value, CAST(:category_c_fee_unit AS fee_unit_enum),
                        :original_charge_text, :note_reference,
                        :priority, CAST(:status AS status_enum), :remarks,
                        :created_at, :updated_at
                    )
                    ON CONFLICT (loan_product, charge_type, charge_context, effective_from) WHERE status='ACTIVE' DO NOTHING
                """)
                
                res = conn.execute(insert_sql, {
                    'charge_id': row[0],
                    'effective_from': row[1],
                    'effective_to': row[2],
                    'loan_product': row[3],
                    'loan_product_name': row[4],
                    'charge_type': row[5],
                    'charge_context': charge_context,
                    'charge_title': charge_title,
                    'charge_description': charge_description,
                    'fee_value': row[7],
                    'fee_unit': row[8],
                    'fee_basis': row[9],
                    'tier_1_threshold': row[10],
                    'tier_1_fee_value': row[11],
                    'tier_1_rate_unit': tier_1_rate_unit,
                    'tier_1_max_fee': row[13],
                    'tier_2_threshold': row[14],
                    'tier_2_fee_value': row[15],
                    'tier_2_rate_unit': tier_2_rate_unit,
                    'tier_2_max_fee': row[17],
                    'min_fee_value': row[18],
                    'min_fee_currency': min_fee_currency,
                    'max_fee_value': row[20],
                    'max_fee_currency': max_fee_currency,
                    'tier_1_threshold_currency': tier_1_threshold_currency,
                    'tier_1_max_fee_currency': 'BDT',
                    'tier_2_threshold_currency': tier_2_threshold_currency,
                    'tier_2_max_fee_currency': 'BDT',
                    'condition_type': row[22],
                    'condition_description': row[23],
                    'employee_fee_value': row[24],
                    'employee_fee_unit': row[25],
                    'employee_fee_description': row[26],
                    'category_a_fee_value': row[27],
                    'category_a_fee_unit': row[28],
                    'category_b_fee_value': row[29],
                    'category_b_fee_unit': row[30],
                    'category_c_fee_value': row[31],
                    'category_c_fee_unit': row[32],
                    'original_charge_text': row[33],
                    'note_reference': row[34],
                    'priority': row[35],
                    'status': row[36],
                    'remarks': row[37],
                    'created_at': row[38],
                    'updated_at': row[39]
                })
                
                # Check if row was actually inserted (rowcount == 1) or skipped by ON CONFLICT (rowcount == 0)
                if res.rowcount == 1:
                    migrated += 1
                    if migrated % 10 == 0:
                        print(f"  Migrated {migrated}/{total_records} records...")
                else:
                    skipped_conflict += 1
                
            except Exception as e:
                skipped += 1
                error_msg = f"Error migrating record {idx} (charge_id={row[0]}): {str(e)}"
                errors.append(error_msg)
                print(f"  {error_msg}")
        
        print(f"\nMigration complete!")
        print(f"  Migrated: {migrated} records")
        print(f"  Skipped (conflicts): {skipped_conflict} records")
        print(f"  Skipped (errors): {skipped} records")
        
        if errors:
            print(f"\nErrors encountered ({len(errors)}):")
            for error in errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")
        
        # Show charge_context distribution
        print("\nCharge context distribution:")
        result = conn.execute(text("""
            SELECT charge_context, COUNT(*) as count
            FROM retail_asset_charge_master_v2
            GROUP BY charge_context
            ORDER BY count DESC
        """))
        for row in result:
            print(f"  {row[0]}: {row[1]} records")

if __name__ == "__main__":
    migrate_data()

