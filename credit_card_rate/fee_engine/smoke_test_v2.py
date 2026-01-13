"""
Minimal production smoke test for v2 migration
Tests 3 key scenarios to ensure v2 is working correctly
"""
import os
from datetime import date
from sqlalchemy import create_engine, text

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

def run_smoke_test():
    """Run minimal smoke tests"""
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    print("=" * 70)
    print("Production Smoke Test for retail_asset_charge_master_v2")
    print("=" * 70)
    
    as_of_date = date.today()
    print(f"\nTesting with as_of_date: {as_of_date}")
    
    with engine.connect() as conn:
        # Test 1: General fee (GENERAL context)
        print("\n[Test 1] General fee (GENERAL context):")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT charge_id, loan_product, charge_type, charge_context, charge_title, fee_value, fee_unit
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND charge_type = 'PROCESSING_FEE'
              AND charge_context = 'GENERAL'
              AND status = 'ACTIVE'
              AND effective_from <= :as_of_date
              AND (effective_to IS NULL OR effective_to >= :as_of_date)
            ORDER BY effective_from DESC, priority DESC
            LIMIT 1
        """), {'as_of_date': as_of_date})
        row = result.fetchone()
        if row:
            print(f"✅ Found general fee:")
            print(f"   Charge ID: {row[0]}")
            print(f"   Loan Product: {row[1]}")
            print(f"   Charge Type: {row[2]}")
            print(f"   Charge Context: {row[3]}")
            print(f"   Title: {row[4]}")
            print(f"   Fee: {row[5]} {row[6] if row[6] else 'N/A'}")
        else:
            print("❌ No general fee found")
        
        # Test 2: On-limit fee (ON_LIMIT context)
        print("\n[Test 2] On-limit fee (ON_LIMIT context):")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT charge_id, loan_product, charge_type, charge_context, charge_title, fee_value, fee_unit
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND charge_type = 'PROCESSING_FEE'
              AND charge_context = 'ON_LIMIT'
              AND status = 'ACTIVE'
              AND effective_from <= :as_of_date
              AND (effective_to IS NULL OR effective_to >= :as_of_date)
            ORDER BY effective_from DESC, priority DESC
            LIMIT 1
        """), {'as_of_date': as_of_date})
        row = result.fetchone()
        if row:
            print(f"✅ Found on-limit fee:")
            print(f"   Charge ID: {row[0]}")
            print(f"   Loan Product: {row[1]}")
            print(f"   Charge Type: {row[2]}")
            print(f"   Charge Context: {row[3]}")
            print(f"   Title: {row[4]}")
            print(f"   Fee: {row[5]} {row[6] if row[6] else 'N/A'}")
        else:
            print("ℹ️  No on-limit fee found (this is OK if not all products have on-limit fees)")
        
        # Test 3: Enhancement fee (ON_ENHANCED_AMOUNT context)
        print("\n[Test 3] Enhancement fee (ON_ENHANCED_AMOUNT context):")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT charge_id, loan_product, charge_type, charge_context, charge_title, fee_value, fee_unit
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND charge_type = 'LIMIT_ENHANCEMENT_FEE'
              AND charge_context = 'ON_ENHANCED_AMOUNT'
              AND status = 'ACTIVE'
              AND effective_from <= :as_of_date
              AND (effective_to IS NULL OR effective_to >= :as_of_date)
            ORDER BY effective_from DESC, priority DESC
            LIMIT 1
        """), {'as_of_date': as_of_date})
        row = result.fetchone()
        if row:
            print(f"✅ Found enhancement fee:")
            print(f"   Charge ID: {row[0]}")
            print(f"   Loan Product: {row[1]}")
            print(f"   Charge Type: {row[2]}")
            print(f"   Charge Context: {row[3]}")
            print(f"   Title: {row[4]}")
            print(f"   Fee: {row[5]} {row[6] if row[6] else 'N/A'}")
        else:
            # Try with PROCESSING_FEE instead
            result2 = conn.execute(text("""
                SELECT charge_id, loan_product, charge_type, charge_context, charge_title, fee_value, fee_unit
                FROM retail_asset_charge_master_v2
                WHERE loan_product = 'FAST_CASH_OD'
                  AND charge_type = 'PROCESSING_FEE'
                  AND charge_context = 'ON_ENHANCED_AMOUNT'
                  AND status = 'ACTIVE'
                  AND effective_from <= :as_of_date
                  AND (effective_to IS NULL OR effective_to >= :as_of_date)
                ORDER BY effective_from DESC, priority DESC
                LIMIT 1
            """), {'as_of_date': as_of_date})
            row2 = result2.fetchone()
            if row2:
                print(f"✅ Found enhancement fee (as PROCESSING_FEE):")
                print(f"   Charge ID: {row2[0]}")
                print(f"   Loan Product: {row2[1]}")
                print(f"   Charge Type: {row2[2]}")
                print(f"   Charge Context: {row2[3]}")
                print(f"   Title: {row2[4]}")
                print(f"   Fee: {row2[5]} {row2[6] if row2[6] else 'N/A'}")
            else:
                print("ℹ️  No enhancement fee found (this is OK if not all products have enhancement fees)")
        
        # Test 4: Check all valid contexts exist
        print("\n[Test 4] Valid charge_context values:")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT DISTINCT charge_context, COUNT(*) as count
            FROM retail_asset_charge_master_v2
            WHERE status = 'ACTIVE'
            GROUP BY charge_context
            ORDER BY charge_context
        """))
        contexts = result.fetchall()
        valid_contexts = {'GENERAL', 'ON_LIMIT', 'ON_ENHANCED_AMOUNT', 'ON_REDUCED_AMOUNT'}
        found_contexts = {row[0] for row in contexts}
        print(f"Found contexts: {', '.join(sorted(found_contexts))}")
        if found_contexts.issubset(valid_contexts):
            print("✅ All contexts are valid (GENERAL, ON_LIMIT, ON_ENHANCED_AMOUNT, ON_REDUCED_AMOUNT)")
            for row in contexts:
                print(f"   - {row[0]}: {row[1]} record(s)")
        else:
            invalid = found_contexts - valid_contexts
            print(f"❌ Found invalid context(s): {', '.join(invalid)}")
    
    print("\n" + "=" * 70)
    print("Smoke test complete!")
    print("=" * 70)

if __name__ == "__main__":
    run_smoke_test()

