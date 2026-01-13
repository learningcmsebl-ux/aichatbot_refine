#!/usr/bin/env python3
"""Check if credit_card_rates.csv data has been imported into PostgreSQL"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from bank_chatbot directory
env_path = Path(__file__).parent.parent / "bank_chatbot" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try current directory
    load_dotenv()

def get_database_url():
    """Construct database URL from environment variables"""
    # Try FEE_ENGINE_DB_URL first
    url = os.getenv("FEE_ENGINE_DB_URL")
    if url:
        return url
    
    # Try POSTGRES_DB_URL
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    # Construct from individual variables
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'postgres')
    
    # URL encode password if it contains special characters
    from urllib.parse import quote_plus
    password_encoded = quote_plus(password) if password else ''
    
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

def main():
    database_url = get_database_url()
    
    print("="*60)
    print("Checking PostgreSQL for credit_card_rates.csv data")
    print("="*60)
    print(f"Database URL: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    print()
    
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'card_fee_master'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("[ERROR] Table 'card_fee_master' does NOT exist!")
                print()
                print("To create the table, run:")
                print("  psql -U postgres -d postgres -f credit_card_rate/fee_engine/schema.sql")
                return
            
            print("[OK] Table 'card_fee_master' exists")
            print()
            
            # Count records
            result = conn.execute(text("SELECT COUNT(*) FROM card_fee_master"))
            count = result.scalar()
            print(f"[INFO] Total records in card_fee_master: {count}")
            print()
            
            if count == 0:
                print("[ERROR] No data found in card_fee_master table!")
                print()
                print("To import data from CSV, run:")
                print("  cd credit_card_rate")
                print("  python fee_engine/migrate_from_csv.py")
                return
            
            # Check for active records
            result = conn.execute(text("SELECT COUNT(*) FROM card_fee_master WHERE status = 'ACTIVE'"))
            active_count = result.scalar()
            print(f"[OK] Active records: {active_count}")
            print()
            
            # Show sample records
            print("Sample records (first 5):")
            print("-" * 60)
            result = conn.execute(text("""
                SELECT 
                    charge_type,
                    card_category,
                    card_network,
                    card_product,
                    fee_value,
                    fee_unit,
                    effective_from
                FROM card_fee_master 
                WHERE status = 'ACTIVE'
                ORDER BY effective_from DESC, priority DESC
                LIMIT 5
            """))
            
            for row in result:
                print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} {row[5]} | From: {row[6]}")
            print()
            
            # Check CSV file
            csv_path = Path(__file__).parent / "credit_card_rates.csv"
            if csv_path.exists():
                import csv
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    csv_rows = list(reader)
                    csv_count = len([r for r in csv_rows if r.get('charge_type', '').strip()])
                
                print(f"[INFO] CSV file has {csv_count} records")
                print()
                
                if csv_count > count:
                    print(f"[WARNING] CSV has more records ({csv_count}) than database ({count})")
                    print("   You may need to re-import the data.")
                elif csv_count == count:
                    print("[OK] CSV record count matches database")
                else:
                    print(f"[INFO] Database has more records ({count}) than CSV ({csv_count})")
                    print("   This is normal if data was modified after import.")
            else:
                print("[WARNING] CSV file not found: credit_card_rates.csv")
            
            print()
            print("="*60)
            print("Summary:")
            print("="*60)
            if count > 0:
                print("[OK] Data has been imported into PostgreSQL")
            else:
                print("[ERROR] Data has NOT been imported into PostgreSQL")
                print()
                print("Next steps:")
                print("1. Ensure the table exists: python fee_engine/deploy_fee_engine.py")
                print("2. Import data: python fee_engine/migrate_from_csv.py")
            
    except Exception as e:
        print(f"[ERROR] Error connecting to database: {e}")
        print()
        print("Please check:")
        print("  - Database is running")
        print("  - Connection credentials in .env file")
        print("  - Network connectivity")

if __name__ == "__main__":
    main()

