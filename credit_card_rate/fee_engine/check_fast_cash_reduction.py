"""
Check Fast Cash limit reduction fee in database
"""
import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def get_database_url():
    user = os.getenv('POSTGRES_USER', 'chatbot_user')
    password = os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')
    host = os.getenv('POSTGRES_HOST', 'host.docker.internal')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'chatbot_db')
    return f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{db}"

def check_data():
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    with engine.connect() as conn:
        # Check for LIMIT_REDUCTION_FEE
        print("Checking for LIMIT_REDUCTION_FEE charges:")
        result = conn.execute(text("""
            SELECT loan_product, charge_type, charge_context, charge_title, charge_description
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND charge_type = 'LIMIT_REDUCTION_FEE'
              AND status = 'ACTIVE'
            ORDER BY charge_context
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  ✓ Found: {row[0]} | {row[1]} | {row[2]} | {row[3]}")
        else:
            print("  ✗ No LIMIT_REDUCTION_FEE found")
        
        # Check for PROCESSING_FEE with ON_REDUCED_AMOUNT context
        print("\nChecking for PROCESSING_FEE with ON_REDUCED_AMOUNT context:")
        result = conn.execute(text("""
            SELECT loan_product, charge_type, charge_context, charge_title, charge_description
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND charge_type = 'PROCESSING_FEE'
              AND charge_context = 'ON_REDUCED_AMOUNT'
              AND status = 'ACTIVE'
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  ✓ Found: {row[0]} | {row[1]} | {row[2]} | {row[3]}")
        else:
            print("  ✗ No PROCESSING_FEE with ON_REDUCED_AMOUNT found")
        
        # Check all FAST_CASH_OD charges
        print("\nAll FAST_CASH_OD charges:")
        result = conn.execute(text("""
            SELECT loan_product, charge_type, charge_context, charge_title
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND status = 'ACTIVE'
            ORDER BY charge_type, charge_context
        """))
        rows = result.fetchall()
        for row in rows:
            print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]}")

if __name__ == "__main__":
    check_data()

