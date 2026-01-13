"""
Add Dhaka region to the database and remove Bangladesh from region lists
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

# Add location_service to path
sys.path.insert(0, os.path.dirname(__file__))

from models import Region, City, Base
from location_service import get_database_url

def add_dhaka_region():
    """Add Dhaka region to database"""
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Check if Dhaka region already exists
        dhaka_region = session.query(Region).filter(
            Region.region_name.ilike('Dhaka')
        ).first()
        
        if dhaka_region:
            print(f"✓ Dhaka region already exists: {dhaka_region.region_name} (code: {dhaka_region.region_code})")
        else:
            # Create Dhaka region
            dhaka_region = Region(
                region_code='DHAKA',
                region_name='Dhaka',
                country_code='50'
            )
            session.add(dhaka_region)
            session.commit()
            print(f"✓ Created Dhaka region: {dhaka_region.region_name} (code: {dhaka_region.region_code})")
        
        # List all regions
        all_regions = session.query(Region).order_by(Region.region_name).all()
        print(f"\nAll regions in database ({len(all_regions)}):")
        for region in all_regions:
            print(f"  - {region.region_name} (code: {region.region_code})")
        
        # Check if Bangladesh exists
        bangladesh_region = session.query(Region).filter(
            Region.region_name.ilike('Bangladesh')
        ).first()
        
        if bangladesh_region:
            print(f"\n⚠ Bangladesh region exists: {bangladesh_region.region_name}")
            print("  Note: Bangladesh will be filtered out in the API/JavaScript, not deleted from database")
        else:
            print("\n✓ Bangladesh region not found in database")
        
        return dhaka_region
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 70)
    print("Adding Dhaka Region to Database")
    print("=" * 70)
    add_dhaka_region()
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)








