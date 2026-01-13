"""
Apply guardrails: lock down v1 table and add exclusion constraint to v2
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

def apply_guardrails():
    """Apply guardrails to lock down v1 and add constraints to v2"""
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    print("=" * 70)
    print("Applying Guardrails: Lock Down v1 and Add Exclusion Constraint")
    print("=" * 70)
    
    # Execute SQL directly (don't read from file to avoid path issues)
    with engine.begin() as conn:
        print("\n1) Locking down v1 table (revoking write permissions)...")
        try:
            # Lock down v1 table
            conn.execute(text("REVOKE INSERT, UPDATE, DELETE ON retail_asset_charge_master FROM PUBLIC"))
            conn.execute(text("""
                COMMENT ON TABLE retail_asset_charge_master IS 
                'DEPRECATED: Use retail_asset_charge_master_v2 instead. This table is read-only and will be removed in a future migration.'
            """))
            print("   ✅ v1 table locked down (write permissions revoked)")
        except Exception as e:
            print(f"   ⚠️  Warning: {str(e)} (may not have permissions or table may not exist)")
        
        print("\n2) Adding exclusion constraint to v2 table...")
        try:
            # Enable extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
            
            # Add exclusion constraint
            conn.execute(text("""
                ALTER TABLE retail_asset_charge_master_v2
                ADD CONSTRAINT no_overlap_active_rules
                EXCLUDE USING gist (
                  loan_product WITH =,
                  charge_type WITH =,
                  charge_context WITH =,
                  daterange(effective_from, COALESCE(effective_to, 'infinity'::date), '[]') WITH &&
                )
                WHERE (status = 'ACTIVE')
            """))
            print("   ✅ Exclusion constraint added successfully")
        except Exception as e:
            error_str = str(e).lower()
            if 'already exists' in error_str:
                print("   ℹ️  Constraint already exists (skipping)")
            else:
                print(f"   ❌ Error: {str(e)}")
                raise
    
    print("\n" + "=" * 70)
    print("Guardrails applied successfully!")
    print("=" * 70)

if __name__ == "__main__":
    apply_guardrails()

