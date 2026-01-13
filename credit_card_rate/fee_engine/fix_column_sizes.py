"""
Fix column sizes to prevent data truncation errors
"""
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / 'bank_chatbot' / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Get database URL
def get_database_url():
    url = os.getenv("FEE_ENGINE_DB_URL") or os.getenv("POSTGRES_DB_URL")
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

def main():
    print("="*70)
    print("Fixing Column Sizes")
    print("="*70)
    
    engine = create_engine(get_database_url())
    
    try:
        with engine.connect() as conn:
            print("\n1. Updating charge_type from VARCHAR(100) to VARCHAR(255)...")
            conn.execute(text("""
                ALTER TABLE card_fee_master 
                ALTER COLUMN charge_type TYPE VARCHAR(255)
            """))
            conn.commit()
            print("   [OK] charge_type updated")
            
            print("\n2. Updating card_product from VARCHAR(50) to VARCHAR(100)...")
            conn.execute(text("""
                ALTER TABLE card_fee_master 
                ALTER COLUMN card_product TYPE VARCHAR(100)
            """))
            conn.commit()
            print("   [OK] card_product updated")
            
            print("\n3. Updating note_reference from VARCHAR(20) to VARCHAR(200)...")
            conn.execute(text("""
                ALTER TABLE card_fee_master 
                ALTER COLUMN note_reference TYPE VARCHAR(200)
            """))
            conn.commit()
            print("   [OK] note_reference updated")
            
            print("\n" + "="*70)
            print("Column sizes fixed successfully!")
            print("="*70)
            
    except Exception as e:
        print(f"\n[ERROR] Failed to update column sizes: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

