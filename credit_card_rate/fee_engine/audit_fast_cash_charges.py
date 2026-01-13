"""
Audit Fast Cash charges to confirm data model reality
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

def audit_fast_cash():
    DATABASE_URL = get_database_url()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    print("=" * 70)
    print("Fast Cash (FAST_CASH_OD) Charge Type Audit")
    print("=" * 70)
    
    with engine.connect() as conn:
        # Audit query: group by charge_type and charge_context
        result = conn.execute(text("""
            SELECT charge_type, charge_context, COUNT(*) as count
            FROM retail_asset_charge_master_v2
            WHERE loan_product = 'FAST_CASH_OD'
              AND status='ACTIVE'
            GROUP BY charge_type, charge_context
            ORDER BY charge_type, charge_context
        """))
        rows = result.fetchall()
        
        print("\nCharge Type Distribution:")
        print("-" * 70)
        print(f"{'Charge Type':<30} {'Charge Context':<25} {'Count':<10}")
        print("-" * 70)
        for row in rows:
            print(f"{row[0]:<30} {row[1]:<25} {row[2]:<10}")
        
        # Check for LIMIT_ENHANCEMENT_FEE and LIMIT_REDUCTION_FEE
        has_limit_enhancement = any(r[0] == 'LIMIT_ENHANCEMENT_FEE' for r in rows)
        has_limit_reduction = any(r[0] == 'LIMIT_REDUCTION_FEE' for r in rows)
        has_processing_fee = any(r[0] == 'PROCESSING_FEE' for r in rows)
        
        print("\n" + "=" * 70)
        print("Data Model Analysis:")
        print("=" * 70)
        
        if has_processing_fee and not has_limit_enhancement and not has_limit_reduction:
            print("✅ CONFIRMED: Fast Cash uses PROCESSING_FEE with charge_context")
            print("   - Enhancement/reduction processing fees are modeled as:")
            print("     PROCESSING_FEE + ON_ENHANCED_AMOUNT")
            print("     PROCESSING_FEE + ON_REDUCED_AMOUNT")
            print("   - NOT as separate LIMIT_ENHANCEMENT_FEE/LIMIT_REDUCTION_FEE charge_types")
        elif has_limit_enhancement or has_limit_reduction:
            print("⚠️  MIXED MODEL: Fast Cash has both PROCESSING_FEE and LIMIT_*_FEE charge_types")
            print("   - Need to check other loan products to determine if this is consistent")
        else:
            print("❓ UNKNOWN: No PROCESSING_FEE found for Fast Cash")
        
        # Check other loan products for comparison
        print("\n" + "=" * 70)
        print("Other Loan Products - LIMIT_*_FEE Usage:")
        print("=" * 70)
        result2 = conn.execute(text("""
            SELECT loan_product, charge_type, COUNT(*) as count
            FROM retail_asset_charge_master_v2
            WHERE charge_type IN ('LIMIT_ENHANCEMENT_FEE', 'LIMIT_REDUCTION_FEE')
              AND status='ACTIVE'
            GROUP BY loan_product, charge_type
            ORDER BY loan_product, charge_type
        """))
        rows2 = result2.fetchall()
        if rows2:
            print(f"{'Loan Product':<30} {'Charge Type':<30} {'Count':<10}")
            print("-" * 70)
            for row in rows2:
                print(f"{row[0]:<30} {row[1]:<30} {row[2]:<10}")
        else:
            print("No LIMIT_ENHANCEMENT_FEE or LIMIT_REDUCTION_FEE found in any loan product")
            print("✅ All enhancement/reduction fees use PROCESSING_FEE with charge_context")

if __name__ == "__main__":
    audit_fast_cash()

