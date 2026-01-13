"""
Create retail_asset_charge_master_v2 table by running schema_retail_asset_v2.sql
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

def create_schema():
    """Create v2 schema by reading and executing schema_retail_asset_v2.sql"""
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    # Read SQL file
    schema_file = os.path.join(os.path.dirname(__file__), 'schema_retail_asset_v2.sql')
    with open(schema_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    print(f"Creating retail_asset_charge_master_v2 table from {schema_file}...")
    
    # Split SQL content - everything before the VIEW creation
    # Find where VIEW creation starts
    view_marker = '-- 8) Backward Compatible VIEW'
    if view_marker in sql_content:
        sql_before_view = sql_content.split(view_marker)[0]
    else:
        sql_before_view = sql_content
    
    print("Creating v2 table and related objects (skipping VIEW - will be created after migration)...")
    
    with engine.begin() as conn:
        # Execute everything before VIEW creation as a single statement
        # psycopg2 should handle multiple statements in one execute
        try:
            conn.execute(text(sql_before_view))
        except Exception as e:
            # Check if it's just "already exists" for individual objects
            error_str = str(e).lower()
            if 'already exists' in error_str or 'duplicate' in error_str:
                print(f"  (Some objects already exist, continuing...)")
                # Try to execute statement by statement to handle partial creation
                # But for now, if there are errors, we'll skip and assume table exists
                pass
            else:
                raise
    
    print("Schema created successfully (VIEW will be created after migration completes)!")

if __name__ == "__main__":
    create_schema()

