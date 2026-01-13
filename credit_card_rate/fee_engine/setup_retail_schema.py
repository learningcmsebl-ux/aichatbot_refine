"""Setup Retail Asset Schema - handles existing types"""
import sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url

schema_file = '/tmp/retail_asset_schema.sql'
print('Reading schema file...')
with open(schema_file, 'r', encoding='utf-8') as f:
    schema_sql = f.read()

print('Connecting to database...')
engine = create_engine(get_database_url(), pool_pre_ping=True)
conn = engine.connect()

statements = [s.strip() for s in schema_sql.split(';') if s.strip() and not s.strip().startswith('--')]
print(f'Found {len(statements)} statements')

executed = 0
skipped = 0
errors = []

for i, stmt in enumerate(statements, 1):
    if not stmt:
        continue
    try:
        conn.execute(text(stmt))
        conn.commit()
        executed += 1
    except Exception as e:
        conn.rollback()  # Rollback on error
        err = str(e).lower()
        if 'already exists' in err or 'duplicate' in err:
            skipped += 1
        else:
            errors.append(f"Statement {i}: {e}")

conn.close()

if errors:
    print(f'\n[WARNING] {len(errors)} errors occurred:')
    for err in errors[:5]:  # Show first 5 errors
        print(f'  {err}')
else:
    print(f'\n[SUCCESS] Schema setup completed!')
    print(f'  Executed: {executed} statements')
    print(f'  Skipped (already exists): {skipped} statements')

