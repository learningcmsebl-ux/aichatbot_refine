"""
Import location data from Excel files into normalized PostgreSQL database
"""

import pandas as pd
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import logging
from typing import Dict, Optional

try:
    from .models import Base, Region, City, Address, Branch, Machine, PriorityCenter
except ImportError:
    from models import Base, Region, City, Address, Branch, Machine, PriorityCenter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Construct database URL from environment variables"""
    url = os.getenv("LOCATION_SERVICE_DB_URL")
    if url:
        return url
    
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'postgres')
    
    from urllib.parse import quote_plus
    password_encoded = quote_plus(password) if password else ''
    
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

def get_or_create_region(session, region_code: str, region_name: str, country_code: str = "50") -> Region:
    """Get existing region or create new one"""
    region = session.query(Region).filter(
        Region.region_code == region_code
    ).first()
    
    if not region:
        region = Region(
            region_code=region_code,
            region_name=region_name,
            country_code=country_code
        )
        session.add(region)
        session.flush()
        logger.info(f"Created region: {region_name}")
    
    return region

def get_or_create_city(session, city_name: str, region: Region) -> City:
    """Get existing city or create new one"""
    city = session.query(City).join(Region).filter(
        City.city_name == city_name,
        City.region_id == region.region_id
    ).first()
    
    if not city:
        city = City(
            city_name=city_name,
            region_id=region.region_id
        )
        session.add(city)
        session.flush()
        logger.info(f"Created city: {city_name} in {region.region_name}")
    
    return city

def get_or_create_address(session, street_address: str, zip_code: Optional[str], city: City) -> Address:
    """Get existing address or create new one"""
    address = session.query(Address).join(City).filter(
        Address.street_address == street_address,
        Address.city_id == city.city_id
    ).first()
    
    if not address:
        address = Address(
            street_address=street_address.strip() if street_address else "",
            zip_code=zip_code if pd.notna(zip_code) else None,
            city_id=city.city_id
        )
        session.add(address)
        session.flush()
    
    return address

def import_branches(session, excel_path: str):
    """Import branches from Branch-Info.xlsx"""
    logger.info(f"Importing branches from {excel_path}")
    
    df = pd.read_excel(excel_path)
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    imported = 0
    skipped = 0
    
    for _, row in df.iterrows():
        try:
            branch_code = str(row['BRANCH_CODE']).strip()
            branch_name = str(row['BRANCH_NAME']).strip()
            address_str = str(row['ADDRESS']).strip() if pd.notna(row['ADDRESS']) else ""
            city_name = str(row['CITY_NAME']).strip() if pd.notna(row['CITY_NAME']) else ""
            region_name = str(row['REGION_NAME']).strip() if pd.notna(row['REGION_NAME']) else ""
            region_code = str(row['REGION_CODE']).strip() if pd.notna(row['REGION_CODE']) else ""
            country_code = str(row['COUNTRY_CODE']).strip() if pd.notna(row['COUNTRY_CODE']) else "50"
            status = str(row['STATUS']).strip() if pd.notna(row['STATUS']) else "A"
            zip_code = row['ZIP_CODE'] if pd.notna(row['ZIP_CODE']) else None
            
            # Skip if essential data is missing
            if not branch_code or not branch_name or not city_name or not region_name:
                skipped += 1
                continue
            
            # Get or create region
            if not region_code:
                region_code = region_name.upper().replace(" ", "_")
            
            region = get_or_create_region(session, region_code, region_name, country_code)
            
            # Get or create city
            city = get_or_create_city(session, city_name, region)
            
            # Get or create address
            address = get_or_create_address(session, address_str, zip_code, city)
            
            # Check if branch already exists
            existing = session.query(Branch).filter(Branch.branch_code == branch_code).first()
            if existing:
                # Update existing branch
                existing.branch_name = branch_name
                existing.address_id = address.address_id
                existing.status = status
                existing.is_head_office = "HEAD OFFICE" in branch_name.upper()
                logger.info(f"Updated branch: {branch_name}")
            else:
                # Create new branch
                is_head_office = "HEAD OFFICE" in branch_name.upper()
                branch = Branch(
                    branch_code=branch_code,
                    branch_name=branch_name,
                    address_id=address.address_id,
                    status=status,
                    is_head_office=is_head_office
                )
                session.add(branch)
                imported += 1
                logger.debug(f"Imported branch: {branch_name}")
        
        except Exception as e:
            logger.error(f"Error importing branch {row.get('BRANCH_NAME', 'unknown')}: {str(e)}")
            skipped += 1
            continue
    
    session.commit()
    logger.info(f"Branches import complete: {imported} imported, {skipped} skipped")

def import_machines(session, excel_path: str):
    """Import ATM/CRM/RTDM from ATM_CRM_RTDM_locations.xlsx"""
    logger.info(f"Importing machines from {excel_path}")
    
    # Read with header=None to handle the first row being headers
    df = pd.read_excel(excel_path, header=None)
    
    # Skip first row (header row) and set column names
    df_clean = df.iloc[1:].copy()
    df_clean.columns = ['SL', 'Machine_Type', 'Machine_Count', 'Address']
    
    imported = 0
    skipped = 0
    
    for _, row in df_clean.iterrows():
        try:
            machine_type = str(row['Machine_Type']).strip().upper() if pd.notna(row['Machine_Type']) else ""
            machine_count = int(row['Machine_Count']) if pd.notna(row['Machine_Count']) else 1
            address_str = str(row['Address']).strip() if pd.notna(row['Address']) else ""
            
            # Skip if essential data is missing
            if not machine_type or not address_str or machine_type == "MACHINE TYPE":
                skipped += 1
                continue
            
            # Parse address to extract city (simple heuristic)
            # Address format: "Street, City, Region" or "Street, City"
            address_parts = [p.strip() for p in address_str.split(',')]
            
            # Try to find city and region from address string
            # This is a simplified parser - may need refinement
            city_name = None
            region_name = None
            
            # Try to match with existing cities
            if len(address_parts) >= 2:
                # Last part might be city or region
                potential_city = address_parts[-1].strip()
                city = session.query(City).filter(City.city_name.ilike(f"%{potential_city}%")).first()
                if city:
                    city_name = city.city_name
                    region_name = city.region.region_name
                else:
                    # Try second to last
                    if len(address_parts) >= 3:
                        potential_city = address_parts[-2].strip()
                        city = session.query(City).filter(City.city_name.ilike(f"%{potential_city}%")).first()
                        if city:
                            city_name = city.city_name
                            region_name = city.region.region_name
            
            # If no city found, try to extract from common patterns
            if not city_name:
                # Common city names in Bangladesh
                common_cities = ['Dhaka', 'Chittagong', 'Sylhet', 'Khulna', 'Rajshahi', 'Barisal', 'Rangpur']
                for common_city in common_cities:
                    if common_city.lower() in address_str.lower():
                        city = session.query(City).filter(City.city_name.ilike(f"%{common_city}%")).first()
                        if city:
                            city_name = city.city_name
                            region_name = city.region.region_name
                            break
            
            # If still no city, create a default one or skip
            if not city_name:
                # Try to create with "Unknown" city in first available region
                region = session.query(Region).first()
                if region:
                    city = get_or_create_city(session, "Unknown", region)
                    city_name = city.city_name
                    region_name = city.region.region_name
                else:
                    skipped += 1
                    logger.warning(f"Could not determine city for address: {address_str}")
                    continue
            
            city = session.query(City).filter(City.city_name == city_name).first()
            if not city:
                skipped += 1
                continue
            
            # Get or create address
            address = get_or_create_address(session, address_str, None, city)
            
            # Create machine
            machine = Machine(
                machine_type=machine_type,
                machine_count=machine_count,
                address_id=address.address_id,
                branch_id=None  # Can be linked later if needed
            )
            session.add(machine)
            imported += 1
            logger.debug(f"Imported {machine_type}: {address_str[:50]}")
        
        except Exception as e:
            logger.error(f"Error importing machine: {str(e)}")
            skipped += 1
            continue
    
    session.commit()
    logger.info(f"Machines import complete: {imported} imported, {skipped} skipped")

def import_priority_centers(session, excel_path: str):
    """Import priority centers from Priority_Centers_Fully_Normalized.xlsx"""
    logger.info(f"Importing priority centers from {excel_path}")
    
    df = pd.read_excel(excel_path)
    
    imported = 0
    skipped = 0
    
    for _, row in df.iterrows():
        try:
            city_id_val = row.get('CityID', None)
            city_name = str(row.get('CityName', '')).strip() if pd.notna(row.get('CityName')) else ""
            
            if not city_name:
                skipped += 1
                continue
            
            # Find city by name
            city = session.query(City).filter(City.city_name.ilike(f"%{city_name}%")).first()
            
            if not city:
                # Try to create city in first available region
                region = session.query(Region).first()
                if region:
                    city = get_or_create_city(session, city_name, region)
                else:
                    skipped += 1
                    logger.warning(f"Could not find or create city: {city_name}")
                    continue
            
            # Check if priority center already exists
            existing = session.query(PriorityCenter).filter(PriorityCenter.city_id == city.city_id).first()
            if existing:
                # Update existing
                existing.center_name = city_name
                logger.info(f"Updated priority center: {city_name}")
            else:
                # Create new priority center
                pc = PriorityCenter(
                    city_id=city.city_id,
                    center_name=city_name
                )
                session.add(pc)
                imported += 1
                logger.debug(f"Imported priority center: {city_name}")
        
        except Exception as e:
            logger.error(f"Error importing priority center: {str(e)}")
            skipped += 1
            continue
    
    session.commit()
    logger.info(f"Priority centers import complete: {imported} imported, {skipped} skipped")

def main():
    """Main import function"""
    # Get Excel file paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    excel_dir = os.path.join(base_dir, "xls", "location_service")
    
    branch_file = os.path.join(excel_dir, "Branch-Info.xlsx")
    machine_file = os.path.join(excel_dir, "ATM_CRM_RTDM_locations.xlsx")
    priority_file = os.path.join(excel_dir, "Priority_Centers_Fully_Normalized.xlsx")
    
    # Check files exist
    if not os.path.exists(branch_file):
        logger.error(f"Branch file not found: {branch_file}")
        return
    if not os.path.exists(machine_file):
        logger.error(f"Machine file not found: {machine_file}")
        return
    if not os.path.exists(priority_file):
        logger.error(f"Priority center file not found: {priority_file}")
        return
    
    # Connect to database
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    session = SessionLocal()
    
    try:
        # Import in order: regions/cities first (from branches), then branches, machines, priority centers
        logger.info("Starting data import...")
        
        # Import branches (this will create regions and cities)
        import_branches(session, branch_file)
        
        # Import machines
        import_machines(session, machine_file)
        
        # Import priority centers
        import_priority_centers(session, priority_file)
        
        logger.info("Data import completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during import: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()

