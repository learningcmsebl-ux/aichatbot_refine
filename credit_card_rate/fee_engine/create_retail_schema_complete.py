"""Create retail asset schema - handles enums, table, indexes, triggers"""
import sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url
import re

schema_file = '/tmp/retail_asset_schema.sql'
with open(schema_file, 'r', encoding='utf-8') as f:
    content = f.read()

engine = create_engine(get_database_url(), pool_pre_ping=True)
conn = engine.connect()

# Extract and execute CREATE TYPE statements first
type_pattern = r'CREATE TYPE (\w+_enum) AS ENUM[^;]+;'
type_matches = re.finditer(type_pattern, content, re.IGNORECASE | re.DOTALL)

print("Creating enum types...")
for match in type_matches:
    type_sql = match.group(0)
    type_name = match.group(1)
    try:
        conn.execute(text(type_sql))
        conn.commit()
        print(f"  Created {type_name}")
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e).lower():
            print(f"  {type_name} already exists, skipping")
        else:
            print(f"  Error creating {type_name}: {e}")

# Extract and execute CREATE TABLE
print("\nCreating table...")
table_match = re.search(r'CREATE TABLE retail_asset_charge_master.*?\);', content, re.DOTALL | re.IGNORECASE)
if table_match:
    table_sql = table_match.group(0)
    try:
        conn.execute(text(table_sql))
        conn.commit()
        print("  Table created successfully!")
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e).lower():
            print("  Table already exists, skipping")
        else:
            print(f"  Error: {e}")
            sys.exit(1)
else:
    print("  Could not find CREATE TABLE statement")

# Extract and execute CREATE INDEX statements
print("\nCreating indexes...")
index_pattern = r'CREATE INDEX[^;]+;'
index_matches = re.finditer(index_pattern, content, re.IGNORECASE | re.DOTALL)

for match in index_matches:
    index_sql = match.group(0)
    try:
        conn.execute(text(index_sql))
        conn.commit()
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e).lower():
            pass  # Skip silently
        else:
            print(f"  Warning: {e}")

# Extract and execute CREATE FUNCTION
print("\nCreating function...")
func_match = re.search(r'CREATE OR REPLACE FUNCTION update_retail_asset_charge_updated_at.*?\$\$ language', content, re.DOTALL | re.IGNORECASE)
if func_match:
    # Get the full function including the language part
    func_start = func_match.start()
    func_end = content.find('$$ language', func_start) + len('$$ language \'plpgsql\';')
    func_sql = content[func_start:func_end]
    try:
        conn.execute(text(func_sql))
        conn.commit()
        print("  Function created!")
    except Exception as e:
        conn.rollback()
        print(f"  Warning: {e}")

# Extract and execute CREATE TRIGGER
print("\nCreating trigger...")
trigger_match = re.search(r'CREATE TRIGGER update_retail_asset_charge_master_updated_at.*?;', content, re.DOTALL | re.IGNORECASE)
if trigger_match:
    trigger_sql = trigger_match.group(0)
    try:
        conn.execute(text(trigger_sql))
        conn.commit()
        print("  Trigger created!")
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e).lower():
            print("  Trigger already exists, skipping")
        else:
            print(f"  Warning: {e}")

conn.close()
print("\n[SUCCESS] Schema setup completed!")









