"""
Verification queries for retail_asset_charge_master_v2 migration
"""
import os
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

def run_verification():
    """Run all verification queries"""
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    print("=" * 70)
    print("Retail Asset Charge v2 Migration Verification")
    print("=" * 70)
    
    with engine.connect() as conn:
        # A) Row count sanity
        print("\n[A] Row count sanity check:")
        print("-" * 70)
        result = conn.execute(text("SELECT COUNT(*) FROM retail_asset_charge_master_v2"))
        count = result.scalar()
        print(f"Total rows in retail_asset_charge_master_v2: {count}")
        if count == 38:
            print("✅ Expected 38 rows (matches migration output)")
        else:
            print(f"⚠️  Expected 38 rows, found {count}")
        
        # B) Any invalid/blank contexts?
        print("\n[B] Check for NULL charge_context values:")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM retail_asset_charge_master_v2
            WHERE charge_context IS NULL
        """))
        null_count = result.scalar()
        print(f"Rows with NULL charge_context: {null_count}")
        if null_count == 0:
            print("✅ All rows have valid charge_context values")
        else:
            print(f"❌ Found {null_count} rows with NULL charge_context (should be 0)")
        
        # C) Determinism collisions per key
        print("\n[C] Check for determinism collisions (duplicate keys):")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT loan_product, charge_type, charge_context, effective_from, COUNT(*)
            FROM retail_asset_charge_master_v2
            WHERE status='ACTIVE'
            GROUP BY loan_product, charge_type, charge_context, effective_from
            HAVING COUNT(*) > 1
        """))
        collisions = result.fetchall()
        if len(collisions) == 0:
            print("✅ No determinism collisions found (all keys are unique)")
        else:
            print(f"❌ Found {len(collisions)} collision(s):")
            for row in collisions:
                print(f"   - {row[0]}, {row[1]}, {row[2]}, {row[3]}: {row[4]} rows")
        
        # D) Effective date overlaps
        print("\n[D] Check for effective date overlaps:")
        print("-" * 70)
        result = conn.execute(text("""
            SELECT a.loan_product, a.charge_type, a.charge_context, 
                   a.charge_id, a.effective_from, COALESCE(a.effective_to, 'infinity'::date) as a_to,
                   b.charge_id, b.effective_from, COALESCE(b.effective_to, 'infinity'::date) as b_to
            FROM retail_asset_charge_master_v2 a
            JOIN retail_asset_charge_master_v2 b
              ON a.loan_product=b.loan_product
             AND a.charge_type=b.charge_type
             AND a.charge_context=b.charge_context
             AND a.charge_id < b.charge_id
            WHERE a.status='ACTIVE' AND b.status='ACTIVE'
              AND daterange(a.effective_from, COALESCE(a.effective_to,'infinity'::date),'[]')
               && daterange(b.effective_from, COALESCE(b.effective_to,'infinity'::date),'[]')
        """))
        overlaps = result.fetchall()
        if len(overlaps) == 0:
            print("✅ No effective date overlaps found")
        else:
            print(f"⚠️  Found {len(overlaps)} overlap(s):")
            for row in overlaps:
                print(f"   - {row[0]}, {row[1]}, {row[2]}:")
                print(f"     Charge A (ID: {row[3]}): {row[4]} to {row[5]}")
                print(f"     Charge B (ID: {row[6]}): {row[7]} to {row[8]}")
            print("\n   Note: Overlaps are not fatal if code picks latest effective_from,")
            print("   but it's better to enforce non-overlap at DB level")
    
    print("\n" + "=" * 70)
    print("Verification complete!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()

