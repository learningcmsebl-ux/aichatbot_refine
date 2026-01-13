"""
Deploy Fee Engine Service
This script:
1. Creates database schema
2. Imports data from CSV
3. Starts the service
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import from fee_engine_service
from fee_engine_service import DATABASE_URL, engine, Base

def create_schema():
    """Create database schema from schema.sql"""
    print("=" * 70)
    print("Step 1: Creating Database Schema")
    print("=" * 70)
    
    schema_file = Path(__file__).parent / "schema.sql"
    
    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {schema_file}")
        return False
    
    try:
        # Use SQLAlchemy to create tables from Base metadata
        print("  Creating tables and types from SQLAlchemy models...")
        Base.metadata.create_all(bind=engine)
        print("  SUCCESS: Tables created from models")
        
        # Also try to execute the SQL file for additional objects (indexes, triggers, etc.)
        print("  Executing additional SQL statements (indexes, triggers, comments)...")
        with engine.connect() as conn:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Execute the entire SQL file using psycopg2 directly for better compatibility
            import psycopg2
            from urllib.parse import urlparse
            
            parsed = urlparse(DATABASE_URL)
            pg_conn = psycopg2.connect(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 5432,
                database=parsed.path[1:] if parsed.path else 'postgres',
                user=parsed.username or 'postgres',
                password=parsed.password or ''
            )
            pg_conn.autocommit = True
            pg_cursor = pg_conn.cursor()
            
            try:
                # Execute the SQL file
                pg_cursor.execute(schema_sql)
                print("  SUCCESS: Additional SQL objects created")
            except Exception as e:
                # Many objects might already exist, which is OK
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  OK: Some objects already exist (this is normal)")
                else:
                    print(f"  WARNING: Some SQL execution issues (may be expected): {e}")
            finally:
                pg_cursor.close()
                pg_conn.close()
        
        print("SUCCESS: Database schema created successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR: Error creating schema: {e}")
        import traceback
        traceback.print_exc()
        return False

def import_data():
    """Import data from CSV"""
    print("\n" + "=" * 70)
    print("Step 2: Importing Data from CSV")
    print("=" * 70)
    
    try:
        # Import the migration script
        import migrate_from_csv
        
        # Run the migration by executing the script logic
        csv_file = Path(__file__).parent.parent / "credit_card_rates.csv"
        if not csv_file.exists():
            print(f"ERROR: CSV file not found: {csv_file}")
            return False
        
        # Call the migration logic directly
        from migrate_from_csv import parse_date, parse_decimal, parse_int
        from fee_engine_service import SessionLocal, CardFeeMaster
        from decimal import Decimal
        import csv
        
        db = SessionLocal()
        imported = 0
        skipped = 0
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip empty rows
                    if not row.get('fee_id') or not row.get('charge_type'):
                        continue
                    
                    try:
                        # Check if record already exists
                        existing = db.query(CardFeeMaster).filter(
                            CardFeeMaster.charge_type == row['charge_type'],
                            CardFeeMaster.card_category == row.get('card_category', ''),
                            CardFeeMaster.card_network == row.get('card_network', ''),
                            CardFeeMaster.card_product == row.get('card_product', '')
                        ).first()
                        
                        if existing:
                            skipped += 1
                            continue
                        
                        # Create new record
                        fee_record = CardFeeMaster(
                            effective_from=parse_date(row.get('effective_from', '')),
                            effective_to=parse_date(row.get('effective_to', '')),
                            charge_type=row['charge_type'],
                            card_category=row.get('card_category', 'ANY'),
                            card_network=row.get('card_network', 'ANY'),
                            card_product=row.get('card_product', ''),
                            full_card_name=row.get('full_card_name', ''),
                            fee_value=parse_decimal(row.get('fee_value', '0')) or Decimal('0'),
                            fee_unit=row.get('fee_unit', 'BDT'),
                            fee_basis=row.get('fee_basis', 'PER_TXN'),
                            min_fee_value=parse_decimal(row.get('min_fee_value', '')),
                            min_fee_unit=row.get('min_fee_unit', ''),
                            max_fee_value=parse_decimal(row.get('max_fee_value', '')),
                            free_entitlement_count=parse_int(row.get('free_entitlement_count', '')),
                            condition_type=row.get('condition_type', 'NONE'),
                            note_reference=row.get('note_reference', ''),
                            priority=parse_int(row.get('priority', '100')) or 100,
                            status=row.get('status', 'ACTIVE'),
                            remarks=row.get('remarks', '')
                        )
                        
                        db.add(fee_record)
                        imported += 1
                        
                        if imported % 10 == 0:
                            db.commit()
                            print(f"  Imported {imported} records...")
                    
                    except Exception as e:
                        print(f"  WARNING: Error importing row {row.get('fee_id', 'unknown')}: {e}")
                        db.rollback()
                        skipped += 1
                        continue
            
            db.commit()
            print(f"SUCCESS: Data import completed!")
            print(f"  Imported: {imported} records")
            print(f"  Skipped: {skipped} records")
            return True
            
        finally:
            db.close()
        
    except Exception as e:
        print(f"ERROR: Error importing data: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_data():
    """Verify data was imported correctly"""
    print("\n" + "=" * 70)
    print("Step 3: Verifying Data Import")
    print("=" * 70)
    
    try:
        from fee_engine_service import SessionLocal, CardFeeMaster
        
        db = SessionLocal()
        try:
            count = db.query(CardFeeMaster).count()
            print(f"SUCCESS: Total records in card_fee_master: {count}")
            
            # Check for World RFCD Debit
            rfcd_count = db.query(CardFeeMaster).filter(
                CardFeeMaster.card_category == 'DEBIT',
                CardFeeMaster.card_network == 'MASTERCARD',
                CardFeeMaster.card_product.like('%RFCD%')
            ).count()
            
            if rfcd_count > 0:
                rfcd_record = db.query(CardFeeMaster).filter(
                    CardFeeMaster.card_category == 'DEBIT',
                    CardFeeMaster.card_network == 'MASTERCARD',
                    CardFeeMaster.card_product.like('%RFCD%')
                ).first()
                
                print(f"SUCCESS: Found World RFCD Debit entry:")
                print(f"   - Fee: {rfcd_record.fee_value} {rfcd_record.fee_unit}")
                print(f"   - Product: {rfcd_record.card_product}")
            else:
                print("WARNING: World RFCD Debit entry not found")
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"ERROR: Error verifying data: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main deployment function"""
    print("\n" + "=" * 70)
    print("Fee Engine Service Deployment")
    print("=" * 70)
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("=" * 70 + "\n")
    
    # Step 1: Create schema
    if not create_schema():
        print("\nERROR: Schema creation failed. Aborting.")
        return False
    
    # Step 2: Import data
    if not import_data():
        print("\nERROR: Data import failed. Aborting.")
        return False
    
    # Step 3: Verify data
    if not verify_data():
        print("\nWARNING: Data verification had issues, but continuing...")
    
    print("\n" + "=" * 70)
    print("SUCCESS: Deployment Complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Start the fee-engine service:")
    print("   cd credit_card_rate")
    print("   python fee_engine/run_service.py")
    print("\n2. Or set environment variables and run:")
    print("   $env:FEE_ENGINE_PORT='8003'")
    print("   python fee_engine/run_service.py")
    print("\n3. Test the service:")
    print("   curl http://localhost:8003/health")
    print("=" * 70 + "\n")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
