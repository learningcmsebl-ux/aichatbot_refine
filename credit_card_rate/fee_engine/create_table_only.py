"""Create retail_asset_charge_master table only"""
import sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url

# Read the schema file and extract just the CREATE TABLE statement
schema_file = '/tmp/retail_asset_schema.sql'
with open(schema_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the CREATE TABLE statement (from CREATE TABLE to the closing parenthesis and semicolon)
import re
table_match = re.search(r'CREATE TABLE retail_asset_charge_master.*?\);', content, re.DOTALL | re.IGNORECASE)
if not table_match:
    print("Could not find CREATE TABLE statement")
    sys.exit(1)

create_table_sql = table_match.group(0)
print("Found CREATE TABLE statement")
print(f"Length: {len(create_table_sql)} characters")

engine = create_engine(get_database_url(), pool_pre_ping=True)
conn = engine.connect()

try:
    print("Creating table...")
    conn.execute(text(create_table_sql))
    conn.commit()
    print("[SUCCESS] Table created!")
except Exception as e:
    conn.rollback()
    print(f"[ERROR] {e}")
    # Check if table already exists
    if 'already exists' in str(e).lower():
        print("Table may already exist, continuing...")
    else:
        sys.exit(1)
finally:
    conn.close()









