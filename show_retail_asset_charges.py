"""Show current retail asset charges from database"""
import psycopg2
from decimal import Decimal

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="bank_fee_db",
    user="postgres",
    password="changeme"
)

cur = conn.cursor()

# Query retail asset charges
cur.execute("""
    SELECT 
        charge_id,
        loan_product,
        loan_product_name,
        charge_type,
        charge_context,
        charge_title,
        charge_description,
        fee_value,
        fee_unit,
        fee_basis,
        fee_text,
        answer_text,
        parse_status,
        original_charge_text,
        remarks,
        status,
        effective_from
    FROM retail_asset_charge_master_v2
    WHERE status = 'ACTIVE'
    ORDER BY 
        CASE 
            WHEN charge_type = 'PENAL_INTEREST' THEN 1
            WHEN charge_type = 'PROCESSING_FEE' THEN 2
            ELSE 3
        END,
        loan_product,
        effective_from DESC
    LIMIT 20
""")

results = cur.fetchall()

print("\n" + "="*120)
print("RETAIL ASSET CHARGES - CURRENT DATA (Top 20)")
print("="*120 + "\n")

if not results:
    print("❌ No active retail asset charges found!\n")
else:
    for idx, row in enumerate(results, 1):
        charge_id, loan_product, loan_product_name, charge_type, charge_context, charge_title, \
        charge_description, fee_value, fee_unit, fee_basis, fee_text, answer_text, parse_status, \
        original_charge_text, remarks, status, effective_from = row
        
        print(f"{idx}. {charge_title}")
        print(f"   ID: {charge_id}")
        print(f"   Product: {loan_product} ({loan_product_name})")
        print(f"   Type: {charge_type}")
        print(f"   Context: {charge_context}")
        print(f"   Description: {charge_description or '-'}")
        print(f"   Fee Value: {fee_value} {fee_unit}" if fee_value else f"   Fee Value: {fee_unit}")
        print(f"   Fee Basis: {fee_basis}")
        print(f"   Fee Text: {fee_text or '-'}")
        print(f"   Answer Text: {answer_text or '(not set)'}")
        print(f"   Parse Status: {parse_status or 'UNPARSED'}")
        print(f"   Original Text: {original_charge_text or '-'}")
        print(f"   Remarks: {remarks or '-'}")
        print(f"   Status: {status}")
        print(f"   Effective: {effective_from}")
        print(f"\n{'-'*120}\n")

# Count by parse_status
cur.execute("""
    SELECT 
        parse_status,
        COUNT(*) as count
    FROM retail_asset_charge_master_v2
    WHERE status = 'ACTIVE'
    GROUP BY parse_status
    ORDER BY count DESC
""")

parse_stats = cur.fetchall()

print("\n" + "="*80)
print("PARSE STATUS SUMMARY")
print("="*80 + "\n")

for status, count in parse_stats:
    print(f"{status or 'NULL'}: {count} charges")

print(f"\n{'='*80}\n")

cur.close()
conn.close()
