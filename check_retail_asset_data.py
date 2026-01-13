"""
Script to check if retail asset charges data exists in the database
"""

import sys
from pathlib import Path
from datetime import date

# Add credit_card_rate/fee_engine to path
sys.path.insert(0, str(Path(__file__).parent / "credit_card_rate" / "fee_engine"))

try:
    from fee_engine_service import RetailAssetChargeMaster, get_db_session, get_database_url
    from sqlalchemy import func
except ImportError as e:
    print(f"Error importing: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

def check_retail_asset_data():
    """Check if retail asset charges data exists"""
    print("=" * 70)
    print("RETAIL ASSET CHARGES DATA CHECK")
    print("=" * 70)
    print()
    
    db_url = get_database_url()
    print(f"Database URL: {db_url.split('@')[1] if '@' in db_url else 'hidden'}")
    print()
    
    db = get_db_session()
    
    try:
        # Check total count
        total_count = db.query(func.count(RetailAssetChargeMaster.charge_id)).scalar()
        print(f"Total retail asset charges: {total_count}")
        print()
        
        if total_count == 0:
            print("⚠️  No retail asset charges found in database!")
            print("   You need to import the data first.")
            print("   Run: python credit_card_rate/fee_engine/import_retail_asset_charges.py")
            return False
        
        # Check active count
        active_count = db.query(func.count(RetailAssetChargeMaster.charge_id)).filter(
            RetailAssetChargeMaster.status == "ACTIVE"
        ).scalar()
        print(f"Active charges: {active_count}")
        print()
        
        # Check for FAST_CASH_OD
        fast_cash_count = db.query(func.count(RetailAssetChargeMaster.charge_id)).filter(
            RetailAssetChargeMaster.loan_product == "FAST_CASH_OD",
            RetailAssetChargeMaster.status == "ACTIVE"
        ).scalar()
        print(f"FAST_CASH_OD charges: {fast_cash_count}")
        print()
        
        # Check for LIMIT_REDUCTION_FEE
        limit_reduction_count = db.query(func.count(RetailAssetChargeMaster.charge_id)).filter(
            RetailAssetChargeMaster.charge_type == "LIMIT_REDUCTION_FEE",
            RetailAssetChargeMaster.status == "ACTIVE"
        ).scalar()
        print(f"LIMIT_REDUCTION_FEE charges: {limit_reduction_count}")
        print()
        
        # Check for the specific combination
        today = date.today()
        specific_charge = db.query(RetailAssetChargeMaster).filter(
            RetailAssetChargeMaster.loan_product == "FAST_CASH_OD",
            RetailAssetChargeMaster.charge_type == "LIMIT_REDUCTION_FEE",
            RetailAssetChargeMaster.status == "ACTIVE",
            RetailAssetChargeMaster.effective_from <= today,
            (
                (RetailAssetChargeMaster.effective_to.is_(None)) |
                (RetailAssetChargeMaster.effective_to >= today)
            )
        ).first()
        
        if specific_charge:
            print("✅ Found Fast Cash Limit Reduction Processing Fee!")
            print(f"   Loan Product: {specific_charge.loan_product}")
            print(f"   Charge Type: {specific_charge.charge_type}")
            print(f"   Charge Description: {specific_charge.charge_description}")
            print(f"   Fee Value: {specific_charge.fee_value} {specific_charge.fee_unit}")
            print(f"   Effective From: {specific_charge.effective_from}")
            print(f"   Effective To: {specific_charge.effective_to or 'No expiry'}")
            print(f"   Status: {specific_charge.status}")
            return True
        else:
            print("❌ Fast Cash Limit Reduction Processing Fee NOT FOUND")
            print()
            print("Checking what charges exist for FAST_CASH_OD:")
            fast_cash_charges = db.query(RetailAssetChargeMaster).filter(
                RetailAssetChargeMaster.loan_product == "FAST_CASH_OD",
                RetailAssetChargeMaster.status == "ACTIVE"
            ).all()
            
            if fast_cash_charges:
                print(f"   Found {len(fast_cash_charges)} charge(s):")
                for charge in fast_cash_charges:
                    print(f"   - {charge.charge_type}: {charge.charge_description}")
                    print(f"     Effective: {charge.effective_from} to {charge.effective_to or 'No expiry'}")
            else:
                print("   No FAST_CASH_OD charges found")
            
            print()
            print("Checking what charge types exist:")
            charge_types = db.query(RetailAssetChargeMaster.charge_type).filter(
                RetailAssetChargeMaster.status == "ACTIVE"
            ).distinct().all()
            
            if charge_types:
                print(f"   Found {len(charge_types)} charge type(s):")
                for ct in charge_types:
                    print(f"   - {ct[0]}")
            
            return False
        
    except Exception as e:
        print(f"❌ Error checking data: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    check_retail_asset_data()

