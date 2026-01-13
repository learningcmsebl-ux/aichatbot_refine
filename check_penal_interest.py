import psycopg2
import json

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="bank_fee_db",
    user="postgres",
    password="changeme"
)

cur = conn.cursor()

# Query for Penal Interest charges
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
        remarks,
        status
    FROM retail_asset_charge_master_v2
    WHERE charge_type = 'PENAL_INTEREST'
    ORDER BY effective_from DESC
""")

results = cur.fetchall()

print(f"\n{'='*80}")
print(f"PENAL INTEREST CHARGES IN DATABASE")
print(f"{'='*80}\n")

if not results:
    print("❌ No Penal Interest charges found in database!\n")
else:
    for row in results:
        print(f"Charge ID: {row[0]}")
        print(f"Loan Product: {row[1]} ({row[2]})")
        print(f"Charge Type: {row[3]}")
        print(f"Charge Context: {row[4]}")
        print(f"Charge Title: {row[5]}")
        print(f"Description: {row[6]}")
        print(f"Fee Value: {row[7]}")
        print(f"Fee Unit: {row[8]}")
        print(f"Fee Basis: {row[9]}")
        print(f"Remarks: {row[10]}")
        print(f"Status: {row[11]}")
        print(f"\n{'-'*80}\n")

cur.close()
conn.close()
