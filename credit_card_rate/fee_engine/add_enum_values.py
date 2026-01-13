"""Add missing enum values for retail asset charges"""
import sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url

engine = create_engine(get_database_url(), pool_pre_ping=True)
conn = engine.connect()

# Values to add to fee_basis_enum
fee_basis_new_values = ['PER_LOAN', 'PER_AMOUNT', 'PER_INSTALLMENT', 'PER_INSTANCE', 'ON_OVERDUE', 'PER_QUOTATION_CHANGE']

# Values to add to fee_unit_enum
fee_unit_new_values = ['ACTUAL_COST']

# Values to add to condition_type_enum
condition_type_new_values = ['TIERED']

print("Adding enum values...")

# Check existing values and add missing ones
try:
    # Get existing fee_basis_enum values
    result = conn.execute(text("SELECT unnest(enum_range(NULL::fee_basis_enum))"))
    existing_fee_basis = [row[0] for row in result]
    print(f"Existing fee_basis_enum values: {existing_fee_basis}")
    
    for value in fee_basis_new_values:
        if value not in existing_fee_basis:
            try:
                # Note: ALTER TYPE ADD VALUE cannot be in a transaction block
                conn.execute(text(f"ALTER TYPE fee_basis_enum ADD VALUE '{value}'"))
                conn.commit()
                print(f"  Added '{value}' to fee_basis_enum")
            except Exception as e:
                if 'already exists' not in str(e).lower():
                    print(f"  Warning adding '{value}': {e}")
                conn.rollback()
except Exception as e:
    print(f"Error checking fee_basis_enum: {e}")

try:
    # Get existing fee_unit_enum values
    result = conn.execute(text("SELECT unnest(enum_range(NULL::fee_unit_enum))"))
    existing_fee_unit = [row[0] for row in result]
    print(f"Existing fee_unit_enum values: {existing_fee_unit}")
    
    for value in fee_unit_new_values:
        if value not in existing_fee_unit:
            try:
                conn.execute(text(f"ALTER TYPE fee_unit_enum ADD VALUE '{value}'"))
                conn.commit()
                print(f"  Added '{value}' to fee_unit_enum")
            except Exception as e:
                if 'already exists' not in str(e).lower():
                    print(f"  Warning adding '{value}': {e}")
                conn.rollback()
except Exception as e:
    print(f"Error checking fee_unit_enum: {e}")

try:
    # Get existing condition_type_enum values
    result = conn.execute(text("SELECT unnest(enum_range(NULL::condition_type_enum))"))
    existing_condition = [row[0] for row in result]
    print(f"Existing condition_type_enum values: {existing_condition}")
    
    for value in condition_type_new_values:
        if value not in existing_condition:
            try:
                conn.execute(text(f"ALTER TYPE condition_type_enum ADD VALUE '{value}'"))
                conn.commit()
                print(f"  Added '{value}' to condition_type_enum")
            except Exception as e:
                if 'already exists' not in str(e).lower():
                    print(f"  Warning adding '{value}': {e}")
                conn.rollback()
except Exception as e:
    print(f"Error checking condition_type_enum: {e}")

conn.close()
print("\n[SUCCESS] Enum values updated!")









