"""
Create Retail Asset Charge Master Schema
"""

from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url
import os

def create_schema():
    """Create the retail_asset_charge_master table schema"""
    
    schema_file = os.path.join(os.path.dirname(__file__), 'retail_asset_schema.sql')
    
    if not os.path.exists(schema_file):
        print(f"Error: Schema file not found at {schema_file}")
        return False
    
    print(f"Reading schema file: {schema_file}")
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    print(f"Schema file size: {len(schema_sql)} bytes")
    print("Connecting to database...")
    
    try:
        engine = create_engine(get_database_url(), pool_pre_ping=True)
        conn = engine.connect()
        
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in schema_sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        print(f"Found {len(statements)} statements to execute")
        print("Creating schema...")
        
        executed = 0
        for i, stmt in enumerate(statements, 1):
            if not stmt:
                continue
            try:
                conn.execute(text(stmt))
                conn.commit()
                executed += 1
                if i % 5 == 0:
                    print(f"  Executed {i}/{len(statements)} statements...")
            except Exception as e:
                error_msg = str(e).lower()
                if 'already exists' not in error_msg and 'duplicate' not in error_msg:
                    print(f"  Warning on statement {i}: {e}")
                # Continue even if some things already exist
        
        conn.close()
        print(f"\n[SUCCESS] Schema creation completed! Executed {executed} statements")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error creating schema: {e}")
        return False

if __name__ == "__main__":
    success = create_schema()
    if success:
        print("\nYou can now import data using:")
        print("  python import_retail_asset_charges.py")
    else:
        print("\nSchema creation failed. Please check the error messages above.")

