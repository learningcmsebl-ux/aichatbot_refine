"""Test script to verify location service data"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus

from models import Branch, Machine, PriorityCenter, Region, City

def get_database_url():
    """Construct database URL from environment variables"""
    url = os.getenv("LOCATION_SERVICE_DB_URL")
    if url:
        return url
    
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    user = os.getenv('POSTGRES_USER', 'chatbot_user')
    password = os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'chatbot_db')
    
    password_encoded = quote_plus(password) if password else ''
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

if __name__ == "__main__":
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        print("=" * 50)
        print("Location Service Data Verification")
        print("=" * 50)
        
        # Count records
        branch_count = session.query(Branch).count()
        machine_count = session.query(Machine).count()
        priority_center_count = session.query(PriorityCenter).count()
        head_office_count = session.query(Branch).filter(Branch.is_head_office == True).count()
        region_count = session.query(Region).count()
        city_count = session.query(City).count()
        
        print(f"\nRegions: {region_count}")
        print(f"Cities: {city_count}")
        print(f"Branches: {branch_count}")
        print(f"  - Head Office: {head_office_count}")
        print(f"Machines: {machine_count}")
        print(f"  - ATMs: {session.query(Machine).filter(Machine.machine_type == 'ATM').count()}")
        print(f"  - CRMs: {session.query(Machine).filter(Machine.machine_type == 'CRM').count()}")
        print(f"  - RTDMs: {session.query(Machine).filter(Machine.machine_type == 'RTDM').count()}")
        print(f"Priority Centers: {priority_center_count}")
        
        # Sample data
        print("\n" + "=" * 50)
        print("Sample Data")
        print("=" * 50)
        
        # Sample branch
        sample_branch = session.query(Branch).first()
        if sample_branch:
            print(f"\nSample Branch:")
            print(f"  Name: {sample_branch.branch_name}")
            print(f"  Code: {sample_branch.branch_code}")
            print(f"  Address: {sample_branch.address.street_address}")
            print(f"  City: {sample_branch.address.city.city_name}")
            print(f"  Region: {sample_branch.address.city.region.region_name}")
            print(f"  Head Office: {sample_branch.is_head_office}")
        
        # Head office
        head_office = session.query(Branch).filter(Branch.is_head_office == True).first()
        if head_office:
            print(f"\nHead Office:")
            print(f"  Name: {head_office.branch_name}")
            print(f"  Address: {head_office.address.street_address}")
            print(f"  City: {head_office.address.city.city_name}")
        
        # Sample machine
        sample_machine = session.query(Machine).first()
        if sample_machine:
            print(f"\nSample Machine:")
            print(f"  Type: {sample_machine.machine_type}")
            print(f"  Count: {sample_machine.machine_count}")
            print(f"  Address: {sample_machine.address.street_address}")
            print(f"  City: {sample_machine.address.city.city_name}")
        
        # Sample priority center
        sample_pc = session.query(PriorityCenter).first()
        if sample_pc:
            print(f"\nSample Priority Center:")
            print(f"  Name: {sample_pc.center_name or sample_pc.city.city_name}")
            print(f"  City: {sample_pc.city.city_name}")
            print(f"  Region: {sample_pc.city.region.region_name}")
        
        print("\n" + "=" * 50)
        print("Data verification complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

